import { expect, test } from "@playwright/test";
import path from "node:path";
import { RAIZ } from "./rutas";

// Explicit opt-in: routine tests never rewrite public assets.
test("@release-assets · regenerate public screenshots and social card", async ({
  browser,
}, testInfo) => {
  test.skip(
    process.env.ATLIFY_CAPTURE !== "1" ||
      testInfo.project.name !== "escritorio",
    "Opt in with ATLIFY_CAPTURE=1 and --project=escritorio",
  );
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1040 },
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const endpoint = encodeURIComponent("GET /api/appointments");
  const views = [
    ["resumen", "atlas.html"],
    ["recorrido", `atlas.html#/endpoint/${endpoint}/recorrido?paso=3`],
    [
      "mapa",
      `atlas.html#/mapa?sel=${encodeURIComponent("e:GET /api/appointments")}`,
    ],
    ["hallazgos", "atlas.html#/hallazgos"],
    ["foco", "foco.html"],
  ];
  for (const [name, url] of views) {
    await page.goto(`http://127.0.0.1:4174/demo/${url}`);
    await page.evaluate(() => document.fonts.ready);
    await page.locator("main").waitFor();
    if (name === "recorrido")
      await expect(page.locator(".codigo").first()).toContainText(
        "def list_for_owner",
      );
    if (name === "hallazgos") await page.locator(".hall-cab").first().click();
    if (name === "mapa") await page.waitForTimeout(900); // settle the viewer's layout
    await page.screenshot({
      path: path.join(RAIZ, "docs/img", `${name}.png`),
      animations: "disabled",
    });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(
    `http://127.0.0.1:4174/demo/atlas.html#/endpoint/${endpoint}/recorrido?paso=3`,
  );
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.join(RAIZ, "docs/img/celular.png"),
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1200, height: 630 });
  await page.goto("http://127.0.0.1:4174/social-card.html");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.join(RAIZ, "docs/img/og-atlify.png"),
    animations: "disabled",
  });
  await context.close();
});
