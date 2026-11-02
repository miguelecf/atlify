#!/usr/bin/env python3
"""Refresh the public fixture demos and fonts, or fail if they are stale.

Uses only the synthetic pet-care-api fixture. Never analyzes a user's repo.
Screenshots and the social card are refreshed separately with the browser tests.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FIXTURE = ROOT / "evals" / "fixtures" / "pet-care-api"


def comparable(path: Path) -> bytes:
    """Compare source content, not gzip implementation details across Python/zlib versions."""
    content = path.read_bytes()
    if path.suffix != ".html":
        return content
    def normalize(match: re.Match) -> bytes:
        source = gzip.decompress(base64.b64decode(match[1], validate=True))
        return b'"fuentesGz": "' + hashlib.sha256(source).hexdigest().encode() + b'"'
    return re.sub(rb'"fuentesGz": "([A-Za-z0-9+/=]+)"', normalize, content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check without modifying docs")
    args = parser.parse_args()
    stale = []
    with tempfile.TemporaryDirectory(prefix="atlify-release-") as temporary:
        work = Path(temporary)
        staging = work / "public"
        atlas = work / "atlas.json"
        shutil.copyfile(FIXTURE / "atlas.json", atlas)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "extract.py"),
                        str(FIXTURE / "repo"), "--routes", "-o", str(work / "skeleton.json")],
                       check=True, stdout=subprocess.DEVNULL)
        for name, extra in (("atlas.html", []), ("foco.html", ["--endpoint", "GET /api/appointments"])):
            target = staging / "demo" / name
            subprocess.run([sys.executable, str(ROOT / "scripts" / "build.py"),
                            str(FIXTURE / "repo"), "--atlas", str(atlas),
                            "-o", str(target), *extra], check=True)
        (staging / "fonts").mkdir()
        for font in (ROOT / "assets" / "vendor" / "fonts").iterdir():
            if font.is_file():
                shutil.copyfile(font, staging / "fonts" / font.name)
        for generated in sorted(staging.rglob("*")):
            if not generated.is_file():
                continue
            relative = generated.relative_to(staging)
            target = DOCS / relative
            if not target.is_file() or comparable(target) != comparable(generated):
                stale.append(relative.as_posix())
                if not args.check:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(generated, target)
    if args.check and stale:
        print("Stale release files: " + ", ".join(stale), file=sys.stderr)
        print("Run: python3 scripts/release.py", file=sys.stderr)
        return 1
    print("Release demos and fonts are current." if args.check else f"Updated {len(stale)} release files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
