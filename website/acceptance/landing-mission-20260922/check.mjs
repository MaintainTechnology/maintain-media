import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:3118";
const browser = await chromium.launch({ headless: true });
const report = { origin, checkedAt: new Date().toISOString(), checks: [], pageErrors: [] };

try {
  for (const [device, viewport] of Object.entries({
    desktop: { width: 1440, height: 1000 },
    mobile: { width: 390, height: 844 },
  })) {
    const page = await browser.newPage({ viewport, reducedMotion: "reduce" });
    page.on("pageerror", error => report.pageErrors.push({ device, message: error.message, stack: error.stack }));
    // Visual review only: block local form submissions, server actions and APIs.
    await page.route("**/*", route => {
      if (new URL(route.request().url()).origin === origin && !["GET", "HEAD"].includes(route.request().method())) return route.abort();
      return route.continue();
    });

    for (const route of ["/", "/contact"]) {
      const name = route === "/" ? "home" : "contact";
      const response = await page.goto(origin + route, { waitUntil: "networkidle", timeout: 120000 });
      assert.equal(response.status(), 200, `${device} ${name} must respond successfully`);
      await page.evaluate(() => document.fonts.ready);
      await page.getByRole("heading", { level: 1 }).waitFor({ state: "visible" });
      await page.waitForFunction(() => getComputedStyle(document.querySelector("h1")).opacity === "1");
      const sizing = await page.evaluate(() => ({
        viewport: innerWidth,
        width: document.documentElement.scrollWidth,
      }));
      assert.ok(sizing.width <= sizing.viewport, `${device} ${name} horizontal overflow: ${JSON.stringify(sizing)}`);
      if (name === "home") {
        assert.match(await page.title(), /Lead generation for new businesses/);
        await page.getByRole("heading", { name: "Built for the first days of your business." }).waitFor();
        assert.match(await page.locator("main").innerText(), /last 7 days/);
        assert.equal(await page.getByRole("link", { name: "Discuss the partnership", exact: true }).count(), 2);
      } else {
        await page.locator("main").getByRole("link", { name: "+61 414 530 836", exact: true }).waitFor();
        assert.equal(await page.getByLabel("Email address", { exact: true }).getAttribute("type"), "email");
        await page.getByLabel("What are you interested in?").selectOption({ label: "New business lead generation partnership" });
      }
      await page.screenshot({ path: path.join(directory, `${name}-${device}-viewport.png`) });
      // Visit scroll-revealed content before a full-page capture.
      for (const item of await page.locator("main h2, main h3, main form").all()) {
        await item.scrollIntoViewIfNeeded();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.screenshot({ path: path.join(directory, `${name}-${device}-full.png`), fullPage: true });
      report.checks.push({ device, route, status: response.status(), horizontalOverflow: false });
    }

    await page.goto(origin, { waitUntil: "networkidle" });
    await page.waitForFunction(() => getComputedStyle(document.querySelector("h1")).opacity === "1");
    await page.getByRole("link", { name: "See how it works", exact: true }).click();
    await page.waitForURL(`${origin}/#new-business`);
    assert.equal(new URL(page.url()).hash, "#new-business");
    await page.getByRole("link", { name: "Discuss the partnership", exact: true }).first().click();
    await page.waitForURL(`${origin}/contact`);
    report.checks.push({ device, navigation: "mission anchor and partnership contact route", passed: true });
    await page.close();
  }
  assert.deepEqual(report.pageErrors, [], "No browser runtime errors expected");
  report.passed = true;
} finally {
  await writeFile(path.join(directory, "report.json"), JSON.stringify(report, null, 2) + "\n");
  await browser.close();
}

console.log(JSON.stringify(report, null, 2));
