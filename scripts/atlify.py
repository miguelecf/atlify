#!/usr/bin/env python3
"""Atlify CLI: extract, validate, build and doctor.

Each subcommand forwards its arguments to the script that already does the
work, without duplicating logic. `doctor` checks the environment and assets.
`--actualizar` (update mode) is a synonym for `extract`: running extract again
prints the CHANGES block against the previous skeleton.

Usage:
    python atlify.py extract <repo> [-o <repo>/.atlify/skeleton.json] [--routes]
    python atlify.py validate <repo> [--atlas <repo>/.atlify/atlas.json] [--endpoint "GET /api/x"]
    python atlify.py build <repo> [--endpoint "GET /api/x"] [-o output.html]
    python atlify.py --actualizar <repo>
    python atlify.py doctor
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"
ASSETS = RAIZ / "assets"
VENDOR = ASSETS / "vendor" / "htm-preact-3.1.1.umd.js"
FUENTES = (ASSETS / "vendor" / "fonts" / "archivo-latin-var.woff2",
           ASSETS / "vendor" / "fonts" / "archivo-black-latin.woff2")
COMANDOS = {
    "extract": "extracts the repo skeleton to .atlify/skeleton.json",
    "validate": "validates .atlify/atlas.json against the real code",
    "build": "generates the offline HTML viewer from atlas.json",
    "doctor": "checks Python, template, vendor and fonts",
}


def reenviar(script: str, args: list[str]) -> None:
    """Imports <script>.py and calls its main() with these arguments."""
    sys.path.insert(0, str(SCRIPTS))
    modulo = importlib.import_module(script)
    sys.argv = [str(SCRIPTS / f"{script}.py"), *args]
    modulo.main()


def doctor() -> int:
    chequeos = [(f"Python {sys.version.split()[0]} (needs >= 3.10)", sys.version_info >= (3, 10)),
                (f"template {ASSETS / 'visor.html'}", (ASSETS / "visor.html").is_file()),
                (f"vendor {VENDOR.name}", VENDOR.is_file())]
    chequeos += [(f"font {p.name}", p.is_file()) for p in FUENTES]
    for descripcion, ok in chequeos:
        print(f"{descripcion}: {'OK' if ok else 'FAIL'}")
    fallas = sum(not ok for _, ok in chequeos)
    print("OK" if not fallas else "FAIL")
    return 1 if fallas else 0


def ayuda() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="atlify.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", metavar="<command>")
    for nombre, descripcion in COMANDOS.items():
        sub.add_parser(nombre, help=descripcion, description=descripcion)
    return ap


def main() -> int:
    argv = sys.argv[1:]
    # --actualizar anywhere means update mode: same as extract (which prints CHANGES)
    if "--actualizar" in argv:
        argv = [a for a in argv if a != "--actualizar"]
        if not (argv and argv[0] in COMANDOS):
            argv = ["extract", *argv]
    # subcommands are forwarded as-is: their options may go before or after the repo
    if argv and argv[0] in COMANDOS:
        if argv[0] == "doctor":
            if len(argv) > 1:
                extra = argparse.ArgumentParser(prog="atlify.py doctor", description=COMANDOS["doctor"])
                extra.parse_args(argv[1:])  # only accepts -h/--help
            return doctor()
        reenviar(argv[0], argv[1:])
        return 0
    ap = ayuda()
    if not argv:
        ap.print_help()
        return 0
    ap.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
