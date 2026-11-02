#!/usr/bin/env python3
"""Validates .atlify/atlas.json against the real repo.

Resolves every code reference ("simbolo" or "ancla") to real lines, detects
misspelled keys, broken cross-references and sensitive files, and compares
coverage with the extract.py skeleton when it exists.

Usage:
    python validate.py <repo> [--atlas <repo>/.atlify/atlas.json] [--endpoint "GET /api/x"]

Exits with code 0 when there are no errors. Warnings do not block.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

MAX_BYTES = 300_000
SEVERIDADES = ("alta", "media", "baja")
ORIGENES = ("script", "agente")
SENSIBLES = re.compile(r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_(rsa|ed25519).*|credentials.*\.json)$")

REF = {"archivo", "simbolo", "ancla", "lineas", "desde", "hasta"}
CLAVES = {
    "raiz": {"proyecto", "naciones", "archivos", "endpoints", "tablas", "hallazgos", "llamadas_rotas"},
    "proyecto": {"nombre", "resumen", "porque", "rama", "stack"},
    "nacion": {"id", "nombre", "tipo", "dir", "resumen"},
    "archivo": {"nacion", "capa", "rol"},
    "endpoint": {"metodo", "ruta", "etiqueta", "auth", "resumen", "explicacion", "entrada", "respuestas",
                 "frontend", "tablas", "pasos", "tests"},
    "paso": REF | {"accion", "explicacion", "pregunta", "tabla", "op"},
    "ref": REF,
    "tabla": REF | {"nombre", "modelo", "resumen", "campos"},
    "campo": {"nombre", "tipo", "clave", "ref", "unico", "sensible", "desc"},
    "hallazgo": REF | {"id", "severidad", "origen", "categoria", "titulo", "explicacion", "sugerencia", "endpoint", "tabla"},
    "rota": REF | {"metodo", "ruta", "usadoEn", "coincide_con", "hallazgo"},
}


def dentro_del_repo(raiz: Path, archivo: str) -> Path | None:
    """Real path of the file if it stays inside the repo; None if absolute, uses .. or escapes through a symlink."""
    if not isinstance(archivo, str) or not archivo:
        return None
    rel = Path(archivo)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    try:
        raiz_real = raiz.resolve()
        destino = (raiz_real / rel).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return destino if destino.is_relative_to(raiz_real) else None


class Repo:
    """Reads repo files once and resolves references to lines."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.textos: dict[str, str] = {}
        self.errores: list[str] = []
        self.avisos: list[str] = []

    def texto(self, archivo: str) -> str | None:
        if archivo not in self.textos:
            p = dentro_del_repo(self.raiz, archivo)
            if p is None or not p.is_file() or p.stat().st_size > MAX_BYTES:
                return None
            self.textos[archivo] = p.read_text(encoding="utf-8", errors="replace")
        return self.textos[archivo]

    def resolver(self, ref: dict, ctx: str) -> None:
        archivo = ref.get("archivo")
        if not archivo:
            return
        if not isinstance(archivo, str):
            self.errores.append(f"{ctx}: 'archivo' must be a string")
            return
        if dentro_del_repo(self.raiz, archivo) is None:
            self.errores.append(f"{ctx}: {archivo} is outside the repo")
            return
        if SENSIBLES.search(archivo):
            self.errores.append(f"{ctx}: {archivo} may contain secrets; it cannot be quoted in the atlas")
            return
        txt = self.texto(archivo)
        if txt is None:
            self.errores.append(f"{ctx}: file {archivo} does not exist (or is larger than {MAX_BYTES // 1000} KB)")
            return
        if ref.get("desde"):
            ref.setdefault("hasta", ref["desde"])
            self.avisos.append(f"{ctx}: uses fixed desde/hasta; prefer simbolo or ancla so it does not drift")
            return
        rango = None
        if ref.get("simbolo"):
            if not isinstance(ref["simbolo"], str):
                self.errores.append(f"{ctx}: 'simbolo' must be a string")
                return
            rango = rango_simbolo(txt, archivo, ref["simbolo"])
            if not rango:
                self.errores.append(f"{ctx}: cannot find '{ref['simbolo']}' in {archivo} (was it renamed?)")
        elif ref.get("ancla"):
            if not isinstance(ref["ancla"], str):
                self.errores.append(f"{ctx}: 'ancla' must be a string")
                return
            i = next((n for n, ln in enumerate(txt.splitlines(), 1) if ref["ancla"] in ln), None)
            if i is None:
                self.errores.append(f"{ctx}: cannot find the text '{ref['ancla']}' in {archivo}")
            else:
                try:
                    lineas = int(ref.get("lineas", 0))
                except (TypeError, ValueError):
                    self.errores.append(f"{ctx}: 'lineas' must be a number")
                    return
                rango = (i, i + lineas)
        else:
            self.errores.append(f"{ctx}: missing 'simbolo' or 'ancla' to locate the code in {archivo}")
        if rango:
            ref["desde"], ref["hasta"] = rango


def rango_simbolo(txt: str, archivo: str, nombre: str) -> tuple[int, int] | None:
    """Lines of a function or class: ast in Python, balanced braces elsewhere."""
    if archivo.endswith(".py"):
        try:
            arbol = ast.parse(txt)
        except SyntaxError:
            return None
        for n in ast.walk(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == nombre:
                inicio = min([n.lineno] + [d.lineno for d in n.decorator_list])
                return inicio, n.end_lineno or n.lineno
        return None
    nombre_rx = re.escape(nombre)
    java = (r"(?:@\w+(?:\([^)]*\))?\s+)*"
            r"(?:(?:public|private|protected|static|final|abstract|synchronized|native|default|strictfp)\s+)*"
            r"(?:<[^>{};]+>\s+)?"
            r"[\w$.]+(?:\s*<[^;{}()]*>)?(?:\s*\[\s*\])*\s+"
            rf"{nombre_rx}\s*\([^;]*$")
    m = re.search(rf"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s*\*?\s*{nombre_rx}\b|"
                  rf"class\s+{nombre_rx}\b|(?:const|let|var)\s+{nombre_rx}\s*[=:]|{java})",
                  txt, re.M)
    if not m:
        return None
    inicio = txt.count("\n", 0, m.start()) + 1
    prof, abrio, i, n = 0, False, m.start(), len(txt)
    while i < n:
        c = txt[i]
        if c in "\"'`":
            j = i + 1
            while j < n and txt[j] != c:
                j += 2 if txt[j] == "\\" else 1
            i = j
        elif txt.startswith("//", i):
            i = txt.find("\n", i)
            if i < 0:
                break
            continue
        elif c in "{(":
            prof += 1
            abrio = True
        elif c in "})":
            prof -= 1
            if abrio and prof == 0 and c == "}":
                return inicio, txt.count("\n", 0, i) + 1
        i += 1
    return inicio, inicio


def ep_id(e: dict) -> str:
    return f"{e.get('metodo', '?')} {e.get('ruta', '?')}"


def recorrer_refs(datos: dict):
    """Every code reference in the atlas, with a readable context for messages."""
    for e in datos.get("endpoints", []):
        eid = ep_id(e)
        if e.get("entrada"):
            yield e["entrada"], f"{eid} entrada"
        for j, r in enumerate(e.get("frontend", [])):
            yield r, f"{eid} frontend[{j}]"
        for j, p in enumerate(e.get("pasos", [])):
            yield p, f"{eid} pasos[{j}]"
        for j, t in enumerate(e.get("tests") or []):
            yield t, f"{eid} tests[{j}]"
    for t in datos.get("tablas", []):
        yield t, f"tabla {t.get('nombre')}"
    for h in datos.get("hallazgos", []):
        yield h, f"hallazgo {h.get('id')}"
    for r in datos.get("llamadas_rotas", []):
        yield r, f"llamada rota {r.get('ruta')}"
        for j, u in enumerate(r.get("usadoEn", [])):
            yield u, f"llamada rota {r.get('ruta')} usadoEn[{j}]"


def lista_de_objetos(valor) -> bool:
    return isinstance(valor, list) and all(isinstance(x, dict) for x in valor)


def normalizar_forma(datos: dict, errores: list[str]) -> None:
    """Leaves the collections traversable; one that is not a list of objects is emptied and reported."""
    if not isinstance(datos.get("proyecto", {}), dict):
        errores.append("proyecto: expected an object")
        datos["proyecto"] = {}
    if not isinstance(datos.get("archivos", {}), dict):
        errores.append("archivos: expected an object (path -> {nacion, capa, rol})")
        datos["archivos"] = {}
    for k, v in list(datos.get("archivos", {}).items()):
        if not isinstance(v, dict):
            errores.append(f"archivos[{k}]: expected an object")
            datos["archivos"][k] = {}
    for clave in ("naciones", "endpoints", "tablas", "hallazgos", "llamadas_rotas"):
        if not lista_de_objetos(datos.get(clave, [])):
            errores.append(f"{clave}: expected a list of objects")
            datos[clave] = []
    for e in datos.get("endpoints", []):
        eid = ep_id(e)
        for clave in ("pasos", "frontend", "tests", "tablas"):
            if clave in e and not lista_de_objetos(e[clave]):
                errores.append(f"{eid}: '{clave}' must be a list of objects")
                e[clave] = []
        if e.get("entrada") is not None and not isinstance(e["entrada"], dict):
            errores.append(f"{eid}: 'entrada' must be an object")
            e.pop("entrada", None)
    for t in datos.get("tablas", []):
        if "campos" in t and not lista_de_objetos(t["campos"]):
            errores.append(f"tabla {t.get('nombre')}: 'campos' must be a list of objects")
            t["campos"] = []
    for r in datos.get("llamadas_rotas", []):
        if "usadoEn" in r and not lista_de_objetos(r["usadoEn"]):
            errores.append(f"llamada rota {r.get('ruta')}: 'usadoEn' must be a list of objects")
            r["usadoEn"] = []


def revisar_claves(datos: dict, errores: list[str]) -> None:
    def chk(obj, tipo, ctx):
        if not isinstance(obj, dict):
            errores.append(f"{ctx}: expected an object")
            return
        sobran = set(obj) - CLAVES[tipo]
        if sobran:
            errores.append(f"{ctx}: unknown keys {sorted(sobran)} (allowed: {sorted(CLAVES[tipo])})")

    chk(datos, "raiz", "atlas.json")
    chk(datos.get("proyecto", {}), "proyecto", "proyecto")
    for n in datos.get("naciones", []):
        chk(n, "nacion", f"nacion {n.get('id')}")
    for k, v in datos.get("archivos", {}).items():
        chk(v, "archivo", f"archivos[{k}]")
    for e in datos.get("endpoints", []):
        chk(e, "endpoint", ep_id(e))
        for p in e.get("pasos", []):
            chk(p, "paso", f"{ep_id(e)} paso")
        for r in e.get("frontend", []) + ([e["entrada"]] if e.get("entrada") else []) + (e.get("tests") or []):
            chk(r, "ref", f"{ep_id(e)} referencia")
    for t in datos.get("tablas", []):
        chk(t, "tabla", f"tabla {t.get('nombre')}")
        for c in t.get("campos", []):
            chk(c, "campo", f"tabla {t.get('nombre')} campo {c.get('nombre')}")
    for h in datos.get("hallazgos", []):
        chk(h, "hallazgo", f"hallazgo {h.get('id')}")
    for r in datos.get("llamadas_rotas", []):
        chk(r, "rota", f"llamada rota {r.get('ruta')}")


def revisar_contenido(datos: dict, repo: Repo, solo_endpoint: str | None) -> None:
    err = repo.errores
    eps = {ep_id(e): e for e in datos.get("endpoints", [])}
    tablas = {t.get("nombre") for t in datos.get("tablas", [])}
    hall_ids = [h.get("id") for h in datos.get("hallazgos", [])]
    naciones = {n.get("id") for n in datos.get("naciones", [])} | {"infra"}

    if not datos.get("proyecto", {}).get("nombre"):
        err.append("proyecto.nombre is required")
    for k, v in datos.get("archivos", {}).items():
        if v.get("nacion") not in naciones:
            err.append(f"archivos[{k}]: unknown nacion {v.get('nacion')!r}")
    for eid, e in eps.items():
        if not e.get("resumen"):
            err.append(f"{eid}: missing resumen")
        if not any(p.get("archivo") for p in e.get("pasos", [])):
            err.append(f"{eid}: the walkthrough has no step with code")
        if "tablas" not in e:
            err.append(f"{eid}: missing 'tablas' (use [] if the endpoint never touches the database)")
        for t in e.get("tablas", []):
            if t.get("tabla") not in tablas:
                err.append(f"{eid}: nonexistent tabla {t.get('tabla')}")
        for p in e.get("pasos", []):
            if p.get("tabla") and p["tabla"] not in tablas:
                err.append(f"{eid}: step with nonexistent tabla {p['tabla']}")
            if not p.get("accion"):
                err.append(f"{eid}: a step is missing 'accion'")
    for h in datos.get("hallazgos", []):
        hid = h.get("id")
        if hall_ids.count(hid) > 1:
            err.append(f"hallazgo {hid}: duplicate id")
        if h.get("severidad") not in SEVERIDADES:
            err.append(f"hallazgo {hid}: severidad must be one of {SEVERIDADES}")
        if h.get("origen") not in ORIGENES:
            err.append(f"hallazgo {hid}: origen must be one of {ORIGENES}")
        for k in ("titulo", "explicacion", "sugerencia", "archivo"):
            if not h.get(k):
                err.append(f"hallazgo {hid}: missing '{k}'")
        if h.get("endpoint") and h["endpoint"] not in eps and not solo_endpoint:
            err.append(f"hallazgo {hid}: nonexistent endpoint {h['endpoint']}")
        if h.get("tabla") and h["tabla"] not in tablas:
            err.append(f"hallazgo {hid}: nonexistent tabla {h['tabla']}")
    for r in datos.get("llamadas_rotas", []):
        if r.get("hallazgo") and r["hallazgo"] not in hall_ids:
            err.append(f"llamada rota {r.get('ruta')}: nonexistent hallazgo {r['hallazgo']}")
    for archivo in datos.get("archivos", {}):
        if dentro_del_repo(repo.raiz, archivo) is None:
            err.append(f"archivos: {archivo} is outside the repo")
        elif repo.texto(archivo) is None:
            err.append(f"archivos: {archivo} does not exist")


def segmentos(ruta: str) -> list[str]:
    ruta = re.sub(r"^https?://[^/]+", "", ruta).split("?")[0]
    return ["*" if re.fullmatch(r"\{[^}]*\}|:\w+|\$\{[^}]*\}|\d+", s) else s.lower() for s in ruta.strip("/").split("/") if s]


def mismo_endpoint(a: str, b: str) -> bool:
    """Compares 'GET /api/x/{id}' with 'GET /x/{id}': same method and the shorter route is a suffix of the other."""
    (ma, ra), (mb, rb) = a.split(" ", 1), b.split(" ", 1)
    sa, sb = segmentos(ra), segmentos(rb)
    corto, largo = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return ma == mb and bool(corto) and largo[len(largo) - len(corto):] == corto


def cobertura(datos: dict, esqueleto: Path, avisos: list[str]) -> None:
    if not esqueleto.exists():
        avisos.append(f"There is no {esqueleto.name}: cannot compare coverage (run atlify.py extract)")
        return
    try:
        sk = json.loads(esqueleto.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        avisos.append(f"Could not read {esqueleto.name}: run atlify.py extract again")
        return
    nodos = sk.get("nodos", []) if isinstance(sk, dict) else []
    del_sk = sorted({f"{e.get('metodo')} {e.get('ruta')}" for n in nodos if isinstance(n, dict)
                     for e in n.get("endpoints", []) if isinstance(e, dict)})
    hechos = [ep_id(e) for e in datos.get("endpoints", [])]
    faltan = [x for x in del_sk if not any(mismo_endpoint(x, h) for h in hechos)]
    if faltan:
        avisos.append(f"{len(faltan)} of {len(del_sk)} skeleton endpoints are missing from atlas.json: " + ", ".join(faltan[:12])
                      + (" …" if len(faltan) > 12 else ""))


def validar(repo_dir: Path, atlas: Path, solo_endpoint: str | None = None) -> tuple[dict | None, Repo, str | None]:
    """Validates and returns (datos, repo, resolved endpoint). The --endpoint
    argument may use the skeleton's form (without the /api prefix): it is
    resolved by suffix, like everywhere else routes are compared."""
    repo = Repo(repo_dir.resolve())
    if not atlas.exists():
        repo.errores.append(f"There is no {atlas}: write it following references/conventions.md")
        return None, repo, solo_endpoint
    try:
        datos = json.loads(atlas.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        repo.errores.append(f"{atlas}: invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}")
        return None, repo, solo_endpoint
    if not isinstance(datos, dict):
        repo.errores.append("atlas.json: the root must be an object")
        return None, repo, solo_endpoint
    normalizar_forma(datos, repo.errores)
    revisar_claves(datos, repo.errores)
    for ref, ctx in recorrer_refs(datos):
        repo.resolver(ref, ctx)
    if solo_endpoint:
        eps_ids = {ep_id(e) for e in datos.get("endpoints", [])}
        if solo_endpoint not in eps_ids:
            parecidos = sorted(k for k in eps_ids if mismo_endpoint(k, solo_endpoint))
            if len(parecidos) == 1:
                solo_endpoint = parecidos[0]
            elif parecidos:
                repo.errores.append(f"--endpoint '{solo_endpoint}' is ambiguous; candidates: {', '.join(parecidos)}")
            else:
                repo.errores.append(f"--endpoint '{solo_endpoint}' is not in atlas.json")
    revisar_contenido(datos, repo, solo_endpoint)
    if not solo_endpoint:
        cobertura(datos, atlas.parent / "skeleton.json", repo.avisos)
    return datos, repo, solo_endpoint


def informar(repo: Repo) -> None:
    for titulo, lista in (("ERRORS", repo.errores), ("WARNINGS", repo.avisos)):
        if lista:
            print(f"{titulo} ({len(lista)}):")
            for x in lista:
                print(f"  - {x}")
    print(f"{'OK' if not repo.errores else 'FAIL'}: {len(repo.errores)} errors, {len(repo.avisos)} warnings")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--atlas", type=Path, help="default: <repo>/.atlify/atlas.json")
    ap.add_argument("--endpoint", help='validates single-endpoint mode, e.g. "GET /api/x"; matched by suffix')
    args = ap.parse_args()
    _, repo, _ = validar(args.repo, args.atlas or args.repo / ".atlify" / "atlas.json", args.endpoint)
    informar(repo)
    sys.exit(1 if repo.errores else 0)


if __name__ == "__main__":
    main()
