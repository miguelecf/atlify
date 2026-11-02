import { expect, test } from "@playwright/test";

const LANDING = "http://127.0.0.1:4174/";

test("La landing carga con sus capturas y sin errores", async ({ page }) => {
  const errores: string[] = [];
  page.on("pageerror", (err) => errores.push(err.message));
  page.on("response", (r) => {
    if (r.url().startsWith(LANDING) && r.status() >= 400)
      errores.push(`${r.status()} ${r.url()}`);
  });
  await page.goto(LANDING);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.evaluate(() =>
    document
      .querySelectorAll("img")
      .forEach((i) => i.setAttribute("loading", "eager")),
  );
  await page.waitForLoadState("networkidle");
  const rotas = await page
    .locator("img")
    .evaluateAll((imgs) =>
      (imgs as HTMLImageElement[])
        .filter((i) => !i.complete || i.naturalWidth === 0)
        .map((i) => i.src),
    );
  expect(rotas).toEqual([]);
  expect(errores, errores.join("\n")).toEqual([]);
});

test("La landing no desborda en horizontal", async ({ page }) => {
  await page.goto(LANDING);
  const [ancho, vista] = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    innerWidth,
  ]);
  expect(ancho).toBeLessThanOrEqual(vista);
});

test("Los enlaces a la demo abren el atlas y el foco", async ({ page }) => {
  for (const [href, texto] of [
    ["demo/atlas.html", "pet-care-api"],
    ["demo/foco.html", "Antes de tocarlo"],
  ]) {
    await page.goto(LANDING + href);
    await expect(page.locator("main")).toContainText(texto);
  }
  await page.goto(LANDING);
  const hrefs = await page
    .locator("a[href^='demo/']")
    .evaluateAll((as) => as.map((a) => a.getAttribute("href")!.split("#")[0]));
  expect(new Set(hrefs)).toEqual(
    new Set(["demo/atlas.html", "demo/foco.html"]),
  );
});

test("Las anclas internas de la landing tienen destino", async ({ page }) => {
  await page.goto(LANDING);
  const faltan = await page
    .locator("a[href^='#']")
    .evaluateAll((as) =>
      as
        .map((a) => a.getAttribute("href")!)
        .filter((h) => h.length > 1 && !document.querySelector(h)),
    );
  expect(faltan).toEqual([]);
});

test("Copiar el comando de instalación pone el texto en el portapapeles", async ({
  page,
  context,
  browserName,
}) => {
  test.skip(
    browserName !== "chromium",
    "permisos de portapapeles solo en Chromium",
  );
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(LANDING + "#instalar");
  const boton = page
    .locator("#instalar button", { hasText: /copiar/i })
    .first();
  await boton.click();
  const texto = await page.evaluate(() => navigator.clipboard.readText());
  expect(texto).toContain("git clone https://github.com/miguelecf/atlify.git");
});

test("El explorador cambia captura, descripción y destino con teclado", async ({
  page,
}) => {
  await page.goto(LANDING);
  for (const [name, image, href] of [
    ["Mapa", "mapa.png", "#/mapa"],
    ["Hallazgos", "hallazgos.png", "#/hallazgos"],
    ["Antes de tocarlo", "foco.png", "demo/foco.html"],
    ["Recorrido", "recorrido.png", "/recorrido"],
  ]) {
    const button = page.getByRole("button", { name, exact: true });
    await button.focus();
    await page.keyboard.press("Enter");
    await expect(button).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.locator('.explorer-controls [aria-pressed="true"]'),
    ).toHaveCount(1);
    await expect(page.locator("#preview-image")).toHaveAttribute(
      "src",
      `img/${image}`,
    );
    await expect(page.locator("#preview-link")).toHaveAttribute(
      "href",
      new RegExp(href),
    );
    await expect(page.locator("#preview-title")).not.toBeEmpty();
  }
});

test("El mensaje de uso se adapta al agente sin mezclar comandos de terminal", async ({
  page,
}) => {
  await page.goto(LANDING + "#instalar");
  for (const [agent, command] of [
    ["Claude Code", "/atlify"],
    ["Otro agente", "Usá atlify para generar el atlas de este repo."],
    ["Codex", "$atlify"],
  ]) {
    await page.getByRole("radio", { name: agent, exact: true }).check();
    await expect(page.locator("#code-usage")).toHaveText(command);
    await expect(page.locator("#code-usage")).not.toContainText("git clone");
  }
});

test("Si falla el portapapeles selecciona el texto y explica cómo copiar", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: () => Promise.reject(new Error("denied")) },
    }),
  );
  await page.goto(LANDING + "#instalar");
  await page
    .getByRole("button", { name: "Copiar los comandos de instalación" })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "No se pudo copiar" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => window.getSelection()?.toString()),
  ).toContain("git clone");
});

test("No necesita servicios externos y respeta movimiento reducido", async ({
  page,
}) => {
  const external: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith(LANDING)) external.push(request.url());
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(LANDING);
  await page.evaluate(() => document.fonts.ready);
  expect(external).toEqual([]);
  expect(
    await page.evaluate(
      () => getComputedStyle(document.documentElement).scrollBehavior,
    ),
  ).toBe("auto");
});

test("Sin JavaScript siguen disponibles contenido, instalación, FAQ y demos", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(LANDING);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("#code-install")).toContainText("git clone");
  await expect(page.locator(".explorer-controls")).toBeHidden();
  await page.locator("summary").filter({ hasText: "¿Mi código sale" }).click();
  await expect(
    page.getByText("Offline describe el HTML", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Explorar la demo", exact: true }).first(),
  ).toBeVisible();
  await context.close();
});

test("Responsive en 360, 768 y 1280 px, y texto ampliado al 200%", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "escritorio",
    "Matriz adicional en escritorio",
  );
  for (const width of [360, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(LANDING);
    for (const largeText of [false, true]) {
      await page.evaluate(
        (large) =>
          (document.documentElement.style.fontSize = large ? "200%" : ""),
        largeText,
      );
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      expect(overflow, `${width}px; large text=${largeText}`).toBe(false);
    }
    await page.evaluate(() => (document.documentElement.style.fontSize = ""));
    await page.screenshot({
      path: testInfo.outputPath(`landing-${width}.png`),
      fullPage: true,
    });
  }
});

test("La demo descargada funciona sin red, con fuentes y código embebidos", async ({
  page,
  browser,
}, testInfo) => {
  await page.goto(LANDING);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Descargar el HTML de ejemplo" }).click(),
  ]);
  const file = testInfo.outputPath("atlify-demo.html");
  await download.saveAs(file);
  const context = await browser.newContext({ offline: true });
  const offlinePage = await context.newPage();
  await offlinePage.goto(`file://${file}`);
  await expect(offlinePage.locator("main")).toContainText("pet-care-api");
  await offlinePage.goto(
    `file://${file}#/endpoint/GET%20%2Fapi%2Fappointments/recorrido?paso=3`,
  );
  await expect(offlinePage.locator("main")).toContainText(
    "GET /api/appointments",
  );
  await expect(offlinePage.locator(".codigo").first()).toContainText(
    "def list_for_owner",
  );
  await context.close();
});

test("ScrollTrigger fija la escena y cambia las cuatro vistas sin secuestrar el scroll", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "escritorio",
    "Escena cinematográfica solo en pantallas amplias",
  );
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(LANDING);
  await expect(page.locator("#explorar")).toHaveClass(/scroll-story/);
  for (const [index, key] of [
    "recorrido",
    "mapa",
    "hallazgos",
    "foco",
  ].entries()) {
    await page.evaluate((i) => {
      const trigger = (window as any).ScrollTrigger.getAll().find(
        (t: any) => t.trigger.id === "explorar",
      );
      window.scrollTo({
        top: trigger.start + ((i + 0.25) / 4) * (trigger.end - trigger.start),
        behavior: "instant",
      });
    }, index);
    await expect(page.locator(`button[data-view="${key}"]`)).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const top = await page
      .locator(".scroll-stage")
      .evaluate((el) => el.getBoundingClientRect().top);
    expect(Math.abs(top)).toBeLessThan(3);
    if (index === 1)
      await page.screenshot({ path: testInfo.outputPath("scroll-story.png") });
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("#explorar")).not.toHaveClass(/scroll-story/);
  await expect(page.locator("#preview-image")).toHaveAttribute(
    "src",
    "img/recorrido.png",
  );
});
