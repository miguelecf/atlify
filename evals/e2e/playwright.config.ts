import { mkdirSync } from "node:fs";

import { defineConfig, devices } from "@playwright/test";

import { DIR_TMP } from "./rutas";

const PUERTO = 4173;
const URL_BASE = `http://127.0.0.1:${PUERTO}`;
// la landing (docs/) se sirve aparte; landing.spec.ts la visita con esta URL
export const PUERTO_DOCS = 4174;
const DOCS = new URL("../../docs", `file://${__dirname}/`).pathname;

// El webServer puede arrancar antes que global-setup; el directorio debe existir.
mkdirSync(DIR_TMP, { recursive: true });

export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  globalSetup: "./global-setup.ts",
  outputDir: "test-results",
  use: {
    baseURL: URL_BASE,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `python3 -m http.server ${PUERTO} --bind 127.0.0.1 --directory "${DIR_TMP}"`,
      url: URL_BASE,
      reuseExistingServer: false,
      timeout: 20_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: `python3 -m http.server ${PUERTO_DOCS} --bind 127.0.0.1 --directory "${DOCS}"`,
      url: `http://127.0.0.1:${PUERTO_DOCS}`,
      reuseExistingServer: false,
      timeout: 20_000,
      stdout: "ignore",
      stderr: "pipe",
    },
  ],
  projects: [
    {
      name: "escritorio",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: "celular",
      use: {
        ...devices["iPhone 15"],
        browserName: "chromium",
      },
    },
  ],
});
