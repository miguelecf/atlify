#!/usr/bin/env python3
"""Extracts the structural skeleton of a repository to JSON.

Supports Java/Spring, JS/TS/React and Python/FastAPI using heuristics
(regex), not a real parser. The skeleton is the mechanical part of the atlas:
the agent uses it as a map to write .atlify/atlas.json, and validate.py uses
it to measure coverage.

Usage:
    python extract.py <repo> [-o <repo>/.atlify/skeleton.json] [--routes]

Prints to stdout a compact tree (id, type, name) so the agent never has to
read the whole JSON, plus suspicious HTTP calls (TO REVIEW) and a diff
against the previous skeleton when one exists. With --routes it prints only
the endpoint inventory, the TO REVIEW block and the diff — the token-lean
form for --endpoint mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

IGNORAR = {
    ".git", "node_modules", "target", "build", "dist", "out", ".idea", ".vscode",
    ".gradle", "coverage", "__pycache__", ".mentor", ".atlas", ".atlify", ".next", "venv",
    ".venv", "env", ".mvn", ".pytest_cache", ".mypy_cache", "migrations", "alembic",
}
EXT_JAVA = {".java"}
EXT_JS = {".js", ".jsx", ".ts", ".tsx", ".mjs"}
EXT_PY = {".py"}
MAX_BYTES = 400_000  # larger files are ignored (generated, bundles)

DB_IMAGENES = ("mysql", "mariadb", "postgres", "mongo", "redis", "sqlserver", "mssql", "oracle")


# ─────────────────────────── utilities ───────────────────────────

def leer(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def nro_linea(texto: str, pos: int) -> int:
    return texto.count("\n", 0, pos) + 1


def h(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8", "replace")).hexdigest()[:12]


def caminar(raiz: Path):
    raiz = raiz.resolve()
    pila = [raiz]
    while pila:
        d = pila.pop()
        try:
            entradas = sorted(d.iterdir())
        except OSError:
            continue
        for e in entradas:
            if e.name in IGNORAR or (e.name.startswith(".") and e.is_dir()):
                continue
            if e.is_symlink():
                if e.is_dir():
                    continue  # do not follow directory symlinks: they can form cycles
                try:
                    if not e.resolve().is_relative_to(raiz):
                        continue  # the real file is outside the repo
                except (OSError, RuntimeError):
                    continue
                yield e
            elif e.is_dir():
                pila.append(e)
            elif e.is_file():
                yield e


def es_test(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    return ("/test/" in r or "/tests/" in r or "/__tests__/" in r or r.startswith("test")
            or ".test." in r or ".spec." in r or r.endswith("test.java") or "/test_" in r)


# ─────────────────────────── containers ───────────────────────────

def detectar_contenedores(raiz: Path) -> list[dict]:
    conts = []
    for f in caminar(raiz):
        rel_dir = f.parent.relative_to(raiz).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        nombre_dir = f.parent.name if rel_dir else raiz.name
        if f.name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            txt = leer(f)
            tipo = "spring-boot" if "spring-boot" in txt or "org.springframework.boot" in txt else "java"
            conts.append({"dir": rel_dir, "nombre": nombre_dir, "tipo": tipo, "lenguaje": "java"})
        elif f.name == "package.json":
            txt = leer(f)
            try:
                pj = json.loads(txt)
            except json.JSONDecodeError:
                pj = {}
            deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
            if not any(k in deps for k in ("react", "vue", "svelte", "@angular/core", "express", "next", "vite", "fastify")):
                continue  # tooling package.json (husky, etc.)
            tipo = ("react" if "react" in deps else "vue" if "vue" in deps else "angular" if "@angular/core" in deps
                    else "svelte" if "svelte" in deps else "node")
            conts.append({"dir": rel_dir, "nombre": nombre_dir, "tipo": tipo, "lenguaje": "js"})
        elif f.name in ("pyproject.toml", "requirements.txt", "setup.py"):
            txt = leer(f).lower()
            tipo = "fastapi" if "fastapi" in txt else "django" if "django" in txt else "flask" if "flask" in txt else "python"
            conts.append({"dir": rel_dir, "nombre": nombre_dir, "tipo": tipo, "lenguaje": "py"})
    # dedupe by (dir, language)
    vistos, unicos = set(), []
    for c in conts:
        k = (c["dir"], c["lenguaje"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(c)
    return unicos


def leer_compose(raiz: Path) -> list[dict]:
    """docker-compose services: name, image and build context."""
    archivos = [p for n in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
                for p in [raiz / n] if p.exists()]
    servicios = []
    for arch in archivos:
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(leer(arch)) or {}
            for nombre, s in (data.get("services") or {}).items():
                s = s or {}
                build = s.get("build")
                ctx = build.get("context") if isinstance(build, dict) else build
                servicios.append({"nombre": nombre, "imagen": s.get("image") or "", "build": ctx or ""})
        except Exception:
            # minimal fallback without PyYAML
            actual = None
            for linea in leer(arch).splitlines():
                m = re.match(r"^  (\w[\w-]*):\s*$", linea)
                if m:
                    actual = {"nombre": m.group(1), "imagen": "", "build": ""}
                    servicios.append(actual)
                elif actual:
                    mi = re.match(r"^\s+image:\s*['\"]?([^'\"\s]+)", linea)
                    mb = re.match(r"^\s+(?:build|context):\s*['\"]?([^'\"\s]+)", linea)
                    if mi:
                        actual["imagen"] = mi.group(1)
                    elif mb and not actual["build"]:
                        actual["build"] = mb.group(1)
    return servicios


# ─────────────────────────── Java ───────────────────────────

RE_PKG = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
RE_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+?)(\.\*)?\s*;", re.M)
RE_TIPO = re.compile(r"^[ \t]*(?:public\s+|protected\s+|private\s+)?(?:(?:abstract|final|sealed|static)\s+)*"
                     r"(class|interface|enum|record|@interface)\s+(\w+)", re.M)
RE_METODO_JAVA = re.compile(r"^[ \t]*(?:@\w+(?:\([^)]*\))?\s*)*(?:public|protected|private)\s+(?:static\s+|final\s+|"
                            r"synchronized\s+|abstract\s+|default\s+)*(?:<[^>]+>\s+)?[\w<>\[\],.?\s]+?\s+(\w+)\s*\(", re.M)
RE_METODO_IFACE = re.compile(r"^[ \t]+(?:default\s+)?[\w<>\[\],.?]+(?:\s*<[^;{]*>)?\s+(\w+)\s*\([^;{]*\)\s*;", re.M)
RE_MAPPING = re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping\s*(?:\(([^)]*)\))?")
RE_STR = re.compile(r"\"([^\"]*)\"")

STEREOTIPOS = [
    ("SpringBootApplication", "aplicacion"), ("RestControllerAdvice", "manejo-errores"),
    ("ControllerAdvice", "manejo-errores"), ("RestController", "controller"), ("Controller", "controller"),
    ("Service", "service"), ("Repository", "repository"), ("Entity", "entity"), ("Table", "entity"),
    ("Configuration", "config"), ("Mapper", "mapper"), ("Component", "component"),
]


def tipo_java(txt: str, nombre: str, clase: str, pos_tipo: int) -> str:
    anots = set(re.findall(r"@(\w+)", txt[:pos_tipo] if pos_tipo else txt))
    for anot, tipo in STEREOTIPOS:
        if anot in anots:
            return tipo
    if re.search(r"extends\s+(Jpa|Crud|PagingAndSorting|Mongo)Repository", txt):
        return "repository"
    if re.search(r"extends\s+\w*(Exception|Error)\b", txt):
        return "excepcion"
    if re.search(r"(Dto|DTO|Request|Response|Form)$", nombre):
        return "dto"
    if clase == "enum":
        return "enum"
    if clase == "interface":
        return "interface"
    return "clase"


def parse_java(txt: str, nombre_archivo: str) -> dict:
    mp = RE_PKG.search(txt)
    pkg = mp.group(1) if mp else ""
    mt = RE_TIPO.search(txt)
    clase, nombre = (mt.group(1), mt.group(2)) if mt else ("class", Path(nombre_archivo).stem)
    linea_tipo = nro_linea(txt, mt.start()) if mt else 1
    pos_tipo = mt.start() if mt else 0

    metodos = []
    patron = RE_METODO_IFACE if clase == "interface" else RE_METODO_JAVA
    for m in patron.finditer(txt):
        n = m.group(1)
        if n in (nombre, "if", "for", "while", "switch", "return", "new", "catch"):
            continue
        metodos.append({"nombre": n, "linea": nro_linea(txt, m.start(1))})

    # endpoints: class prefix + method mappings
    prefijo = ""
    endpoints = []
    for m in RE_MAPPING.finditer(txt):
        args = m.group(2) or ""
        s = RE_STR.search(args)
        ruta = s.group(1) if s else ""
        if m.start() < pos_tipo:
            if m.group(1) == "Request":
                prefijo = ruta
            continue
        verbo = m.group(1).upper()
        if verbo == "REQUEST":
            mv = re.search(r"RequestMethod\.(\w+)", args)
            verbo = mv.group(1) if mv else "ANY"
        endpoints.append({"metodo": verbo, "ruta": unir_rutas(prefijo, ruta), "linea": nro_linea(txt, m.start())})

    imports = [m.group(1) for m in RE_IMPORT.finditer(txt) if not m.group(2)]
    return {"paquete": pkg, "nombre": nombre, "clase": clase, "linea": linea_tipo,
            "tipo": tipo_java(txt, nombre, clase, pos_tipo),"metodos": metodos, "endpoints": endpoints, "imports": imports}


def unir_rutas(a: str, b: str) -> str:
    r = "/" + "/".join(p for p in (a.strip("/"), b.strip("/")) if p)
    return r


# ─────────────────────────── JS / TS ───────────────────────────

RE_IMPORT_JS = re.compile(r"""(?:import\s[^'"`;]*?from\s*|import\s*\(?\s*|require\s*\(\s*)['"]([^'"]+)['"]""")
RE_EXPORT_FN = re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)", re.M)
RE_EXPORT_CONST = re.compile(r"^\s*export\s+(?:default\s+)?const\s+(\w+)\s*=", re.M)
RE_FN_TOP = re.compile(r"^(?:async\s+)?function\s+(\w+)|^const\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>", re.M)
RE_HTTP = re.compile(r"""\b\w+\.(get|post|put|delete|patch)\s*(?:<[^>]*>)?\(\s*([`'"])(.*?)\2""", re.S)
RE_FETCH = re.compile(r"""\bfetch\s*\(\s*([`'"])(.*?)\1""", re.S)


def tipo_js(rel: str, nombre: str, txt: str) -> str:
    partes = [p.lower() for p in Path(rel).parts]
    if nombre.startswith("use") and len(nombre) > 3 and nombre[3].isupper():
        return "hook"
    for clave, tipo in (("pages", "pagina"), ("views", "pagina"), ("routes", "rutas"), ("hooks", "hook"),
                        ("context", "contexto"), ("store", "estado"), ("services", "servicio-api"),
                        ("api", "servicio-api"), ("utils", "util"), ("lib", "util"), ("components", "componente-ui")):
        if clave in partes[:-1]:
            return tipo
    if Path(rel).suffix in (".jsx", ".tsx") or re.search(r"return\s*\(\s*<", txt):
        return "componente-ui" if nombre[:1].isupper() else "modulo-ui"
    return "modulo"


def parse_js(txt: str, rel: str) -> dict:
    nombre = Path(rel).stem
    if nombre == "index":
        nombre = Path(rel).parent.name or nombre
    metodos, vistos = [], set()
    for r in (RE_EXPORT_FN, RE_EXPORT_CONST):
        for m in r.finditer(txt):
            if m.group(1) not in vistos:
                vistos.add(m.group(1))
                metodos.append({"nombre": m.group(1), "linea": nro_linea(txt, m.start(1)), "exportado": True})
    for m in RE_FN_TOP.finditer(txt):
        n = m.group(1) or m.group(2)
        if n and n not in vistos:
            vistos.add(n)
            metodos.append({"nombre": n, "linea": nro_linea(txt, m.start())})
    metodos.sort(key=lambda x: x["linea"])

    http = []
    for m in RE_HTTP.finditer(txt):
        ruta = m.group(3)
        if "/" in ruta and "\n" not in ruta:
            http.append({"metodo": m.group(1).upper(), "ruta": ruta, "linea": nro_linea(txt, m.start())})
    for m in RE_FETCH.finditer(txt):
        ruta = m.group(2)
        if "\n" in ruta:
            continue
        cola = txt[m.end(): m.end() + 250]
        mv = re.search(r"method\s*:\s*['\"](\w+)['\"]", cola)
        http.append({"metodo": (mv.group(1) if mv else "GET").upper(), "ruta": ruta, "linea": nro_linea(txt, m.start())})

    imports = [m.group(1) for m in RE_IMPORT_JS.finditer(txt)]
    return {"nombre": nombre, "tipo": tipo_js(rel, nombre, txt), "metodos": metodos, "http": http, "imports": imports}


def resolver_js(origen: Path, spec: str, raiz_cont: Path) -> Path | None:
    if spec.startswith("@/"):
        base = raiz_cont / "src" / spec[2:]
    elif spec.startswith("~/"):
        base = raiz_cont / "src" / spec[2:]
    elif spec.startswith("."):
        base = (origen.parent / spec)
    else:
        return None
    candidatos = [base] + [base.with_name(base.name + e) for e in EXT_JS] + [base / ("index" + e) for e in EXT_JS]
    for c in candidatos:
        if c.is_file():
            return c.resolve()
    return None


# ─────────────────────────── Python ───────────────────────────

RE_PY_DEF = re.compile(r"^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)", re.M)
RE_PY_ROUTE = re.compile(r"^[ \t]*@(\w+)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]*)['\"]", re.M)
RE_PY_PREFIX = re.compile(r"^[ \t]*(\w+)\s*(?::[^=\n]+)?=\s*APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]", re.M)
RE_PY_IMPORT = re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import\s+([\w, ()*]+)|import\s+([\w.]+))", re.M)


def tipo_py(rel: str, txt: str) -> str:
    partes = [p.lower() for p in Path(rel).parts]
    if RE_PY_ROUTE.search(txt):
        return "controller"
    for clave, tipo in (("routers", "controller"), ("routes", "controller"), ("api", "controller"),
                        ("services", "service"), ("repositories", "repository"), ("repos", "repository"),
                        ("models", "entity"), ("schemas", "dto"), ("core", "config"), ("utils", "util")):
        if clave in partes[:-1]:
            return tipo
    if "declarative_base" in txt or "Mapped[" in txt or "__tablename__" in txt:
        return "entity"
    if "BaseModel" in txt:
        return "dto"
    if Path(rel).name == "main.py":
        return "aplicacion"
    return "modulo"


def parse_py(txt: str, rel: str) -> dict:
    metodos = [{"nombre": m.group(1) or m.group(2), "linea": nro_linea(txt, m.start())} for m in RE_PY_DEF.finditer(txt)]
    prefijos = {m.group(1): m.group(2) for m in RE_PY_PREFIX.finditer(txt)}
    endpoints = [{"metodo": m.group(2).upper(), "ruta": unir_rutas(prefijos.get(m.group(1), ""), m.group(3)),
                  "linea": nro_linea(txt, m.start())}
                 for m in RE_PY_ROUTE.finditer(txt)]
    imports = []
    for m in RE_PY_IMPORT.finditer(txt):
        if m.group(1) is not None:
            imports.append((m.group(1), [n.strip(" ()") for n in m.group(2).split(",")]))
        else:
            imports.append((m.group(3), []))
    nombre = Path(rel).stem if Path(rel).stem != "__init__" else Path(rel).parent.name
    return {"nombre": nombre, "tipo": tipo_py(rel, txt), "metodos": metodos, "endpoints": endpoints, "imports": imports}


def resolver_py(origen: Path, modulo: str, nombres: list[str], raiz_cont: Path) -> list[Path]:
    if modulo.startswith("."):
        puntos = len(modulo) - len(modulo.lstrip("."))
        base = origen.parent
        for _ in range(puntos - 1):
            base = base.parent
        partes = [p for p in modulo.lstrip(".").split(".") if p]
        bases = [base.joinpath(*partes)]
    else:
        partes = modulo.split(".")
        bases = [raiz_cont.joinpath(*partes), (raiz_cont / "src").joinpath(*partes)]
    res = []
    for b in bases:
        if b.with_suffix(".py").is_file():
            res.append(b.with_suffix(".py").resolve())
        elif b.is_dir():
            for n in nombres:  # from package import name
                if (b / f"{n}.py").is_file():
                    res.append((b / f"{n}.py").resolve())
            if (b / "__init__.py").is_file() and not res:
                res.append((b / "__init__.py").resolve())
        if res:
            break
    return res


# ─────────────────────────── matching HTTP ───────────────────────────

def segmentos(ruta: str) -> list[str]:
    ruta = re.sub(r"^https?://[^/]+", "", ruta)
    ruta = re.sub(r"^\$\{[^}]*\}", "", ruta)  # ${API_URL}/...
    ruta = ruta.split("?")[0]
    segs = []
    for s in ruta.strip("/").split("/"):
        if not s:
            continue
        segs.append("*" if re.fullmatch(r"\{[^}]*\}|\$\{[^}]*\}|:\w+|\d+", s) or "${" in s else s.lower())
    return segs


def coincide(front: list[str], back: list[str]) -> bool:
    if not front or not back:
        return False
    corto, largo = (front, back) if len(front) <= len(back) else (back, front)
    if all(s == "*" for s in corto):
        return False
    cola = largo[len(largo) - len(corto):]
    return all(a == b or a == "*" or b == "*" for a, b in zip(corto, cola))


# ─────────────────────────── main ───────────────────────────

def extraer(raiz: Path) -> dict:
    raiz = raiz.resolve()
    conts = detectar_contenedores(raiz)
    compose = leer_compose(raiz)

    nodos: dict[str, dict] = {}
    relaciones: list[dict] = []

    def agregar_rel(de, a, etiqueta, origen):
        if de != a and de in nodos and a in nodos:
            relaciones.append({"de": de, "a": a, "etiqueta": etiqueta, "origen": origen})

    # code containers
    for c in conts:
        cid = "c:" + (c["dir"] or c["nombre"]).replace("/", ".")
        c["id"] = cid
        nodos[cid] = {"id": cid, "nombre": c["nombre"], "nivel": "contenedor", "padre": "sistema",
                      "tipo": c["tipo"], "archivo": c["dir"] or ".", "lenguaje": c["lenguaje"]}

    # compose services
    db_ids = []
    for s in compose:
        ctx = (s["build"] or "").strip("./")
        match = next((c for c in conts if c["dir"] and (c["dir"] == ctx or c["dir"].endswith("/" + ctx))), None)
        if match:
            nodos[match["id"]]["servicio_compose"] = s["nombre"]
            continue
        img = s["imagen"].lower()
        if not img:
            continue
        es_db = any(d in img for d in DB_IMAGENES)
        sid = "c:svc." + s["nombre"]
        nodos[sid] = {"id": sid, "nombre": s["nombre"], "nivel": "contenedor", "padre": "sistema",
                      "tipo": "db" if es_db else "infra", "imagen": s["imagen"], "archivo": "docker-compose.yml"}
        if es_db:
            db_ids.append(sid)

    # assign files to the most specific container
    def contenedor_de(rel: str):
        mejor = None
        for c in conts:
            if c["dir"] == "" or rel == c["dir"] or rel.startswith(c["dir"] + "/"):
                if mejor is None or len(c["dir"]) > len(mejor["dir"]):
                    mejor = c
        return mejor

    componentes = []  # (cid, path, parse, lenguaje)
    for f in caminar(raiz):
        ext = f.suffix.lower()
        if ext not in EXT_JAVA | EXT_JS | EXT_PY:
            continue
        rel = f.relative_to(raiz).as_posix()
        if es_test(rel) or f.stat().st_size > MAX_BYTES or rel.endswith((".d.ts", ".config.js", ".config.ts", ".config.mjs")):
            continue
        c = contenedor_de(rel)
        if not c:
            continue
        lang = "java" if ext in EXT_JAVA else "js" if ext in EXT_JS else "py"
        if lang != c["lenguaje"]:
            continue  # e.g. a stray .js inside the Java backend
        txt = leer(f)
        if f.name == "__init__.py" and not RE_PY_DEF.search(txt):
            continue  # empty __init__ or re-exports only: noise
        p = parse_java(txt, f.name) if lang == "java" else parse_js(txt, rel) if lang == "js" else parse_py(txt, rel)
        p["hash"] = h(txt)
        p["texto"] = txt
        componentes.append((c, f.resolve(), rel, p))

    # modules: Java package (relative to the base package) or directory
    paquetes_por_cont: dict[str, list[str]] = {}
    for c, _, _, p in componentes:
        if c["lenguaje"] == "java" and p.get("paquete"):
            paquetes_por_cont.setdefault(c["id"], []).append(p["paquete"])

    def base_comun(pkgs: list[str]) -> str:
        if not pkgs:
            return ""
        partes = [x.split(".") for x in pkgs]
        comun = []
        for grupo in zip(*partes):
            if len(set(grupo)) == 1:
                comun.append(grupo[0])
            else:
                break
        return ".".join(comun)

    bases = {cid: base_comun(pk) for cid, pk in paquetes_por_cont.items()}

    por_path: dict[Path, str] = {}
    por_fqn: dict[str, str] = {}
    por_paquete: dict[tuple[str, str], list[tuple[str, str]]] = {}

    for c, path, rel, p in componentes:
        if c["lenguaje"] == "java" and p.get("paquete"):
            base = bases.get(c["id"], "")
            mod = p["paquete"][len(base):].strip(".") if p["paquete"].startswith(base) else p["paquete"]
            mod = mod or "(root)"
        else:
            rel_c = rel[len(c["dir"]) + 1:] if c["dir"] else rel
            partes = Path(rel_c).parts[:-1]
            if partes and partes[0] in ("src", "app", "lib"):
                partes = partes[1:]
            mod = "/".join(partes) if partes else "(root)"
        mid = f"m:{c['id'][2:]}:{mod}"
        if mid not in nodos:
            nodos[mid] = {"id": mid, "nombre": mod, "nivel": "modulo", "padre": c["id"], "tipo": "paquete"
                          if c["lenguaje"] == "java" else "directorio", "archivo": str(Path(rel).parent.as_posix())}
        kid = f"k:{rel}"
        nodos[kid] = {"id": kid, "nombre": p["nombre"], "nivel": "componente", "padre": mid, "tipo": p["tipo"],
                      "archivo": rel, "linea": p.get("linea", 1), "metodos": p["metodos"], "hash": p["hash"]}
        if p.get("endpoints"):
            nodos[kid]["endpoints"] = p["endpoints"]
        if p.get("http"):
            nodos[kid]["http"] = p["http"]
        por_path[path] = kid
        if c["lenguaje"] == "java":
            por_fqn[f"{p['paquete']}.{p['nombre']}"] = kid
            por_paquete.setdefault((c["id"], p["paquete"]), []).append((p["nombre"], kid))

    # relations by imports / usage
    for c, path, rel, p in componentes:
        kid = por_path[path]
        destino: set[str] = set()
        if c["lenguaje"] == "java":
            for imp in p["imports"]:
                if imp in por_fqn:
                    destino.add(por_fqn[imp])
            for nombre, otro in por_paquete.get((c["id"], p.get("paquete", "")), []):
                if otro != kid and re.search(rf"\b{re.escape(nombre)}\b", p["texto"]):
                    destino.add(otro)
        elif c["lenguaje"] == "js":
            raiz_c = raiz / c["dir"] if c["dir"] else raiz
            for spec in p["imports"]:
                r = resolver_js(path, spec, raiz_c)
                if r and r in por_path:
                    destino.add(por_path[r])
        else:
            raiz_c = raiz / c["dir"] if c["dir"] else raiz
            for mod, nombres in p["imports"]:
                for r in resolver_py(path, mod, nombres, raiz_c):
                    if r in por_path:
                        destino.add(por_path[r])
        for d in sorted(destino):
            agregar_rel(kid, d, "usa", "import")

    # front -> back by HTTP routes
    endpoints = [(kid, e) for kid, n in nodos.items() for e in n.get("endpoints", [])]
    for kid, n in list(nodos.items()):
        for llamada in n.get("http", []):
            sf = segmentos(llamada["ruta"])
            for back_id, ep in endpoints:
                if nodos[back_id]["padre"].split(":")[1] == n["padre"].split(":")[1]:
                    continue  # same container
                metodo_ok = ep["metodo"] in ("ANY", llamada["metodo"])
                if metodo_ok and coincide(sf, segmentos(ep["ruta"])):
                    agregar_rel(kid, back_id, f"HTTP {llamada['metodo']} {ep['ruta']}", "http")

    # repositories / entities -> database
    if db_ids:
        for kid, n in list(nodos.items()):
            if n.get("tipo") in ("repository",) or (n.get("tipo") == "entity" and not any(
                    m.get("tipo") == "repository" for m in nodos.values())):
                for db in db_ids:
                    agregar_rel(kid, db, "SQL", "heuristica-db")

    # dedupe relations
    vistas, rels = set(), []
    for r in relaciones:
        k = (r["de"], r["a"], r["etiqueta"])
        if k not in vistas:
            vistas.add(k)
            rels.append(r)

    # containers with no content (except services)
    usados = {n["padre"] for n in nodos.values() if n["nivel"] == "modulo"}
    for cid in [k for k, n in nodos.items() if n["nivel"] == "contenedor" and k.startswith("c:")
                and not k.startswith("c:svc.") and k not in usados]:
        del nodos[cid]

    return {
        "version": 1,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": raiz.name,
        "nodos": list(nodos.values()),
        "relaciones": [r for r in rels if r["de"] in nodos and r["a"] in nodos],
    }


def solo_por_parametro(front: list[str], back: list[str]) -> bool:
    """The call matches only because a frontend literal falls into a backend parameter."""
    corto, largo = (front, back) if len(front) <= len(back) else (back, front)
    pares = zip(front[len(front) - len(corto):], back[len(back) - len(corto):])
    return any(f != "*" and b == "*" for f, b in pares)


def revisar_http(sk: dict) -> list[str]:
    """Frontend calls with no endpoint (or matching only through a parameter) and endpoints nobody calls."""
    cont = lambda n: n["padre"].split(":")[1]  # noqa: E731
    eps = [(n, e) for n in sk["nodos"] for e in n.get("endpoints", [])]
    con_eps = {cont(n) for n, _ in eps}
    llamadas = [(n, c) for n in sk["nodos"] if n["nivel"] == "componente" and cont(n) not in con_eps for c in n.get("http", [])]
    if not eps or not llamadas:
        return []
    out, usados = [], set()
    for n, c in llamadas:
        sf = segmentos(c["ruta"])
        if not sf or all(s == "*" for s in sf):
            continue  # route assembled at runtime: cannot be judged
        exactos, por_param = [], []
        for bn, e in eps:
            if e["metodo"] in ("ANY", c["metodo"]) and coincide(sf, segmentos(e["ruta"])):
                (por_param if solo_por_parametro(sf, segmentos(e["ruta"])) else exactos).append((bn, e))
        usados |= {(bn["id"], e["metodo"], e["ruta"]) for bn, e in exactos}  # matching through a parameter is not real usage
        donde = f"{n['archivo']}:{c['linea']} {c['metodo']} {c['ruta']}"
        if not exactos and por_param:
            bn, e = por_param[0]
            out.append(f"  call {donde} only matches because a literal falls into a parameter of {e['metodo']} {e['ruta']} "
                       f"({bn['archivo']}:{e['linea']}); the route probably does not exist")
        elif not exactos:
            out.append(f"  call {donde} matches no endpoint")
    for bn, e in eps:
        if (bn["id"], e["metodo"], e["ruta"]) not in usados:
            out.append(f"  endpoint {e['metodo']} {e['ruta']} ({bn['archivo']}:{e['linea']}) is called by no frontend")
    return out


def arbol(sk: dict) -> str:
    hijos: dict[str, list[dict]] = {}
    for n in sk["nodos"]:
        hijos.setdefault(n["padre"], []).append(n)
    lineas = []

    def rec(pid: str, nivel: int):
        for n in sorted(hijos.get(pid, []), key=lambda x: (x["nivel"], x.get("tipo", ""), x["nombre"])):
            extra = ""
            if n.get("endpoints"):
                extra = f"  [{len(n['endpoints'])} endpoints]"
            elif n.get("http"):
                extra = f"  [{len(n['http'])} HTTP calls]"
            lineas.append(f"{'  ' * nivel}{n['id']}  ({n.get('tipo', '')}){extra}")
            rec(n["id"], nivel + 1)

    rec("sistema", 0)
    return "\n".join(lineas)


def diff(viejo: dict, nuevo: dict) -> str:
    a = {n["id"]: n.get("hash") for n in viejo.get("nodos", []) if n["nivel"] == "componente"}
    b = {n["id"]: n.get("hash") for n in nuevo["nodos"] if n["nivel"] == "componente"}
    nuevos = sorted(set(b) - set(a))
    borrados = sorted(set(a) - set(b))
    cambiados = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    if not (nuevos or borrados or cambiados):
        return "No component changes since the last skeleton."
    out = ["CHANGES since the last skeleton (check in atlas.json everything that goes through these files):"]
    for titulo, lista in (("added", nuevos), ("modified", cambiados), ("deleted", borrados)):
        if lista:
            out.append(f"  {titulo} ({len(lista)}):")
            out += [f"    {x}" for x in lista]
    return "\n".join(out)


def inventario(sk: dict) -> str:
    """Endpoint inventory, one line per endpoint grouped by file."""
    lineas = []
    for n in sorted((n for n in sk["nodos"] if n.get("endpoints")), key=lambda x: x.get("archivo", "")):
        lineas.append(f"{n['archivo']}:")
        lineas += [f"  {e['metodo']} {e['ruta']}  (line {e['linea']})" for e in n["endpoints"]]
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("-o", "--out", dest="salida", type=Path, help="default: <repo>/.atlify/skeleton.json")
    ap.add_argument("--routes", action="store_true", help="print only the endpoint inventory, TO REVIEW and CHANGES (no tree)")
    args = ap.parse_args()
    if not args.repo.is_dir():
        sys.exit(f"Directory does not exist: {args.repo}")
    salida = args.salida or args.repo / ".atlify" / "skeleton.json"
    salida.parent.mkdir(parents=True, exist_ok=True)

    sk = extraer(args.repo)
    viejo = json.loads(salida.read_text(encoding="utf-8")) if salida.exists() else None
    salida.write_text(json.dumps(sk, ensure_ascii=False, indent=1), encoding="utf-8")

    niveles = {}
    for n in sk["nodos"]:
        niveles[n["nivel"]] = niveles.get(n["nivel"], 0) + 1
    print(f"Skeleton: {salida}")
    plural = {"contenedor": "containers", "modulo": "modules", "componente": "components"}
    print("Nodes: " + ", ".join(f"{v} {plural.get(k, k)}" for k, v in niveles.items()) + f" | relations: {len(sk['relaciones'])}")
    if args.routes:
        print("\n" + inventario(sk))
    else:
        print("\n" + arbol(sk))
    revisar = revisar_http(sk)
    if revisar:
        print("\nTO REVIEW (flagged by the script; confirm by reading the code before reporting it):")
        print("\n".join(revisar))
    if viejo:
        print("\n" + diff(viejo, sk))


if __name__ == "__main__":
    main()
