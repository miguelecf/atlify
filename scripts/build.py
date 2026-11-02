#!/usr/bin/env python3
"""Generates the atlas viewer: a single offline HTML from atlas.json and the repo.

It validates first (validate.py), embeds the quoted source files compressed
into the HTML, and writes it to .atlify/. With --endpoint it keeps only that
route and computes, over the real code, which other routes and tests pass
through the same functions and tables.

Usage:
    python build.py <repo> [--atlas <repo>/.atlify/atlas.json] [-o output.html]
    python build.py <repo> --endpoint "GET /api/appointments"
"""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import json
import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import caminar, es_test  # noqa: E402  # pyright: ignore[reportMissingImports]
from validate import (dentro_del_repo, ep_id, informar, mismo_endpoint, rango_simbolo,  # noqa: E402  # pyright: ignore[reportMissingImports]
                      recorrer_refs, validar)

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PLANTILLA = ASSETS / "visor.html"
VENDOR = ASSETS / "vendor" / "htm-preact-3.1.1.umd.js"
FUENTES = (("Archivo", "archivo-latin-var.woff2", "100 900", "swap"),
           ("Archivo Black", "archivo-black-latin.woff2", "400", ""))
EXT_CODIGO = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".java"}
# Java method declarations: optional modifiers and return type, name and parens
RE_METODO_JAVA = re.compile(
    r"^[ \t]*(?!(?:if|for|while|switch|catch|new|return|else|do|try|throw|assert)\b)"
    r"(?:@\w+(?:\([^)]*\))?\s+)*"
    r"(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp)\s+)*"
    r"(?:<[^>{};]+>\s+)?"
    r"[\w$.]+(?:\s*<[^;{}()]*>)?(?:\s*\[\s*\])*\s+(\w+)\s*\([^;{}]*\)\s*"
    r"(?:throws\s+[\w.,\s<>]+)?\{", re.M)
# names too common to search without the module in front (db.get, list.add...)
GENERICOS = {"get", "add", "set", "put", "post", "list", "create", "update", "delete", "remove", "save", "find",
             "run", "main", "init", "load", "fetch", "render", "handle", "query", "send", "close", "open"}
PROFUNDIDAD = 4


class Indice:
    """Usages of functions and classes across the repo, with the function containing each usage."""

    def __init__(self, raiz: Path):
        raiz = raiz.resolve()
        self.raiz = raiz
        self.textos: dict[str, list[str]] = {}
        for f in caminar(raiz):
            if f.suffix in EXT_CODIGO and f.stat().st_size < 300_000:
                rel = f.relative_to(raiz).as_posix()
                if dentro_del_repo(raiz, rel) is None:
                    continue
                self.textos[rel] = f.read_text(encoding="utf-8", errors="replace").splitlines()
        self._funcs: dict[str, list[tuple[str, int, int]]] = {}

    def funciones(self, archivo: str) -> list[tuple[str, int, int]]:
        if archivo not in self._funcs:
            lineas = self.textos.get(archivo, [])
            txt = "\n".join(lineas)
            res = []
            if archivo.endswith(".py"):
                try:
                    for n in ast.walk(ast.parse(txt)):
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            res.append((n.name, n.lineno, n.end_lineno or n.lineno))
                except SyntaxError:
                    pass
            elif archivo.endswith(".java"):
                for m in RE_METODO_JAVA.finditer(txt):
                    nombre = m.group(1)
                    r = rango_simbolo(txt, archivo, nombre)
                    if r:
                        res.append((nombre, *r))
            else:
                for m in re.finditer(r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s*\*?\s*(\w+)|"
                                     r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>)", txt, re.M):
                    nombre = m.group(1) or m.group(2)
                    r = rango_simbolo(txt, archivo, nombre)
                    if r:
                        res.append((nombre, *r))
            self._funcs[archivo] = res
        return self._funcs[archivo]

    def encierra(self, archivo: str, linea: int) -> tuple[str, int, int] | None:
        dentro = [f for f in self.funciones(archivo) if f[1] <= linea <= f[2]]
        return min(dentro, key=lambda f: f[2] - f[1]) if dentro else None

    def usos(self, archivo: str, simbolo: str, desde: int, hasta: int, llamada: bool = True) -> list[dict]:
        cola = r"\s*\(" if llamada else r"\b"
        patrones = [rf"\b{re.escape(Path(archivo).stem)}\.{re.escape(simbolo)}{cola}"]
        # a class (Pet) is unambiguous even when short; a short function only with the module in front
        if simbolo[:1].isupper() or (simbolo not in GENERICOS and len(simbolo) >= 4):
            patrones.append(rf"(?<![\w.]){re.escape(simbolo)}{cola}")
        if archivo.endswith(".java") and simbolo not in GENERICOS and len(simbolo) >= 3:
            # in Java it is called through the injected variable: petService.buscar(id)
            patrones.append(rf"\.{re.escape(simbolo)}\s*\(")
        rx = re.compile("|".join(patrones))
        out = []
        for rel, lineas in self.textos.items():
            for i, ln in enumerate(lineas, 1):
                if rel == archivo and desde <= i <= hasta:
                    continue
                if re.match(r"\s*(from\s+\S+\s+)?import\b", ln) or not rx.search(ln):
                    continue
                f = self.encierra(rel, i)
                out.append({"archivo": rel, "linea": i, "funcion": f[0] if f else None,
                            "rango": (f[1], f[2]) if f else None, "test": es_test(rel)})
        return out


def manejadores(datos: dict, esqueleto: Path) -> dict[tuple[str, str], str]:
    """(file, function) -> endpoint, from the skeleton and from the atlas steps."""
    res: dict[tuple[str, str], str] = {}
    if esqueleto.exists():
        sk = json.loads(esqueleto.read_text(encoding="utf-8"))
        for n in sk.get("nodos", []):
            metodos = sorted(n.get("metodos", []), key=lambda m: m["linea"])
            for e in n.get("endpoints", []):
                m = next((m for m in metodos if m["linea"] >= e["linea"]), None)
                if m:
                    res[(n["archivo"], m["nombre"])] = f"{e['metodo']} {e['ruta']}"
    capas = datos.get("archivos", {})
    for e in datos.get("endpoints", []):
        for p in e.get("pasos", []):
            if p.get("simbolo") and capas.get(p.get("archivo"), {}).get("capa") == "router":
                res[(p["archivo"], p["simbolo"])] = ep_id(e)
    return res


def afectados(idx: Indice, mans: dict, archivo: str, simbolo: str, desde: int, hasta: int, llamada: bool = True):
    """Direct usages and endpoints reached by climbing callers, up to PROFUNDIDAD levels."""
    directos = idx.usos(archivo, simbolo, desde, hasta, llamada)
    endpoints, tests, vistos = set(), set(), set()
    cola = [(u, 1) for u in directos]
    if (archivo, simbolo) in mans:
        endpoints.add(mans[(archivo, simbolo)])
    while cola:
        u, prof = cola.pop()
        if u["test"]:
            tests.add((u["archivo"], u["funcion"] or ""))
            continue
        if not u["funcion"] or (u["archivo"], u["funcion"]) in vistos:
            continue
        vistos.add((u["archivo"], u["funcion"]))
        if (u["archivo"], u["funcion"]) in mans:
            endpoints.add(mans[(u["archivo"], u["funcion"])])
        elif prof < PROFUNDIDAD:
            cola += [(x, prof + 1) for x in idx.usos(u["archivo"], u["funcion"], *u["rango"])]
    return directos, endpoints, tests


def enfocar(datos: dict, eid: str, repo_dir: Path, esqueleto: Path) -> dict:
    """Keeps only one endpoint and adds the blast radius computed over the real code."""
    eps = {ep_id(e): e for e in datos.get("endpoints", [])}
    e = eps[eid]
    idx = Indice(repo_dir)
    mans = manejadores(datos, esqueleto)
    otro = lambda x: not mismo_endpoint(x, eid)  # noqa: E731
    # atlas names when they exist (full routes), otherwise the skeleton's
    nombre = lambda x: next((k for k in eps if mismo_endpoint(k, x)), x)  # noqa: E731

    impacto, tests = [], set()
    for p in e.get("pasos", []) + e.get("frontend", []):
        if not (p.get("archivo") and p.get("simbolo")) or any(i["simbolo"] == p["simbolo"] and i["archivo"] == p["archivo"] for i in impacto):
            continue
        directos, alcanzados, ts = afectados(idx, mans, p["archivo"], p["simbolo"], p["desde"], p["hasta"])
        tests |= ts
        impacto.append({"archivo": p["archivo"], "simbolo": p["simbolo"], "desde": p["desde"], "hasta": p["hasta"],
                        "usos": [{"archivo": u["archivo"], "linea": u["linea"], "funcion": u["funcion"]} for u in directos if not u["test"]][:20],
                        "endpoints": sorted({nombre(x) for x in alcanzados if otro(x)})})

    tablas_e = {t["tabla"] for t in e.get("tablas", [])}
    tablas_d = [t for t in datos.get("tablas", []) if t["nombre"] in tablas_e]
    tablas_comp = []
    for t in tablas_d:
        por_atlas = {ep_id(o): sorted({x["op"] for x in o.get("tablas", []) if x["tabla"] == t["nombre"]})
                     for o in eps.values() if o is not e and any(x["tabla"] == t["nombre"] for x in o.get("tablas", []))}
        if t.get("archivo") and (t.get("modelo") or t.get("simbolo")) and t.get("desde"):
            _, alcanzados, _ = afectados(idx, mans, t["archivo"], t.get("modelo") or t["simbolo"], t["desde"], t["hasta"], llamada=False)
            for x in alcanzados:
                if otro(x):
                    por_atlas.setdefault(nombre(x), [])
        tablas_comp.append({"tabla": t["nombre"], "endpoints": [{"id": k, "ops": v} for k, v in sorted(por_atlas.items())]})

    # tests: those calling the chain, plus those requesting the route over HTTP
    ruta = re.sub(r"\{[^}]*\}", "", e["ruta"]).rstrip("/")
    for rel, lineas in idx.textos.items():
        if es_test(rel):
            for i, ln in enumerate(lineas, 1):
                if ruta and ruta in ln:
                    f = idx.encierra(rel, i)
                    tests.add((rel, f[0] if f else ""))
    if not e.get("tests"):  # an empty list also means "not written": build discovers them
        e["tests"] = [{"archivo": a, "simbolo": f} for a, f in sorted(tests) if f]
        for t in e["tests"]:
            t["desde"], t["hasta"] = rango_simbolo("\n".join(idx.textos[t["archivo"]]), t["archivo"], t["simbolo"]) or (1, 1)

    refs = e.get("frontend", []) + e.get("pasos", []) + ([e["entrada"]] if e.get("entrada") else []) + e["tests"]
    rangos = [(r["archivo"], r["desde"], r["hasta"]) for r in refs if r.get("archivo") and r.get("desde")]
    hallazgos = [h for h in datos.get("hallazgos", []) if h.get("endpoint") == eid or any(
        h["archivo"] == a and h["desde"] <= hasta and h["hasta"] >= desde for a, desde, hasta in rangos)]
    usados = {a for a, _, _ in rangos} | {t["archivo"] for t in tablas_d if t.get("archivo")} | {h["archivo"] for h in hallazgos}
    return {
        **{k: datos[k] for k in ("proyecto", "naciones") if k in datos},
        "archivos": {k: v for k, v in datos.get("archivos", {}).items() if k in usados},
        "endpoints": [e],
        "tablas": tablas_d,
        "hallazgos": hallazgos,
        "llamadas_rotas": [r for r in datos.get("llamadas_rotas", []) if r.get("coincide_con") == eid],
        "foco": {"endpoint": eid, "impacto": impacto, "tablas": tablas_comp,
                 "total_endpoints": len(eps), "total_archivos": len(datos.get("archivos", {}))},
    }


def slug(eid: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", eid.lower()).strip("-")


def css_fuentes() -> str:
    """@font-face with vendored fonts in base64, so the HTML works offline."""
    bloques = []
    for familia, archivo, peso, display in FUENTES:
        p = ASSETS / "vendor" / "fonts" / archivo
        if not p.is_file():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        extra = f";font-display:{display}" if display else ""
        bloques.append(f"@font-face{{font-family:'{familia}';font-weight:{peso};font-style:normal{extra};"
                       f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "\n".join(bloques)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--atlas", type=Path, help="default: <repo>/.atlify/atlas.json")
    ap.add_argument("--skeleton", dest="esqueleto", type=Path, help="default: skeleton.json next to atlas.json")
    ap.add_argument("--endpoint", help='generate only that route, e.g. "POST /api/appointments"; matched by suffix')
    ap.add_argument("-o", "--out", dest="salida", type=Path)
    args = ap.parse_args()

    atlas = args.atlas or args.repo / ".atlify" / "atlas.json"
    datos, repo, eid = validar(args.repo, atlas, args.endpoint)
    if repo.errores or datos is None:
        informar(repo)
        sys.exit("The viewer is not generated until validate.py reports 0 errors.")
    if repo.avisos:
        print(f"{len(repo.avisos)} validation warnings (run atlify.py validate to see them).")

    if args.endpoint:
        datos = enfocar(datos, eid, repo.raiz, args.esqueleto or atlas.parent / "skeleton.json")
    usados = set(datos.get("archivos", {})) | {r["archivo"] for r, _ in recorrer_refs(datos) if r.get("archivo")}
    fuentes = {k: repo.texto(k) for k in sorted(usados) if repo.texto(k) is not None}

    crudo = json.dumps(fuentes, ensure_ascii=False).encode("utf-8")
    # No wall-clock timestamp in the payload: identical input produces identical HTML.
    datos["fuentesGz"] = base64.b64encode(gzip.compress(crudo, 9, mtime=0)).decode("ascii")
    payload = json.dumps(datos, ensure_ascii=False).replace("<", "\\u003c")

    vendor = VENDOR.read_text(encoding="utf-8")
    if "</script" in vendor.lower():
        sys.exit(f"{VENDOR} contains </script and would break the HTML")
    html = PLANTILLA.read_text(encoding="utf-8")
    for marca in ("/*__VENDOR__*/", "__ATLAS_DATOS__", "<title>Atlas del código</title>"):
        if html.count(marca) != 1:
            sys.exit(f"The template {PLANTILLA} must contain exactly once: {marca}")
    nombre = datos.get("proyecto", {}).get("nombre") or repo.raiz.name
    titulo = f"Atlify · {nombre}" + (f" · {eid}" if args.endpoint else "")
    html = (html.replace("/*__VENDOR__*/", vendor).replace("__ATLAS_DATOS__", payload)
            .replace("/*__FONTS__*/", css_fuentes())
            .replace("<title>Atlas del código</title>", f"<title>{escape(titulo)}</title>"))

    salida = args.salida or atlas.parent / (f"atlas-{slug(eid)}.html" if args.endpoint else "atlas.html")
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    print(f"Atlify: {salida}  ({salida.stat().st_size // 1024} KB, {len(fuentes)} source files)")
    if args.endpoint:
        f = datos["foco"]
        compartidas = [i for i in f["impacto"] if i["endpoints"]]
        print(f"Focus {eid}: {len(f['impacto'])} functions in the chain, {len(compartidas)} shared with other routes, "
              f"{len(datos['endpoints'][0]['tests'])} tests, {len(datos['hallazgos'])} findings on the path.")
        for i in compartidas:
            print(f"  {i['simbolo']}() is also reached by: {', '.join(i['endpoints'])}")


if __name__ == "__main__":
    main()
