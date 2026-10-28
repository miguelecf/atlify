#!/usr/bin/env python3
"""Valida .atlas/atlas.json contra el repo real.

Resuelve cada referencia a código ("simbolo" o "ancla") a líneas reales,
detecta claves mal escritas, referencias cruzadas rotas y archivos sensibles,
y compara la cobertura con el esqueleto de extract.py si existe.

Uso:
    python validate.py <repo> [--atlas <repo>/.atlas/atlas.json] [--endpoint "GET /api/x"]

Sale con código 0 si no hay errores. Los avisos no bloquean.
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


class Repo:
    """Lee archivos del repo una sola vez y resuelve referencias a líneas."""

    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.textos: dict[str, str] = {}
        self.errores: list[str] = []
        self.avisos: list[str] = []

    def texto(self, archivo: str) -> str | None:
        if archivo not in self.textos:
            p = self.raiz / archivo
            if not p.is_file() or p.stat().st_size > MAX_BYTES:
                return None
            self.textos[archivo] = p.read_text(encoding="utf-8", errors="replace")
        return self.textos[archivo]

    def resolver(self, ref: dict, ctx: str) -> None:
        archivo = ref.get("archivo")
        if not archivo:
            return
        if SENSIBLES.search(archivo):
            self.errores.append(f"{ctx}: {archivo} parece contener secretos; no se puede citar en el atlas")
            return
        txt = self.texto(archivo)
        if txt is None:
            self.errores.append(f"{ctx}: no existe el archivo {archivo} (o pesa más de {MAX_BYTES // 1000} KB)")
            return
        if ref.get("desde"):
            ref.setdefault("hasta", ref["desde"])
            self.avisos.append(f"{ctx}: usa desde/hasta fijos; preferí simbolo o ancla para que no se desfase")
            return
        rango = None
        if ref.get("simbolo"):
            rango = rango_simbolo(txt, archivo, ref["simbolo"])
            if not rango:
                self.errores.append(f"{ctx}: no encuentro '{ref['simbolo']}' en {archivo} (¿se renombró?)")
        elif ref.get("ancla"):
            i = next((n for n, ln in enumerate(txt.splitlines(), 1) if ref["ancla"] in ln), None)
            if i is None:
                self.errores.append(f"{ctx}: no encuentro el texto '{ref['ancla']}' en {archivo}")
            else:
                rango = (i, i + int(ref.get("lineas", 0)))
        else:
            self.errores.append(f"{ctx}: falta 'simbolo' o 'ancla' para ubicar el código en {archivo}")
        if rango:
            ref["desde"], ref["hasta"] = rango


def rango_simbolo(txt: str, archivo: str, nombre: str) -> tuple[int, int] | None:
    """Líneas de una función o clase: ast en Python, llaves balanceadas en el resto."""
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
    m = re.search(rf"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\s*\*?\s*{re.escape(nombre)}\b|"
                  rf"class\s+{re.escape(nombre)}\b|(?:const|let|var)\s+{re.escape(nombre)}\s*[=:]|"
                  rf"(?:(?:public|private|protected|static|final|async)\s+)*[\w<>\[\],.? ]+\s+{re.escape(nombre)}\s*\([^;]*$)",
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
    """Todas las referencias a código del atlas, con un contexto legible para los mensajes."""
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


def revisar_claves(datos: dict, errores: list[str]) -> None:
    def chk(obj, tipo, ctx):
        if not isinstance(obj, dict):
            errores.append(f"{ctx}: se esperaba un objeto")
            return
        sobran = set(obj) - CLAVES[tipo]
        if sobran:
            errores.append(f"{ctx}: claves desconocidas {sorted(sobran)} (permitidas: {sorted(CLAVES[tipo])})")

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
        err.append("proyecto.nombre es obligatorio")
    if solo_endpoint and solo_endpoint not in eps:
        err.append(f"--endpoint {solo_endpoint!r} no está en atlas.json")
    for k, v in datos.get("archivos", {}).items():
        if v.get("nacion") not in naciones:
            err.append(f"archivos[{k}]: nación desconocida {v.get('nacion')!r}")
    for eid, e in eps.items():
        if not e.get("resumen"):
            err.append(f"{eid}: falta resumen")
        if not any(p.get("archivo") for p in e.get("pasos", [])):
            err.append(f"{eid}: el recorrido no tiene ningún paso con código")
        if "tablas" not in e:
            err.append(f"{eid}: falta 'tablas' (usá [] si no toca la base)")
        for t in e.get("tablas", []):
            if t.get("tabla") not in tablas:
                err.append(f"{eid}: tabla inexistente {t.get('tabla')}")
        for p in e.get("pasos", []):
            if p.get("tabla") and p["tabla"] not in tablas:
                err.append(f"{eid}: paso con tabla inexistente {p['tabla']}")
            if not p.get("accion"):
                err.append(f"{eid}: hay un paso sin 'accion'")
    for h in datos.get("hallazgos", []):
        hid = h.get("id")
        if hall_ids.count(hid) > 1:
            err.append(f"hallazgo {hid}: id repetido")
        if h.get("severidad") not in SEVERIDADES:
            err.append(f"hallazgo {hid}: severidad debe ser una de {SEVERIDADES}")
        if h.get("origen") not in ORIGENES:
            err.append(f"hallazgo {hid}: origen debe ser una de {ORIGENES}")
        for k in ("titulo", "explicacion", "sugerencia", "archivo"):
            if not h.get(k):
                err.append(f"hallazgo {hid}: falta '{k}'")
        if h.get("endpoint") and h["endpoint"] not in eps and not solo_endpoint:
            err.append(f"hallazgo {hid}: endpoint inexistente {h['endpoint']}")
        if h.get("tabla") and h["tabla"] not in tablas:
            err.append(f"hallazgo {hid}: tabla inexistente {h['tabla']}")
    for r in datos.get("llamadas_rotas", []):
        if r.get("hallazgo") and r["hallazgo"] not in hall_ids:
            err.append(f"llamada rota {r.get('ruta')}: hallazgo inexistente {r['hallazgo']}")
    for archivo in datos.get("archivos", {}):
        if repo.texto(archivo) is None:
            err.append(f"archivos: no existe {archivo}")


def segmentos(ruta: str) -> list[str]:
    ruta = re.sub(r"^https?://[^/]+", "", ruta).split("?")[0]
    return ["*" if re.fullmatch(r"\{[^}]*\}|:\w+|\$\{[^}]*\}|\d+", s) else s.lower() for s in ruta.strip("/").split("/") if s]


def mismo_endpoint(a: str, b: str) -> bool:
    """Compara 'GET /api/x/{id}' con 'GET /x/{id}': mismo método y la ruta más corta es sufijo de la otra."""
    (ma, ra), (mb, rb) = a.split(" ", 1), b.split(" ", 1)
    sa, sb = segmentos(ra), segmentos(rb)
    corto, largo = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return ma == mb and bool(corto) and largo[len(largo) - len(corto):] == corto


def cobertura(datos: dict, esqueleto: Path, avisos: list[str]) -> None:
    if not esqueleto.exists():
        avisos.append(f"No hay {esqueleto.name}: no puedo comparar la cobertura (corré extract.py)")
        return
    sk = json.loads(esqueleto.read_text(encoding="utf-8"))
    del_sk = sorted({f"{e['metodo']} {e['ruta']}" for n in sk.get("nodos", []) for e in n.get("endpoints", [])})
    hechos = [ep_id(e) for e in datos.get("endpoints", [])]
    faltan = [x for x in del_sk if not any(mismo_endpoint(x, h) for h in hechos)]
    if faltan:
        avisos.append(f"{len(faltan)} de {len(del_sk)} endpoints del esqueleto no están en atlas.json: " + ", ".join(faltan[:12])
                      + (" …" if len(faltan) > 12 else ""))


def validar(repo_dir: Path, atlas: Path, solo_endpoint: str | None = None) -> tuple[dict | None, Repo]:
    repo = Repo(repo_dir.resolve())
    if not atlas.exists():
        repo.errores.append(f"No existe {atlas}: escribilo siguiendo references/conventions.md")
        return None, repo
    try:
        datos = json.loads(atlas.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        repo.errores.append(f"{atlas}: JSON inválido en la línea {e.lineno}, columna {e.colno}: {e.msg}")
        return None, repo
    revisar_claves(datos, repo.errores)
    for ref, ctx in recorrer_refs(datos):
        repo.resolver(ref, ctx)
    revisar_contenido(datos, repo, solo_endpoint)
    if not solo_endpoint:
        cobertura(datos, atlas.parent / "skeleton.json", repo.avisos)
    return datos, repo


def informar(repo: Repo) -> None:
    for titulo, lista in (("ERRORES", repo.errores), ("AVISOS", repo.avisos)):
        if lista:
            print(f"{titulo} ({len(lista)}):")
            for x in lista:
                print(f"  - {x}")
    print(f"{'OK' if not repo.errores else 'FALLA'}: {len(repo.errores)} errores, {len(repo.avisos)} avisos")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--atlas", type=Path, help="default: <repo>/.atlas/atlas.json")
    ap.add_argument("--endpoint", help='valida el modo de un solo endpoint, p. ej. "GET /api/x"')
    args = ap.parse_args()
    _, repo = validar(args.repo, args.atlas or args.repo / ".atlas" / "atlas.json", args.endpoint)
    informar(repo)
    sys.exit(1 if repo.errores else 0)


if __name__ == "__main__":
    main()
