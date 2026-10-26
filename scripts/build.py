#!/usr/bin/env python3
"""Une skeleton.json + enrich.json, extrae los fragmentos de código del repo
y genera un único atlas.html autocontenido (funciona offline).

Uso:
    python build.py <repo> [--atlas-dir <repo>/.atlas] [-o <repo>/.atlas/atlas.html]

El agente nunca escribe código en enrich.json: da archivo + desde/hasta y este
script copia las líneas reales, así el atlas no puede inventar código.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MAX_LINEAS = 60
PLANTILLA = Path(__file__).resolve().parent.parent / "assets" / "atlas.html"
MARCA = "__ATLAS_DATOS__"


def fragmento(repo: Path, archivo: str, desde: int, hasta: int, avisos: list[str], ctx: str) -> dict | None:
    p = (repo / archivo)
    if not p.is_file():
        avisos.append(f"{ctx}: no existe el archivo {archivo}")
        return None
    lineas = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if not (1 <= desde <= len(lineas)):
        avisos.append(f"{ctx}: línea {desde} fuera de rango en {archivo} ({len(lineas)} líneas)")
        return None
    hasta = max(desde, min(hasta or desde, len(lineas)))
    if hasta - desde + 1 > MAX_LINEAS:
        avisos.append(f"{ctx}: fragmento de {hasta - desde + 1} líneas recortado a {MAX_LINEAS}; elegí las líneas clave")
        hasta = desde + MAX_LINEAS - 1
    return {"desde": desde, "codigo": "\n".join(lineas[desde - 1: hasta])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--atlas-dir", type=Path)
    ap.add_argument("-o", "--salida", type=Path)
    args = ap.parse_args()

    repo = args.repo.resolve()
    d = args.atlas_dir or repo / ".atlas"
    sk_path, en_path = d / "skeleton.json", d / "enrich.json"
    if not sk_path.exists():
        sys.exit(f"Falta {sk_path}: corré primero extract.py")
    sk = json.loads(sk_path.read_text(encoding="utf-8"))
    en = json.loads(en_path.read_text(encoding="utf-8")) if en_path.exists() else {}
    avisos: list[str] = []

    proyecto = en.get("proyecto", {})
    nodos = {"sistema": {"id": "sistema", "nombre": proyecto.get("nombre") or sk.get("repo", "Sistema"),
                         "nivel": "sistema", "padre": None, "tipo": "sistema",
                         "resumen": proyecto.get("resumen", ""), "porque": proyecto.get("porque", ""),
                         "pregunta": proyecto.get("pregunta", "")}}
    for n in sk["nodos"]:
        nodos[n["id"]] = dict(n)

    # nodos nuevos (nivel código, o contenedores/módulos que el extractor no vio)
    for i, nn in enumerate(en.get("nuevos", [])):
        ctx = f"nuevos[{i}] {nn.get('id')}"
        if not nn.get("id") or nn.get("padre") not in nodos:
            avisos.append(f"{ctx}: padre inexistente ({nn.get('padre')})")
            continue
        n = {"nivel": "codigo", "tipo": "metodo", **{k: v for k, v in nn.items() if k not in ("desde", "hasta")}}
        if nn.get("archivo") and nn.get("desde"):
            f = fragmento(repo, nn["archivo"], int(nn["desde"]), int(nn.get("hasta") or nn["desde"]), avisos, ctx)
            if f:
                n["linea"] = f["desde"]
                n["codigo"] = f
        nodos[n["id"]] = n

    # enriquecimiento de nodos existentes
    for nid, extra in en.get("nodos", {}).items():
        if nid not in nodos:
            avisos.append(f"nodos.{nid}: no existe en el esqueleto (¿renombrado o borrado?)")
            continue
        for k in ("resumen", "porque", "pregunta", "nombre", "tipo"):
            if extra.get(k):
                nodos[nid][k] = extra[k]
        if extra.get("desde") and nodos[nid].get("archivo"):
            f = fragmento(repo, nodos[nid]["archivo"], int(extra["desde"]), int(extra.get("hasta") or extra["desde"]),
                          avisos, f"nodos.{nid}")
            if f:
                nodos[nid]["codigo"] = f

    # relaciones
    quitar = {(r["de"], r["a"]) for r in en.get("quitar_relaciones", [])}
    rels = [r for r in sk["relaciones"] if (r["de"], r["a"]) not in quitar]
    for i, r in enumerate(en.get("relaciones", [])):
        if r.get("de") in nodos and r.get("a") in nodos:
            rels.append({"de": r["de"], "a": r["a"], "etiqueta": r.get("etiqueta", "usa"), "origen": "agente"})
        else:
            avisos.append(f"relaciones[{i}]: extremo inexistente {r.get('de')} → {r.get('a')}")

    # flujos
    flujos = []
    for i, fl in enumerate(en.get("flujos", [])):
        pasos = []
        for j, p in enumerate(fl.get("pasos", [])):
            ctx = f"flujos[{fl.get('id', i)}].pasos[{j}]"
            if p.get("nodo") not in nodos:
                avisos.append(f"{ctx}: nodo inexistente {p.get('nodo')}")
                continue
            paso = {k: v for k, v in p.items() if k not in ("desde", "hasta")}
            archivo = p.get("archivo") or nodos[p["nodo"]].get("archivo")
            if archivo and p.get("desde"):
                paso["archivo"] = archivo
                f = fragmento(repo, archivo, int(p["desde"]), int(p.get("hasta") or p["desde"]), avisos, ctx)
                if f:
                    paso["codigo"] = f
            pasos.append(paso)
        if pasos:
            flujos.append({**{k: v for k, v in fl.items() if k != "pasos"}, "pasos": pasos})

    # cobertura: qué falta explicar
    sin_resumen = [n for n in nodos.values() if n["nivel"] in ("sistema", "contenedor", "modulo") and not n.get("resumen")]
    clave = ("controller", "service", "repository", "entity", "pagina", "servicio-api", "aplicacion", "hook")
    sin_resumen_k = [n for n in nodos.values() if n["nivel"] == "componente" and n.get("tipo") in clave
                     and not n.get("resumen")]

    datos = {"repo": sk.get("repo"), "generado": sk.get("generado"), "nodos": list(nodos.values()),
             "relaciones": rels, "flujos": flujos}
    html = PLANTILLA.read_text(encoding="utf-8")
    if MARCA not in html:
        sys.exit(f"La plantilla {PLANTILLA} no tiene la marca {MARCA}")
    payload = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    salida = args.salida or d / "atlas.html"
    salida.write_text(html.replace(MARCA, payload), encoding="utf-8")

    print(f"Atlas: {salida}  ({salida.stat().st_size // 1024} KB)")
    print(f"Nodos: {len(nodos)} | relaciones: {len(rels)} | flujos: {len(flujos)}")
    if sin_resumen:
        print(f"\nSin resumen ({len(sin_resumen)} de sistema/contenedor/módulo):")
        for n in sin_resumen[:30]:
            print(f"  {n['id']}")
    if sin_resumen_k:
        print(f"\nComponentes clave sin resumen: {len(sin_resumen_k)}"
              + (" (ej.: " + ", ".join(n["id"] for n in sin_resumen_k[:5]) + ")" if sin_resumen_k else ""))
    if avisos:
        print(f"\nAVISOS ({len(avisos)}), corregí enrich.json:")
        for a in avisos:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
