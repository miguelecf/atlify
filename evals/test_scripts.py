"""Deterministic tests for the scripts against the pet-care-api fixture.

Usage:
    python3 -m unittest evals.test_scripts
"""
import json
import os
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


def correr_atlify(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "atlify.py"), *args], capture_output=True, text=True, env=env)


def datos_html(path: Path) -> dict:
    m = re.search(r'<script id="atlas-datos" type="application/json">(.*?)</script>', path.read_text(encoding="utf-8"), re.S)
    assert m, f"{path} has no atlas data"
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
    def test_detects_the_9_endpoints(self):
        sk = json.loads((self.tmp / "skeleton.json").read_text(encoding="utf-8"))
        eps = {f"{e['metodo']} {e['ruta']}" for n in sk["nodos"] for e in n.get("endpoints", [])}
        self.assertEqual(len(eps), 9, eps)
        self.assertIn("DELETE /appointments/{appointment_id}", eps)

    def test_to_review_finds_the_planted_ones(self):
        salida = self.extraccion.stdout
        self.assertIn("TO REVIEW", salida)
        self.assertRegex(salida, r"/api/pets/search.*only matches.*GET /pets/\{pet_id\}")
        self.assertIn("GET /services", salida)
        self.assertIn("GET /pets/{pet_id}", salida.split("TO REVIEW")[1])

    def test_routes_flag_prints_inventory_without_the_tree(self):
        salida = correr("extract.py", str(REPO), "-o", str(self.tmp / "r.json"), "--routes").stdout
        self.assertIn("DELETE /appointments/{appointment_id}", salida)
        self.assertIn("TO REVIEW", salida)
        self.assertNotIn("k:", salida)  # no tree, only the inventory
        arbol_completo = self.extraccion.stdout
        self.assertIn("k:backend/app/routers/appointments.py", arbol_completo)

    def test_indented_decorators(self):
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

    def test_router_prefixes_by_variable(self):
        repo = self.tmp / "prefijos"
        (repo / "app").mkdir(parents=True)
        (repo / "requirements.txt").write_text("fastapi\n")
        (repo / "app" / "router.py").write_text(
            "from fastapi import APIRouter\n\nrouter = APIRouter(prefix='/v1')\n"
            "admin = APIRouter(prefix='/admin')\n\n"
            "@router.get('/x')\ndef x():\n    return 1\n\n"
            "@admin.get('/y')\ndef y():\n    return 2\n")
        r = correr("extract.py", str(repo), "-o", str(self.tmp / "p.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        sk = json.loads((self.tmp / "p.json").read_text(encoding="utf-8"))
        eps = {f"{e['metodo']} {e['ruta']}" for n in sk["nodos"] for e in n.get("endpoints", [])}
        self.assertEqual(eps, {"GET /v1/x", "GET /admin/y"})

    def test_does_not_follow_symlinks(self):
        repo = self.tmp / "con-enlaces"
        (repo / "app").mkdir(parents=True)
        (repo / "requirements.txt").write_text("fastapi\n")
        (repo / "app" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
        (repo / "app" / "loop").symlink_to(repo, target_is_directory=True)
        fuera = self.tmp / "fuera.py"
        fuera.write_text("def externo():\n    return 1\n")
        (repo / "app" / "externo.py").symlink_to(fuera)
        r = correr("extract.py", str(repo), "-o", str(self.tmp / "e.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        sk = json.loads((self.tmp / "e.json").read_text(encoding="utf-8"))
        componentes = [n for n in sk["nodos"] if n["nivel"] == "componente"]
        self.assertEqual(len(componentes), 1, componentes)
        self.assertFalse(any("loop" in (n.get("archivo") or "") for n in sk["nodos"]))
        self.assertEqual([n["archivo"] for n in componentes], ["app/main.py"])


class Validate(Base):
    def validar(self, *extra):
        return correr("validate.py", str(REPO), "--atlas", str(self.atlas), *extra)

    def test_valid_fixture(self):
        r = self.validar()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK: 0 errors, 0 warnings", r.stdout)

    def test_misspelled_key(self):
        self.mutar(lambda d: d["endpoints"][0].update({"explicación": d["endpoints"][0].pop("explicacion")}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown keys ['explicación']", r.stdout)

    def test_renamed_symbol(self):
        self.mutar(lambda d: d["endpoints"][3]["pasos"][3].update({"simbolo": "book_v2"}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot find 'book_v2'", r.stdout)

    def test_rejects_secrets(self):
        self.mutar(lambda d: d["endpoints"][0]["pasos"][0].update({"archivo": "backend/.env", "simbolo": None}))
        self.assertIn("may contain secrets", self.validar().stdout)

    def test_incomplete_coverage(self):
        self.mutar(lambda d: d.update({"endpoints": d["endpoints"][:-1]}))
        r = self.validar()
        self.assertIn("1 of 9 skeleton endpoints are missing from atlas.json: GET /services", r.stdout)

    def test_finding_without_sugerencia(self):
        self.mutar(lambda d: d["hallazgos"][0].pop("sugerencia"))
        self.assertIn("missing 'sugerencia'", self.validar().stdout)

    def test_rejects_path_outside_the_repo(self):
        self.mutar(lambda d: d["endpoints"][0]["pasos"][0].update({"archivo": "../../../../SKILL.md"}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("../../../../SKILL.md is outside the repo", r.stdout)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        b = correr("build.py", str(REPO), "--atlas", str(self.atlas))
        self.assertNotEqual(b.returncode, 0)
        self.assertFalse((self.tmp / "atlas.html").exists())

    def test_rejects_absolute_path(self):
        self.mutar(lambda d: d["endpoints"][0]["pasos"][0].update({"archivo": "/etc/passwd"}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("/etc/passwd is outside the repo", r.stdout)

    def test_endpoints_null(self):
        self.mutar(lambda d: d.update({"endpoints": None}))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("endpoints: expected a list of objects", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_root_is_a_list(self):
        self.atlas.write_text("[]", encoding="utf-8")
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("the root must be an object", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_endpoint_that_is_a_string(self):
        self.mutar(lambda d: d["endpoints"].__setitem__(0, "GET /x"))
        r = self.validar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("endpoints: expected a list of objects", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_endpoint_matched_by_suffix(self):
        """The skeleton prints routes without the /api prefix; --endpoint must accept that form."""
        r = self.validar("--endpoint", "GET /appointments")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK: 0 errors", r.stdout)

    def test_endpoint_not_in_atlas_lists_the_problem(self):
        r = self.validar("--endpoint", "GET /no-existe")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not in atlas.json", r.stdout)


class Build(Base):
    def test_full_atlas(self):
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = (self.tmp / "atlas.html").read_text(encoding="utf-8")
        self.assertIn("<title>Atlify · pet-care-api</title>", html)
        self.assertNotIn("__ATLAS_DATOS__", html)
        self.assertNotIn("/*__VENDOR__*/", html)
        self.assertEqual(len(datos_html(self.tmp / "atlas.html")["endpoints"]), 9)

    def test_replaces_the_font_marker(self):
        plantilla = (RAIZ / "assets" / "visor.html").read_text(encoding="utf-8")
        if "/*__FONTS__*/" not in plantilla:
            self.skipTest("the template does not have the /*__FONTS__*/ marker yet")
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = (self.tmp / "atlas.html").read_text(encoding="utf-8")
        self.assertNotIn("/*__FONTS__*/", html)
        self.assertIn("font-family:'Archivo';font-weight:100 900", html)
        self.assertIn("font-family:'Archivo Black';font-weight:400", html)
        self.assertIn("data:font/woff2;base64,", html)

    def test_no_output_with_errors(self):
        self.mutar(lambda d: d["hallazgos"][0].update({"severidad": "critica"}))
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.tmp / "atlas.html").exists())

    def test_endpoint_with_single_endpoint_atlas(self):
        """The real case for a large repo: atlas.json holds only the route to fix."""
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
        html = (self.tmp / "atlas-get-api-appointments.html").read_text(encoding="utf-8")
        self.assertIn("<title>Atlify · pet-care-api · GET /api/appointments</title>", html)
        d = datos_html(self.tmp / "atlas-get-api-appointments.html")
        by_owner = next(i for i in d["foco"]["impacto"] if i["simbolo"] == "by_owner")
        self.assertEqual(by_owner["endpoints"], ["GET /pets", "POST /pets"])
        pets = next(t for t in d["foco"]["tablas"] if t["tabla"] == "pets")
        self.assertIn("GET /pets/{pet_id}", [x["id"] for x in pets["endpoints"]])
        self.assertEqual(d["endpoints"][0]["tests"], [])
        self.assertEqual([h["id"] for h in d["hallazgos"]], ["h-n-mas-1"])

    def test_endpoint_by_suffix_uses_the_canonical_id(self):
        """--endpoint in the skeleton's form resolves to the atlas route and builds."""
        r = correr("build.py", str(REPO), "--atlas", str(self.atlas), "--endpoint", "GET /appointments")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.tmp / "atlas-get-api-appointments.html").exists())

    def test_empty_tests_list_still_discovers_tests(self):
        """A written `tests: []` must not disable test discovery."""
        repo = self.tmp / "con-test"
        (repo / "app").mkdir(parents=True)
        (repo / "requirements.txt").write_text("fastapi\n")
        (repo / "app" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/x')\ndef leer_x():\n    return 1\n")
        (repo / "app" / "test_x.py").write_text(
            "from app.main import leer_x\n\ndef test_x():\n    assert leer_x() == 1\n")
        atlas = self.tmp / "test-atlas.json"
        atlas.write_text(json.dumps({
            "proyecto": {"nombre": "con-test"},
            "naciones": [], "archivos": {}, "tablas": [], "hallazgos": [], "llamadas_rotas": [],
            "endpoints": [{
                "metodo": "GET", "ruta": "/x", "resumen": "Devuelve uno.", "tablas": [],
                "tests": [],
                "pasos": [{"archivo": "app/main.py", "simbolo": "leer_x", "accion": "entra"}],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        correr("extract.py", str(repo))
        r = correr("build.py", str(repo), "--atlas", str(atlas), "--endpoint", "GET /x")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = datos_html(self.tmp / "atlas-get-x.html")
        self.assertIn("test_x", [t["simbolo"] for t in d["endpoints"][0]["tests"]])

    def test_climbs_from_service_to_controller_java(self):
        repo = self.tmp / "spring"
        java = repo / "src" / "main" / "java" / "com" / "example"
        java.mkdir(parents=True)
        (repo / "pom.xml").write_text(
            "<project><dependencies><dependency><groupId>org.springframework.boot</groupId>"
            "<artifactId>spring-boot-starter-web</artifactId></dependency></dependencies></project>")
        (java / "PetController.java").write_text(
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n@RequestMapping(\"/pets\")\n"
            "public class PetController {\n"
            "    private final PetService petService = new PetService();\n\n"
            "    @GetMapping(\"/{id}\")\n"
            "    public Pet getPet(Long id) {\n"
            "        return petService.buscar(id);\n"
            "    }\n\n"
            "    @GetMapping(\"/all\")\n"
            "    public List<Pet> listar() {\n"
            "        return petService.buscar(1L);\n"
            "    }\n"
            "}\n")
        (java / "PetService.java").write_text(
            "package com.example;\n\n@Service\npublic class PetService {\n"
            "    public Pet buscar(Long id) {\n"
            "        return new Pet();\n"
            "    }\n"
            "}\n")
        atlas = self.tmp / "spring-atlas.json"
        atlas.write_text(json.dumps({
            "proyecto": {"nombre": "mini-spring"},
            "naciones": [], "archivos": {}, "tablas": [], "hallazgos": [], "llamadas_rotas": [],
            "endpoints": [{
                "metodo": "GET", "ruta": "/pets/{id}", "resumen": "Reads one pet.", "tablas": [],
                "pasos": [
                    {"archivo": "src/main/java/com/example/PetController.java", "simbolo": "getPet", "accion": "enters"},
                    {"archivo": "src/main/java/com/example/PetService.java", "simbolo": "buscar", "accion": "searches"},
                ],
            }],
        }, ensure_ascii=False), encoding="utf-8")
        sk = self.tmp / "spring-skeleton.json"
        e = correr("extract.py", str(repo), "-o", str(sk))
        self.assertEqual(e.returncode, 0, e.stdout + e.stderr)
        r = correr("build.py", str(repo), "--atlas", str(atlas), "--skeleton", str(sk), "--endpoint", "GET /pets/{id}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = datos_html(self.tmp / "atlas-get-pets-id.html")
        service = next(i for i in d["foco"]["impacto"] if i["simbolo"] == "buscar")
        self.assertIn("GET /pets/all", service["endpoints"])


class Atlify(Base):
    def test_doctor(self):
        r = correr_atlify("doctor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_help_lists_the_subcommands(self):
        r = correr_atlify("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for comando in ("extract", "validate", "build", "doctor"):
            self.assertIn(comando, r.stdout)

    def test_extract_forwards_to_the_script(self):
        salida = self.tmp / "cli.json"
        r = correr_atlify("extract", str(REPO), "-o", str(salida))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TO REVIEW", r.stdout)
        self.assertTrue(salida.exists())

    def test_actualizar_is_a_real_flag(self):
        """`--actualizar` (update mode) runs extract and prints the CHANGES block."""
        salida = self.tmp / "cli.json"
        r1 = correr_atlify("--actualizar", str(REPO), "-o", str(salida))
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertTrue(salida.exists())
        r2 = correr_atlify("--actualizar", str(REPO), "-o", str(salida))
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("No component changes since the last skeleton.", r2.stdout)
        r3 = correr_atlify("extract", str(REPO), "-o", str(salida), "--actualizar")
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)


class Install(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)

    def instalar(self, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "HOME": str(self.home)}
        return subprocess.run(["/bin/sh", str(RAIZ / "install.sh"), *args], capture_output=True, text=True, env=env)

    def test_idempotent_link_and_uninstall(self):
        (self.home / ".claude" / "skills").mkdir(parents=True)
        r = self.instalar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        enlace = self.home / ".claude" / "skills" / "atlify"
        self.assertTrue(enlace.is_symlink())
        self.assertEqual(enlace.resolve(), RAIZ.resolve())
        agentes = self.home / ".agents" / "skills" / "atlify"
        self.assertTrue(agentes.is_symlink())
        r = self.instalar()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("already present", r.stdout)
        r = self.instalar("--uninstall")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(enlace.exists())
        self.assertFalse(enlace.is_symlink())
        self.assertFalse(agentes.exists())
        self.assertFalse(agentes.is_symlink())

    def test_copy_with_marker_and_uninstall(self):
        skills = self.home / ".codex" / "skills"
        skills.mkdir(parents=True)
        r = self.instalar("--copy", "--only", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        destino = skills / "atlify"
        self.assertTrue((destino / ".atlify-install").is_file())
        self.assertFalse((destino / ".git").exists())
        r = self.instalar("--copy", "--only", "codex")
        self.assertIn("copied", r.stdout)
        r = self.instalar("--uninstall", "--only", "codex")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(destino.exists())


if __name__ == "__main__":
    unittest.main()
