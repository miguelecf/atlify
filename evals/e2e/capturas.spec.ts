import { mkdirSync } from "node:fs";
import path from "node:path";

import { devices, expect, test, type Page } from "@playwright/test";

import { leerInfo, rutaHtml } from "./rutas";

const ENDPOINT = "GET /api/appointments";

function pidenCapturas(testInfo: { config: unknown }): boolean {
  const config = testInfo.config as { argv?: string[]; grep?: RegExp | RegExp[] };
  const argv = config.argv ?? [];
  const indiceGrep = argv.findIndex((arg) => arg === "--grep" || arg === "-g");
  if (indiceGrep >= 0 && argv[indiceGrep + 1]?.includes("capturas")) return true;
  if (argv.some((arg) => arg.includes("@capturas"))) return true;

  const grep = config.grep;
  const patrones = Array.isArray(grep) ? grep : grep ? [grep] : [];
  return patrones.some((patron) => patron.source.includes("capturas"));
}

async function preparar(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready.then(() => true));
}

test("@capturas · capturas de revisión visual", async ({ browser }, testInfo) => {
  test.skip(
    testInfo.project.name !== "escritorio",
    "Las capturas se generan una sola vez.",
  );
  test.skip(
    !pidenCapturas(testInfo),
    "Correr con: npx playwright test --grep @capturas",
  );

  const info = leerInfo();
  const salida = path.join(__dirname, "capturas");
  mkdirSync(salida, { recursive: true });

  // iPhone 15 pero sobre Chromium, igual que el proyecto "celular".
  const { defaultBrowserType: _ignorado, ...iphone } = devices["iPhone 15"];

  const modos = [
    {
      nombre: "escritorio-claro",
      opciones: {
        viewport: { width: 1280, height: 1000 },
        colorScheme: "light" as const,
      },
      oscuro: false,
    },
    {
      nombre: "escritorio-oscuro",
      opciones: {
        viewport: { width: 1280, height: 1000 },
        colorScheme: "light" as const,
      },
      oscuro: true,
    },
    {
      nombre: "celular",
      opciones: iphone,
      oscuro: false,
    },
  ];

  const paginas = [
    { id: "resumen", archivo: info.atlas, hash: "" },
    {
      id: "mapa",
      archivo: info.atlas,
      hash: `#/mapa?sel=${encodeURIComponent(`e:${ENDPOINT}`)}`,
      espera: 800,
    },
    {
      id: "recorrido",
      archivo: info.atlas,
      hash: `#/endpoint/${encodeURIComponent(ENDPOINT)}/recorrido?paso=3`,
    },
    { id: "foco", archivo: info.foco, hash: "" },
    {
      id: "hallazgos",
      archivo: info.atlas,
      hash: "#/hallazgos",
      accion: async (page: Page) => {
        await page.locator(".hall-cab").first().click();
      },
    },
  ];

  for (const modo of modos) {
    const contexto = await browser.newContext(modo.opciones);
    const page = await contexto.newPage();

    await page.goto(rutaHtml(info.atlas));
    await preparar(page);

    if (modo.oscuro) {
      await page.getByRole("button", { name: "Cambiar tema" }).click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    }

    for (const vista of paginas) {
      await page.goto(rutaHtml(vista.archivo, vista.hash));
      await preparar(page);
      if (vista.accion) await vista.accion(page);
      if (vista.espera) await page.waitForTimeout(vista.espera);
      await page.screenshot({
        path: path.join(salida, `${modo.nombre}-${vista.id}.png`),
        animations: "disabled",
      });
    }

    await contexto.close();
  }
});
