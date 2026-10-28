#!/usr/bin/env python3
"""Genera el visor del atlas: un único HTML offline a partir de atlas.json y del repo.

Valida primero (validate.py), comprime los archivos fuente citados dentro del
HTML y lo escribe en .atlas/. Con --endpoint deja solo esa ruta y calcula, sobre
el código real, qué otras rutas y tests pasan por las mismas funciones y tablas.

Uso:
    python build.py <repo> [--atlas <repo>/.atlas/atlas.json] [-o salida.html]
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
from validate import ep_id, informar, mismo_endpoint, rango_simbolo, recorrer_refs, validar  # noqa: E402  # pyright: ignore[reportMissingImports]

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PLANTILLA = ASSETS / "visor.html"
VENDOR = ASSETS / "vendor" / "htm-preact-3.1.1.umd.js"
EXT_CODIGO = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".java"}
# nombres demasiado comunes para buscarlos sin el módulo delante (db.get, list.add…)
GENERICOS = {"get", "add", "set", "put", "post", "list", "create", "update", "delete", "remove", "save", "find",
             "run", "main", "init", "load", "fetch", "render", "handle", "query", "send", "close", "open"}
PROFUNDIDAD = 4


class Indice:
    """Usos de funciones y clases en todo el repo, con la función que contiene cada uso."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.textos: dict[str, list[str]] = {}
        for f in caminar(raiz):
            if f.suffix in EXT_CODIGO and f.stat().st_size < 300_000:
                rel = f.relative_to(raiz).as_posix()
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
        # una clase (Pet) es inconfundible aunque sea corta; una función corta solo con el módulo delante
        if simbolo[:1].isupper() or (simbolo not in GENERICOS and len(simbolo) >= 4):
            patrones.append(rf"(?<![\w.]){re.escape(simbolo)}{cola}")
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
    """(archivo, función) → endpoint, según el esqueleto y según los pasos del atlas."""
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
    """Usos directos y endpoints alcanzados subiendo por quien llama, hasta PROFUNDIDAD niveles."""
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
    """Deja solo un endpoint y agrega el impacto calculado sobre el código real."""
    eps = {ep_id(e): e for e in datos.get("endpoints", [])}
    e = eps[eid]
    idx = Indice(repo_dir)
    mans = manejadores(datos, esqueleto)
    otro = lambda x: not mismo_endpoint(x, eid)  # noqa: E731
    # nombres del atlas cuando existen (rutas completas), si no los del esqueleto
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
        _, alcanzados, _ = afectados(idx, mans, t["archivo"], t.get("modelo") or t["simbolo"], t["desde"], t["hasta"], llamada=False)
        for x in alcanzados:
            if otro(x):
                por_atlas.setdefault(nombre(x), [])
        tablas_comp.append({"tabla": t["nombre"], "endpoints": [{"id": k, "ops": v} for k, v in sorted(por_atlas.items())]})

    # tests: los que llaman a la cadena, más los que piden la ruta por HTTP
    ruta = re.sub(r"\{[^}]*\}", "", e["ruta"]).rstrip("/")
    for rel, lineas in idx.textos.items():
        if es_test(rel):
            for i, ln in enumerate(lineas, 1):
                if ruta and ruta in ln:
                    f = idx.encierra(rel, i)
                    tests.add((rel, f[0] if f else ""))
    if e.get("tests") is None:
        e["tests"] = [{"archivo": a, "simbolo": f} for a, f in sorted(tests) if f]
        for t in e["tests"]:
            t["desde"], t["hasta"] = rango_simbolo("\n".join(idx.textos[t["archivo"]]), t["archivo"], t["simbolo"]) or (1, 1)

    refs = e.get("frontend", []) + e.get("pasos", []) + ([e["entrada"]] if e.get("entrada") else []) + e["tests"]
    rangos = [(r["archivo"], r["desde"], r["hasta"]) for r in refs if r.get("archivo") and r.get("desde")]
    hallazgos = [h for h in datos.get("hallazgos", []) if h.get("endpoint") == eid or any(
        h["archivo"] == a and h["desde"] <= hasta and h["hasta"] >= desde for a, desde, hasta in rangos)]
    usados = {a for a, _, _ in rangos} | {t["archivo"] for t in tablas_d} | {h["archivo"] for h in hallazgos}
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--atlas", type=Path, help="default: <repo>/.atlas/atlas.json")
    ap.add_argument("--esqueleto", type=Path, help="default: skeleton.json junto a atlas.json")
    ap.add_argument("--endpoint", help='genera solo esa ruta, p. ej. "POST /api/appointments"')
    ap.add_argument("-o", "--salida", type=Path)
    args = ap.parse_args()

    atlas = args.atlas or args.repo / ".atlas" / "atlas.json"
    datos, repo = validar(args.repo, atlas, args.endpoint)
    if repo.errores or datos is None:
        informar(repo)
        sys.exit("No genero el visor hasta que validate.py dé 0 errores.")
    if repo.avisos:
        print(f"{len(repo.avisos)} avisos de validación (corré validate.py para verlos).")

    if args.endpoint:
        datos = enfocar(datos, args.endpoint, repo.raiz, args.esqueleto or atlas.parent / "skeleton.json")
    usados = set(datos.get("archivos", {})) | {r["archivo"] for r, _ in recorrer_refs(datos) if r.get("archivo")}
    fuentes = {k: repo.texto(k) for k in sorted(usados) if repo.texto(k) is not None}

    crudo = json.dumps(fuentes, ensure_ascii=False).encode("utf-8")
    datos["fuentesGz"] = base64.b64encode(gzip.compress(crudo, 9)).decode("ascii")
    payload = json.dumps(datos, ensure_ascii=False).replace("<", "\\u003c")

    vendor = VENDOR.read_text(encoding="utf-8")
    if "</script" in vendor.lower():
        sys.exit(f"{VENDOR} contiene </script y rompería el HTML")
    html = PLANTILLA.read_text(encoding="utf-8")
    for marca in ("/*__VENDOR__*/", "__ATLAS_DATOS__", "<title>Atlas del código</title>"):
        if html.count(marca) != 1:
            sys.exit(f"La plantilla {PLANTILLA} debe tener exactamente una vez: {marca}")
    nombre = datos.get("proyecto", {}).get("nombre") or repo.raiz.name
    titulo = f"Atlas {nombre}" + (f" {args.endpoint}" if args.endpoint else "")
    html = (html.replace("/*__VENDOR__*/", vendor).replace("__ATLAS_DATOS__", payload)
            .replace("<title>Atlas del código</title>", f"<title>{escape(titulo)}</title>"))

    salida = args.salida or atlas.parent / (f"atlas-{slug(args.endpoint)}.html" if args.endpoint else "atlas.html")
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html, encoding="utf-8")
    print(f"Atlas: {salida}  ({salida.stat().st_size // 1024} KB, {len(fuentes)} archivos fuente)")
    if args.endpoint:
        f = datos["foco"]
        compartidas = [i for i in f["impacto"] if i["endpoints"]]
        print(f"Foco {args.endpoint}: {len(f['impacto'])} funciones en la cadena, {len(compartidas)} compartidas con otras rutas, "
              f"{len(datos['endpoints'][0]['tests'])} tests, {len(datos['hallazgos'])} hallazgos en el camino.")
        for i in compartidas:
            print(f"  {i['simbolo']}() también la alcanzan: {', '.join(i['endpoints'])}")


if __name__ == "__main__":
    main()
