import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  mkdirSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

import { DIR_TMP, RAIZ } from "./rutas";

const FIXTURE = path.join(RAIZ, "evals", "fixtures", "pet-care-api");
const REPO = path.join(FIXTURE, "repo");
const ATLAS = path.join(DIR_TMP, "atlas.json");

function limpiarDirectorio(dir: string): void {
  // No borramos el directorio: el servidor http ya puede tenerlo como cwd.
  mkdirSync(dir, { recursive: true });
  for (const nombre of readdirSync(dir)) {
    rmSync(path.join(dir, nombre), { recursive: true, force: true });
  }
}

function nombreDelHtml(salida: string): string {
  const match = salida.match(/^(?:Atlify|Atlas):\s+(.+?\.html)\b/m);
  if (!match) {
    throw new Error(
      `No encontré "Atlify: <ruta>.html" en la salida de build.py:\n${salida}`,
    );
  }
  return path.basename(match[1].trim());
}

function construir(extra: string[] = []): string {
  const salida = execFileSync(
    "python3",
    ["scripts/build.py", REPO, "--atlas", ATLAS, ...extra],
    { cwd: RAIZ, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
  return nombreDelHtml(salida);
}

export default async function globalSetup(): Promise<void> {
  limpiarDirectorio(DIR_TMP);
  copyFileSync(path.join(FIXTURE, "atlas.json"), ATLAS);

  const atlas = construir();
  const foco = construir(["--endpoint", "GET /api/appointments"]);

  writeFileSync(
    path.join(DIR_TMP, "info.json"),
    JSON.stringify({ atlas, foco }, null, 2),
    "utf8",
  );
}
