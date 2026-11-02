import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { DIR_TMP, leerInfo, rutaHtml } from "./rutas";

const ENDPOINT = "GET /api/appointments";
const HASH_RECORRIDO = `#/endpoint/${encodeURIComponent(ENDPOINT)}/recorrido`;

async function irA(page: Page, archivo: string, hash = ""): Promise<void> {
  await page.goto(rutaHtml(archivo, hash));
  await page.waitForLoadState("networkidle");
  await expect(page.locator("main")).toBeVisible();
}

async function abrirRecorrido(page: Page, paso?: number): Promise<void> {
  const hash = paso == null
    ? HASH_RECORRIDO
    : `${HASH_RECORRIDO}?paso=${paso}`;
  await irA(page, leerInfo().atlas, hash);
  await expect(page.locator(".stepper")).toBeVisible();
}

test("Resumen carga sin errores de consola", async ({ page }) => {
  const errores: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errores.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errores.push(`pageerror: ${err.message}`));

  await irA(page, leerInfo().atlas);

  await expect(page.locator("main")).toContainText("pet-care-api");
  await expect(page.getByRole("heading", { name: "pet-care-api" })).toBeVisible();
  expect(errores, errores.join("\n")).toEqual([]);
});

test("Las pestañas de navegación abren con contenido", async ({ page }) => {
  const errores: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errores.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errores.push(`pageerror: ${err.message}`));

  await irA(page, leerInfo().atlas);

  const secciones: Array<[RegExp, RegExp]> = [
    [/^Resumen/, /pet-care-api/],
    [/^Mapa/, /Cómo leer el mapa/],
    [/^Endpoints/, /Todo lo que expone el backend/],
    [/^Base de datos/, /Base de datos/],
    [/^Archivos/, /Qué hace cada archivo/],
    [/^Hallazgos/, /Problemas detectados en el código/],
  ];

  for (const [pestana, contenido] of secciones) {
    await page.getByRole("link", { name: pestana }).click();
    await expect(page.locator("main")).toContainText(contenido);
  }

  expect(errores, errores.join("\n")).toEqual([]);
});

test("El recorrido de GET /api/appointments muestra código real", async ({ page }) => {
  // El paso 4 es list_for_owner() en appointment_service.py.
  await abrirRecorrido(page, 3);

  const main = page.locator("main");
  await expect(main).toContainText("list_for_owner");
  await expect(main).toContainText("appointment_service.py");
  await expect(page.locator(".codigo").first()).toContainText("def list_for_owner");
});

test("Avanzar un paso del recorrido cambia el paso activo", async ({ page }) => {
  await abrirRecorrido(page);

  await expect(page.getByText(/Paso 1 de \d+/)).toBeVisible();
  const primerActivo = await page.locator(".paso.on").innerText();

  await page.getByRole("button", { name: /Siguiente/ }).click();

  await expect(page.getByText(/Paso 2 de \d+/)).toBeVisible();
  const segundoActivo = page.locator(".paso.on");
  await expect(segundoActivo).toHaveAttribute("aria-current", "step");
  await expect(segundoActivo).not.toHaveText(primerActivo);
  await expect(segundoActivo).toContainText("GET /api/appointments");
  await expect(segundoActivo).toContainText("Cliente API");
});

test('El buscador se abre con "/" y Enter navega al resultado', async ({ page }) => {
  await irA(page, leerInfo().atlas);

  await page.keyboard.press("/");
  const buscador = page.getByRole("textbox", {
    name: "Buscar endpoints, tablas, archivos o hallazgos",
  });
  await expect(buscador).toBeFocused();

  await page.keyboard.type("pets");
  const resultados = page.locator(".resultados");
  await expect(resultados).toBeVisible();
  await expect(resultados).toContainText("/api/pets");

  await page.keyboard.press("Enter");
  await expect(page.locator(".ep-cab h1")).toContainText("pets");
  await expect(page.locator(".stepper")).toBeVisible();
});

test("El botón de tema alterna data-theme y el fondo", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await irA(page, leerInfo().atlas);

  const fondoAntes = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );

  await page.getByRole("button", { name: "Cambiar tema" }).click();

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const fondoDespues = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  expect(fondoDespues).not.toBe(fondoAntes);
  expect(fondoDespues).toBe("rgb(16, 19, 17)");
});

test("Hallazgos muestra el problema de cancelación", async ({ page }) => {
  await irA(page, leerInfo().atlas);
  await page.getByRole("link", { name: /^Hallazgos/ }).click();

  await expect(page.locator("main")).toContainText(
    "Cualquiera puede cancelar cualquier turno",
  );
});

test("La vista de foco muestra el impacto y el botón de copiar", async ({ page }) => {
  await irA(page, leerInfo().foco);

  const main = page.locator("main");
  await expect(main).toContainText("Antes de tocarlo");
  await expect(main).toContainText("by_owner");
  await expect(
    page.getByRole("button", { name: /Copiar contexto/ }),
  ).toBeVisible();
});

test("Celular: no hay desborde horizontal y los pasos se apilan", async ({ page }, testInfo) => {
  test.skip(
    testInfo.project.name !== "celular",
    "Solo aplica al proyecto celular.",
  );
  const info = leerInfo();

  const rutas = [
    { nombre: "Resumen", hash: "" },
    { nombre: "Endpoints", hash: "#/endpoints" },
    { nombre: "Recorrido", hash: HASH_RECORRIDO },
  ];

  const comprobarSinDesborde = async (hash: string, etiqueta: string) => {
    await irA(page, info.atlas, hash);
    const medidas = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      ancho: window.innerWidth,
    }));
    expect(
      medidas.scroll,
      `${etiqueta}: scrollWidth ${medidas.scroll} > innerWidth ${medidas.ancho}`,
    ).toBeLessThanOrEqual(medidas.ancho);
  };

  for (const ruta of rutas) {
    await comprobarSinDesborde(ruta.hash, `${ruta.nombre} (iPhone 15)`);
  }

  await irA(page, info.atlas, HASH_RECORRIDO);
  await expect(page.locator(".stepper .sep").first()).toBeHidden();

  const cajas = await page.locator(".paso").evaluateAll((nodos) =>
    nodos.map((nodo) => {
      const r = nodo.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left };
    }),
  );
  expect(cajas.length).toBeGreaterThan(1);
  for (let i = 1; i < cajas.length; i++) {
    expect(
      cajas[i].top,
      `El paso ${i + 1} no está debajo del paso ${i}`,
    ).toBeGreaterThanOrEqual(cajas[i - 1].bottom - 1);
    expect(cajas[i].left).toBeCloseTo(cajas[0].left, 0);
  }

  // Además del iPhone 15, el requisito pide que a 360px no haya desborde.
  await page.setViewportSize({ width: 360, height: 780 });
  for (const ruta of rutas) {
    await comprobarSinDesborde(ruta.hash, `${ruta.nombre} (360px)`);
  }
});

test("La marca visible es Atlify", async ({ page }) => {
  await irA(page, leerInfo().atlas);

  await expect(page).toHaveTitle(/^Atlify/);
  await expect(page.locator("header.top .marca")).toContainText("Atlify");
});

test("Las fuentes Archivo están embebidas", async ({ page }) => {
  const info = leerInfo();
  const html = readFileSync(path.join(DIR_TMP, info.atlas), "utf8");
  test.skip(
    html.includes("/*__FONTS__*/"),
    "build.py todavía no reemplazó /*__FONTS__*/; no se pueden comprobar las fuentes.",
  );

  await irA(page, info.atlas);
  await page.evaluate(() => document.fonts.ready.then(() => true));

  const disponible = await page.evaluate(() =>
    document.fonts.check("16px Archivo"),
  );
  expect(disponible).toBe(true);
});
