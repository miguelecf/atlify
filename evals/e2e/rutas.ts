import { readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

/** Directorio temporal compartido por global-setup, el servidor y los tests. */
export const DIR_TMP = path.join(os.tmpdir(), "atlify-e2e");

/** Raíz del repo atlas-codigo (este archivo vive en evals/e2e). */
export const RAIZ = path.resolve(__dirname, "../..");

export type InfoBuild = {
  atlas: string;
  foco: string;
};

export function leerInfo(): InfoBuild {
  return JSON.parse(readFileSync(path.join(DIR_TMP, "info.json"), "utf8")) as InfoBuild;
}

export function rutaHtml(archivo: string, hash = ""): string {
  return `/${archivo}${hash}`;
}
