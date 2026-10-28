"""Pruebas deterministas de los scripts sobre el fixture pet-care-api.

Uso:
    python3 -m unittest evals/test_scripts.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"
FIXTURE = RAIZ / "evals" / "fixtures" / "pet-care-api"
REPO = FIXTURE / "repo"


def correr(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)


def datos_html(path: Path) -> dict:
    m = re.search(r'<script id="atlas-datos" type="application/json">(.*?)</script>', path.read_text(encoding="utf-8"), re.S)
    assert m, f"{path} no tiene datos del atlas"
    return json.loads(m.group(1))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.extraccion = correr("extract.py", str(REPO), "-o", str(self.tmp / "skeleton.json"))
        self.atlas = self.tmp / "atlas.json"
        shutil.copy(FIXTURE / "atlas.json", self.atlas)

    def mutar(self, cambio) -> None:
        d = json.loads(self.atlas.read_text(encoding="utf-8"))
        cambio(d)
        self.atlas.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


class Extract(Base):
    def test_detecta_los_9_endpoints(self):
        sk = json.loads((self.tmp / "skeleton.json").read_text(encoding="utf-8"))
        eps = {f"{e['metodo']} {e['ruta']}" for n in sk["nodos"] for e in n.get("endpoints", [])}
        self.assertEqual(len(eps), 9, eps)
        self.assertIn("DELETE /appointments/{appointment_id}", eps)

    def test_para_revisar_encuentra_lo_plantado(self):
        salida = self.extraccion.stdout
        self.assertIn("PARA REVISAR", salida)
        self.assertRegex(salida, r"/api/pets/search.*solo coincide.*GET /pets/\{pet_id\}")
        self.assertIn("GET /services", salida)
        self.assertIn("GET /pets/{pet_id}", salida.split("PARA REVISAR")[1])

    def test_decoradores_indentados(self):
        repo = self.tmp / "factory"
        (repo / "app").mkdir(parents=True)
        (repo / "requirements.txt").write_text("fastapi\n")
        (repo / "app" / "router.py").write_text(
            "from fastapi import APIRouter\n\ndef build():\n    router = APIRouter(prefix='/x')\n\n"
            "    @router.get('/{id}')\n    def leer(id: int):\n        return id\n    return router\n")
        r = correr("extract.py", str(repo), "-o", str(self.tmp / "f.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        sk = json.loads((self.tmp / "f.json").read_text(encoding="utf-8"))
        self.assertIn({"metodo": "GET", "ruta": "/x/{id}"}, [{k: e[k] for k in ("metodo", "ruta")} for n in sk["nodos"] for e in n.get("endpoints", [])])


class Validate(Base):
    def validar(self, *extra):
        return correr("validate.py", str(REPO), "--atlas", str(self.atlas), *extra)

    def test_fixture_valido(self):
        r = self.validar()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK: 0 errores, 0 avisos", r.stdout)

    def test_clave_mal_escrita(self):
        self.mutar(lambda d: d["endpoints"][0].update({"explicación": d["endpoints"][0].pop("explicacion")}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("claves desconocidas ['explicación']", r.stdout)

    def test_simbolo_renombrado(self):
        self.mutar(lambda d: d["endpoints"][3]["pasos"][3].update({"simbolo": "book_v2"}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("no encuentro 'book_v2'", r.stdout)

    def test_rechaza_secretos(self):
        self.mutar(lambda d: d["endpoints"][0]["pasos"][0].update({"archivo": "backend/.env", "simbolo": None}))
        self.assertIn("parece contener secretos", self.validar().stdout)

    def test_cobertura_incompleta(self):
        self.mutar(lambda d: d.update({"endpoints": d["endpoints"][:-1]}))
        r = self.validar()
        self.assertIn("1 de 9 endpoints del esqueleto no están en atlas.json: GET /services", r.stdout)

    def test_hallazgo_sin_sugerencia(self):
        self.mutar(lambda d: d["hallazgos"][0].pop("sugerencia"))
        self.assertIn("falta 'sugerencia'", self.validar().stdout)


class Build(Base):
    def test_atlas_completo(self):
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = (self.tmp / "atlas.html").read_text(encoding="utf-8")
        self.assertIn("<title>Atlas pet-care-api</title>", html)
        self.assertNotIn("__ATLAS_DATOS__", html)
        self.assertNotIn("/*__VENDOR__*/", html)
        self.assertEqual(len(datos_html(self.tmp / "atlas.html")["endpoints"]), 9)

    def test_no_genera_con_errores(self):
        self.mutar(lambda d: d["hallazgos"][0].update({"severidad": "critica"}))
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.tmp / "atlas.html").exists())

    def test_endpoint_con_atlas_de_un_solo_endpoint(self):
        """El caso real de un repo grande: atlas.json tiene solo la ruta a arreglar."""
        def recortar(d):
            e = next(x for x in d["endpoints"] if x["metodo"] == "GET" and x["ruta"] == "/api/appointments")
            e.pop("tests", None)
            d["endpoints"] = [e]
            d["tablas"] = [t for t in d["tablas"] if t["nombre"] in {x["tabla"] for x in e["tablas"]}]
            d["hallazgos"] = [h for h in d["hallazgos"] if h.get("endpoint") == "GET /api/appointments"]
            d["llamadas_rotas"] = []
        self.mutar(recortar)
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas), "--endpoint", "GET /api/appointments")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = datos_html(self.tmp / "atlas-get-api-appointments.html")
        by_owner = next(i for i in d["foco"]["impacto"] if i["simbolo"] == "by_owner")
        self.assertEqual(by_owner["endpoints"], ["GET /pets", "POST /pets"])
        pets = next(t for t in d["foco"]["tablas"] if t["tabla"] == "pets")
        self.assertIn("GET /pets/{pet_id}", [x["id"] for x in pets["endpoints"]])
        self.assertEqual(d["endpoints"][0]["tests"], [])
        self.assertEqual([h["id"] for h in d["hallazgos"]], ["h-n-mas-1"])


if __name__ == "__main__":
    unittest.main()
