/**
 * Actual dashboard/component React browser check using synthetic engine responses.
 * Run: node website/tests/source-records-browser/check.mjs
 * Only loopback is served. No app routes, credentials, auth bypass, production data,
 * source runs, outreach, or package/lockfile changes are involved.
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const website = path.resolve(directory, "../..");
const require = createRequire(path.join(website, "package.json"));
const { chromium } = require("playwright");
const webpack = require("next/dist/compiled/webpack/webpack").webpack;
const output = await mkdtemp(path.join(tmpdir(), "maintain-source-records-ui-"));
const transpiler = require.resolve("typescript");
const loader = path.join(output, "transpile.cjs");
await writeFile(loader, `const ts = require(${JSON.stringify(transpiler)}); module.exports = function(source) { return ts.transpileModule(source, {compilerOptions:{jsx:ts.JsxEmit.ReactJSX, target:ts.ScriptTarget.ES2020, module:ts.ModuleKind.ESNext}}).outputText; };`);
const cssLoader = path.join(output, "css.cjs");
await writeFile(cssLoader, `module.exports = function(source) { const classes = [...source.matchAll(/\\.([a-zA-Z_][\\w-]*)/g)].map(match => [match[1],match[1]]); return 'module.exports = ' + JSON.stringify(Object.fromEntries(classes)); };`);
const mocks = path.join(directory, "framework-mocks.jsx");
const imageMock = path.join(output, "image.jsx");
const linkMock = path.join(output, "link.jsx");
await writeFile(imageMock, `export { Image as default } from ${JSON.stringify(mocks)};`);
await writeFile(linkMock, `export { Link as default } from ${JSON.stringify(mocks)};`);
await new Promise((resolve, reject) => {
  const compiler = webpack({
  mode: "development", devtool: false, context: website,
  entry: path.join(directory, "harness.jsx"), output: { path: output, filename: "bundle.js" },
  resolve: { extensions: [".tsx", ".ts", ".jsx", ".js", ".json"], modules: [path.join(website, "node_modules"), "node_modules"],
    alias: { "@": path.join(website, "src"), "next/image$": imageMock, "next/link$": linkMock,
      "@clerk/nextjs$": mocks, [path.join(website, "src/components/abn-lead-gen/use-dashboard.ts")]: mocks } },
  module: { rules: [{ test: /\.[jt]sx?$/, exclude: /node_modules/, use: loader }, { test: /\.css$/, use: cssLoader }] },
}, (error, stats) => compiler.close(() => error || stats.hasErrors() ? reject(error || new Error(stats.toString({ all: false, errors: true }))) : resolve()));
});

const baseCss = `@font-face{font-family:Albert;src:url('/albert.ttf')}*{box-sizing:border-box}html,body{margin:0;padding:0}body{--font-sans:Albert,system-ui,sans-serif;background:#061518}button,input,select{font:inherit}`;
const css = baseCss + await readFile(path.join(website, "src/components/abn-lead-gen/dashboard.module.css"), "utf8");
const bundle = await readFile(path.join(output, "bundle.js"));
const font = await readFile(path.join(website, "src/fonts/AlbertSans-VariableFont_wght.ttf"));
const logo = await readFile(path.join(website, "public/brand/logo-darkbg.svg"));
const server = createServer((request, response) => {
  const resources = { "/bundle.js": ["application/javascript", bundle], "/style.css": ["text/css", css],
    "/albert.ttf": ["font/ttf", font], "/brand/logo-darkbg.svg": ["image/svg+xml", logo] };
  const [mime, body] = resources[request.url] || ["text/html", '<!doctype html><html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/style.css"></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>'];
  response.writeHead(200, { "Content-Type": mime, "Cache-Control": "no-store" }); response.end(body);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
const errors = [];
page.on("pageerror", error => errors.push(error.message));
await page.route("**/*", route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
const checks = [];
async function check(name, action) { await action(); checks.push({ name, status: "passed" }); }
const sourceReview = source => page.locator(`#${source.toLowerCase()}-source-records`);
const selected = source => page.locator('#view-sources').getByRole('button', { name: source, exact: true });
const openSources = async () => {
  await page.getByRole('link', { name: 'Source records', exact: true }).click();
  await sourceReview('ABR').waitFor();
};
const lastRequest = () => page.evaluate(() => {
  const item = globalThis.sourceHarness.requests.at(-1);
  return { path: item.path, ...JSON.parse(item.options?.body || '{}') };
});
const search = source => sourceReview(source).getByRole('searchbox');
const apply = source => sourceReview(source).getByRole('button', { name: 'Apply filters', exact: true });
const reset = source => sourceReview(source).getByRole('button', { name: /Reset|Clear filters/ });
const leadsList = () => page.getByRole('region', { name: 'Leads list.', exact: true });
const listSource = source => leadsList().getByRole('region', { name: `${source} businesses`, exact: true });
const listRows = source => listSource(source).getByRole('button', { name: /^Synthetic (ABR|QBCC) business / });
const openLeadsList = async () => {
  await page.getByRole('button', { name: /^Leads list/ }).click();
  await leadsList().getByRole('button', { name: 'All businesses', exact: true }).waitFor();
};
try {
  await page.goto(origin);
  await check('Latest leads discovers candidates automatically while full Source records stays separate', async () => {
    assert.equal(await page.getByRole('link', { name: 'Source records', exact: true }).isVisible(), true);
    assert.equal(await sourceReview('ABR').count(), 0);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.getByText('Website not checked', { exact: true }).first().waitFor();
    const initialQuery = await page.evaluate(() => JSON.parse(globalThis.sourceHarness.requests.find(item => item.path === 'source-records/query').options.body));
    assert.equal(initialQuery.sort, 'status_date_desc');
    assert.equal((Date.parse(initialQuery.filters.status_date_to) - Date.parse(initialQuery.filters.status_date_from)) / 86400000, 29);
    await openSources();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    assert.equal(new URL(page.url()).hash, '#sources');
    for (const source of ['ABR', 'QBCC']) assert.equal(await selected(source).isVisible(), true);
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 50);
    const request = await lastRequest();
    assert.equal(request.path, 'source-records/query');
    assert.equal(request.source, 'abr');
    assert.equal(request.offset, 0);
  });
  await check('ABR table displays all 14 parsed columns and links its ABN to current ABN Lookup', async () => {
    assert.equal(await sourceReview('ABR').locator('thead th').count(), 14);
    const row = sourceReview('ABR').locator('tbody tr').first();
    assert.match(await row.innerText(), /Synthetic registered business name/);
    assert.match(await row.innerText(), /20260914_Public01.xml/);
    assert.match(await row.innerText(), new RegExp('a'.repeat(64)));
    const links = await row.locator('a[href]').evaluateAll(elements => elements.map(element => element.href));
    assert.ok(links.some(link => new URL(link).hostname === 'abr.business.gov.au' && link.includes('10000000000')));
  });
  await check('Source pagination remains pinned to the accepted run', async () => {
    await sourceReview('ABR').getByRole('button', { name: /Next/ }).click();
    await page.getByText('Synthetic ABR business 51', { exact: true }).waitFor();
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 2);
    assert.equal((await lastRequest()).run_id, '2f634182-1111-4111-8111-111111111111');
    assert.equal((await lastRequest()).offset, 50);
    await sourceReview('ABR').getByRole('button', { name: /Previous/ }).click();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
  });
  await check('Name and ABN searches apply to the source publication and reset pagination', async () => {
    await search('ABR').fill('Synthetic ABR business 52');
    await apply('ABR').click();
    await page.getByText('Synthetic ABR business 52', { exact: true }).waitFor();
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 1);
    assert.equal((await lastRequest()).offset, 0);
    assert.equal((await lastRequest()).filters.query, 'Synthetic ABR business 52');
    await search('ABR').fill('10000000000');
    await search('ABR').press('Enter');
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 1);
    await search('ABR').fill('Synthetic registered business name');
    await apply('ABR').click();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    assert.equal((await lastRequest()).filters.query, 'Synthetic registered business name');
    await reset('ABR').click();
    await page.waitForFunction(() => document.querySelectorAll('#abr-source-records tbody tr').length === 50);
  });
  await check('Missing GST filter submits the stored NONE value and displays Not supplied', async () => {
    await sourceReview('ABR').locator('#abr-filter-gst_status').selectOption('NONE');
    await apply('ABR').click();
    await page.getByText('Synthetic ABR business 52', { exact: true }).waitFor();
    assert.equal((await lastRequest()).filters.gst_status, 'NONE');
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 1);
    assert.match(await sourceReview('ABR').locator('tbody tr').first().innerText(), /Not supplied/);
    await reset('ABR').click();
    await page.waitForFunction(() => document.querySelectorAll('#abr-source-records tbody tr').length === 50);
  });
  await check('Stored field filters and full versus filtered CSV keep distinct request bodies', async () => {
    await sourceReview('ABR').locator('#abr-filter-state').selectOption('QLD');
    await apply('ABR').click();
    await page.waitForFunction(() => document.querySelectorAll('#abr-source-records tbody tr').length === 26);
    assert.equal((await lastRequest()).filters.state, 'QLD');
    await sourceReview('ABR').getByRole('button', { name: /Export filtered CSV|Download filtered CSV/ }).click();
    await page.waitForFunction(() => globalThis.sourceHarness.downloads.length === 1);
    assert.equal((await lastRequest()).path, 'source-exports');
    assert.equal((await lastRequest()).filters.state, 'QLD');
    await sourceReview('ABR').getByRole('button', { name: /Export all CSV|Download all CSV/ }).click();
    await page.waitForFunction(() => globalThis.sourceHarness.downloads.length === 2);
    assert.ok(Object.values((await lastRequest()).filters).every(value => !value));
    const downloads = await page.evaluate(() => globalThis.sourceHarness.downloads);
    for (const download of downloads) {
      assert.equal(download.method.toLowerCase(), 'post');
      assert.equal(download.action, 'https://abn-engine.maintainmedia.com.au/api/source-exports/download');
      assert.equal(download.fields.ticket, 'synthetic-local-download-ticket-0123456789');
    }
    await reset('ABR').click();
    await page.waitForFunction(() => document.querySelectorAll('#abr-source-records tbody tr').length === 50);
  });
  await check('QBCC autoloads with all 17 parsed columns, nested licence data and unknown status', async () => {
    await selected('QBCC').click();
    await page.getByText('Synthetic QBCC business 1', { exact: true }).waitFor();
    assert.equal(await sourceReview('ABR').count(), 0);
    assert.equal(await sourceReview('QBCC').locator('thead th').count(), 17);
    const row = sourceReview('QBCC').locator('tbody tr').first();
    assert.match(await row.innerText(), /Builder - Low Rise/);
    assert.match(await row.innerText(), /Carpentry/);
    assert.match(await row.innerText(), /600000000/);
    assert.match(await row.innerText(), /Not supplied/);
    assert.match(await row.innerText(), /UNKNOWN/);
    assert.doesNotMatch(await row.innerText(), /Active/);
  });
  await check('Completed runs open their corresponding source and exact run on Source records', async () => {
    await page.getByRole('link', { name: 'Run history', exact: true }).click();
    await page.locator('#run-list tr').filter({ hasText: '2f634182' }).getByRole('button', { name: 'View source records', exact: true }).click();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    assert.equal(new URL(page.url()).hash, '#sources');
    assert.equal(await selected('ABR').getAttribute('aria-pressed'), 'true');
    assert.equal((await lastRequest()).run_id, '2f634182-1111-4111-8111-111111111111');
  });
  for (const width of [375, 768, 1024, 1440]) {
    await check(`Source navigation, filters and bounded table fit ${width}px`, async () => {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate(() => document.fonts.ready);
      for (const source of ['ABR', 'QBCC']) assert.equal(await selected(source).isVisible(), true);
      const dimensions = await page.evaluate(() => ({ viewport: innerWidth, page: document.documentElement.scrollWidth }));
      assert.ok(dimensions.page <= dimensions.viewport + 1, JSON.stringify(dimensions));
      const region = sourceReview('ABR').getByRole('region', { name: 'ABR source records table', exact: true });
      const size = await region.evaluate(element => ({ height: element.clientHeight, fullHeight: element.scrollHeight, width: element.clientWidth, fullWidth: element.scrollWidth, viewport: innerHeight }));
      assert.ok(size.fullHeight > size.height && size.height <= size.viewport * 0.65 + 1, JSON.stringify(size));
      assert.ok(size.fullWidth > size.width, JSON.stringify(size));
      assert.equal(await region.locator('thead th').first().evaluate(element => getComputedStyle(element).position), 'sticky');
      await page.screenshot({ path: path.join(output, `source-records-${width}.png`), fullPage: true });
      await sourceReview('ABR').evaluate(element => element.scrollIntoView({ block: 'start' }));
      await page.screenshot({ path: path.join(output, `source-table-${width}.png`) });
    });
  }
  await check('A late ABR query cannot overwrite the selected QBCC source', async () => {
    await page.goto(origin);
    await page.evaluate(() => { globalThis.sourceHarness.delay = true; });
    await openSources();
    await page.waitForFunction(() => globalThis.sourceHarness.pending.length === 1);
    await page.evaluate(() => { globalThis.sourceHarness.delay = false; });
    await selected('QBCC').click();
    await page.getByText('Synthetic QBCC business 1', { exact: true }).waitFor();
    await page.evaluate(() => globalThis.sourceHarness.release());
    assert.equal(await page.getByText('Synthetic ABR business 1', { exact: true }).count(), 0);
    assert.equal(await page.getByText('Synthetic QBCC business 1', { exact: true }).isVisible(), true);
  });
  await check('Pending source queries disable filter edits and allow the next search after completion', async () => {
    await selected('ABR').click();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.delay = true; });
    await search('ABR').fill('Synthetic ABR business 52');
    await apply('ABR').click();
    await page.waitForFunction(() => globalThis.sourceHarness.pending.length === 1);
    assert.equal(await search('ABR').isDisabled(), true);
    assert.equal(await sourceReview('ABR').locator('#abr-filter-state').isDisabled(), true);
    assert.equal(await apply('ABR').isDisabled(), true);
    await page.evaluate(() => { globalThis.sourceHarness.delay = false; globalThis.sourceHarness.release(); });
    await page.getByText('Synthetic ABR business 52', { exact: true }).waitFor();
    await search('ABR').fill('Synthetic ABR business 51');
    await search('ABR').press('Enter');
    await page.getByText('Synthetic ABR business 51', { exact: true }).waitFor();
    assert.equal(await page.getByText('Synthetic ABR business 52', { exact: true }).count(), 0);
  });
  await check('A late run response cannot replace the newly selected latest publication', async () => {
    await page.goto(origin);
    await openSources();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.mode = 'expired'; globalThis.sourceHarness.delay = true; });
    await sourceReview('ABR').locator('#abr-record-run').selectOption('2f634182-1111-4111-8111-111111111111');
    await page.waitForFunction(() => globalThis.sourceHarness.pending.length === 1);
    await page.evaluate(() => { globalThis.sourceHarness.mode = 'available'; globalThis.sourceHarness.delay = false; });
    await sourceReview('ABR').locator('#abr-record-run').selectOption('latest');
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    await page.evaluate(() => globalThis.sourceHarness.release());
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 50);
    assert.equal(await sourceReview('ABR').getByText(/no longer retained/).count(), 0);
  });
  for (const [state, message] of [['expired', /no longer retained/], ['not_collected', /No current accepted ABR publication/]]) {
    await check(`${state} publication has an honest empty state`, async () => {
      await page.goto(origin);
      await page.evaluate(value => { globalThis.sourceHarness.mode = value; }, state);
      await openSources();
      await sourceReview('ABR').getByText(message).waitFor();
      assert.equal(await sourceReview('ABR').locator('table').count(), 0);
    });
  }
  await check('Source page failures preserve the last successful table', async () => {
    await page.goto(origin);
    await openSources();
    await page.getByText('Synthetic ABR business 1', { exact: true }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.error = 'Synthetic connection interruption'; });
    await sourceReview('ABR').getByRole('button', { name: /Next/ }).click();
    await sourceReview('ABR').getByRole('alert').waitFor();
    assert.equal(await sourceReview('ABR').locator('tbody tr').count(), 50);
  });
  await check('Recent active registrations use server filters and a compact research view', async () => {
    await page.goto(origin); await openSources();
    await sourceReview('ABR').getByRole('button', { name: 'Last 7 days', exact: true }).click();
    await page.getByRole('button', { name: 'Research business', exact: true }).first().waitFor();
    const request = await lastRequest();
    assert.equal(request.filters.status, 'ACT');
    assert.equal((Date.parse(request.filters.status_date_to) - Date.parse(request.filters.status_date_from)) / 86400000, 6);
    assert.equal(await page.getByRole('button', { name: 'Research business', exact: true }).count(), 3);
    await page.getByText(/Includes registrations and possible reactivations/).waitFor();
    await page.screenshot({ path: path.join(output, 'prospect-discovery-1440.png'), fullPage: true });
  });
  await check('Research starts unknown and persists evidence, first registration and follow-up', async () => {
    await page.getByRole('button', { name: 'Research business', exact: true }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Website presence').waitFor();
    assert.equal(await dialog.getByLabel('Website presence').inputValue(), 'unknown');
    assert.equal(await dialog.getByLabel('Verified first registration date').inputValue(), '');
    await dialog.getByLabel('Website presence').selectOption('absent');
    await dialog.getByLabel('Email presence').selectOption('absent');
    await dialog.getByLabel('Social media', { exact: true }).selectOption('absent');
    await dialog.getByLabel('Research evidence / source reference').fill('Synthetic owner conversation, confirms no digital presence');
    const today = (await page.evaluate(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'Australia/Brisbane' }).format(new Date())));
    await dialog.getByLabel('Verified first registration date').fill(today);
    await dialog.getByLabel('Registration evidence', { exact: true }).fill('Synthetic ABN history check');
    await dialog.getByLabel('Contact stage').selectOption('follow_up');
    await dialog.getByLabel('Follow-up date').fill(today);
    await dialog.getByLabel('Research & conversation notes').fill('Would like to discuss the zero-cost-to-start partnership.');
    await dialog.getByRole('button', { name: 'Save research', exact: true }).click();
    await dialog.getByText('Research saved. Find this business in Saved prospects.').waitFor();
    await page.screenshot({ path: path.join(output, 'prospect-research-1440.png'), fullPage: true });
    await dialog.getByRole('button', { name: 'Close research' }).click();
    await page.getByRole('link', { name: 'Saved prospects', exact: true }).click();
    await page.getByRole('heading', { name: '1 matching prospects' }).waitFor();
    await page.getByRole('button', { name: 'Target match · 7 days' }).click();
    await page.getByRole('button', { name: /Synthetic ABR business 1/ }).waitFor();
    await page.getByRole('button', { name: 'Follow-ups due', exact: true }).click();
    await page.getByRole('button', { name: /Synthetic ABR business 1/ }).waitFor();
  });
  await check('Existing research edits omit read-only fields and failed saves preserve notes', async () => {
    await page.getByRole('button', { name: /Synthetic ABR business 1/ }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Research & conversation notes').fill('Second research update');
    await page.evaluate(() => { globalThis.sourceHarness.saveError = 'Synthetic save interruption'; });
    await dialog.getByRole('button', { name: 'Save research', exact: true }).click();
    await dialog.getByRole('alert').waitFor();
    assert.equal(await dialog.getByLabel('Research & conversation notes').inputValue(), 'Second research update');
    await page.evaluate(() => { globalThis.sourceHarness.saveError = null; });
    await dialog.getByRole('button', { name: 'Save research', exact: true }).click();
    await dialog.getByText('Research saved. Find this business in Saved prospects.').waitFor();
    assert.equal(await page.evaluate(() => Object.values(globalThis.sourceHarness.prospects)[0].revision), 2);
    await dialog.getByRole('button', { name: 'Close research' }).click();
    await page.getByRole('button', { name: 'No website', exact: true }).click();
    await page.getByLabel('Website', { exact: true }).selectOption('');
    await page.getByRole('button', { name: 'Apply prospect filters' }).click();
    await page.getByRole('heading', { name: '1 matching prospects' }).waitFor();
    assert.equal(await page.getByRole('alert').filter({ hasText: 'Empty filter' }).count(), 0);
  });
  await check('Unknown presence is excluded and research dialog preserves unsaved work', async () => {
    await page.evaluate(() => { const h = globalThis.sourceHarness; const first = Object.values(h.prospects)[0]; h.prospects['10000000001'] = { ...first, abn: '10000000001', business_name: 'Synthetic unknown presence', website_presence: 'unknown', email_presence: 'unknown', social_presence: 'unknown' }; });
    await page.getByRole('button', { name: 'All saved', exact: true }).click();
    await page.getByRole('heading', { name: '2 matching prospects' }).waitFor();
    await page.getByRole('button', { name: 'No digital presence', exact: true }).click();
    await page.getByRole('heading', { name: '1 matching prospects' }).waitFor();
    await page.getByRole('button', { name: /Synthetic ABR business 1/ }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Research & conversation notes').fill('Keep this unsaved text');
    page.once('dialog', prompt => prompt.dismiss());
    await page.keyboard.press('Escape');
    assert.equal(await dialog.isVisible(), true);
    assert.equal(await dialog.getByLabel('Research & conversation notes').inputValue(), 'Keep this unsaved text');
    for (const width of [820, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      assert.equal(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
      await page.screenshot({ path: path.join(output, `prospect-research-${width}.png`), fullPage: true });
    }
    page.once('dialog', prompt => prompt.accept());
    await dialog.getByRole('button', { name: 'Close research' }).click();
    for (const link of await page.locator('nav a').all()) {
      assert.equal(await link.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true, 'Navigation label must fit its own button');
    }
    await page.screenshot({ path: path.join(output, 'saved-prospects-320.png'), fullPage: true });
  });
  await check('Latest leads defaults to broad discovery and keeps the single 100-score record secondary', async () => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(origin);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.getByText('Website not checked', { exact: true }).first().waitFor();
    assert.equal(await page.getByRole('button', { name: /^New · 30 days/ }).getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('#view-leads article').count(), 3);
    assert.equal(await page.locator('#view-leads article h3').first().innerText(), 'Synthetic ABR business 3');
    assert.equal(await page.getByText('100/100', { exact: true }).isVisible(), false);
    assert.equal(await page.locator('#nav-count').count(), 0);
    await openLeadsList();
    await leadsList().getByRole('button', { name: 'Qualification reviews', exact: true }).click();
    await page.getByText('100/100', { exact: true }).waitFor();
    assert.equal(await page.getByText('Previously reviewed business', { exact: true }).first().isVisible(), true);
    await page.getByRole('button', { name: /^New · 7 days/ }).click();
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.getByText('Publication predates this window', { exact: true }).waitFor();
  });
  await check('Discovery pagination is globally newest first and bound to its accepted publication', async () => {
    await page.evaluate(() => { globalThis.sourceHarness.freshAll = true; });
    await page.getByRole('button', { name: /^New · 30 days/ }).click();
    await page.getByRole('heading', { name: '52 recent candidates' }).waitFor();
    await page.getByRole('button', { name: 'Next 50', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('#view-leads article').length === 2);
    const query = await page.evaluate(() => JSON.parse(globalThis.sourceHarness.requests.filter(item => item.path === 'source-records/query').at(-1).options.body));
    assert.equal(query.run_id, '2f634182-1111-4111-8111-111111111111'); assert.equal(query.sort, 'status_date_desc'); assert.equal(query.offset, 50);
    await page.getByRole('button', { name: 'Previous 50', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('#view-leads article').length === 50);
    assert.equal(await page.locator('#view-leads article h3').first().innerText(), 'Synthetic ABR business 3');
  });
  await check('No website is independent of business age, email, social presence and qualification score', async () => {
    await page.evaluate(() => {
      const base = { abn: '10000000000', business_name: 'Established business without website', source: 'abr', snapshot_id: '33333333-3333-4333-8333-333333333333', run_id: '2f634182-1111-4111-8111-111111111111', revision: 1, saved_at: new Date().toISOString(), website_presence: 'absent', email_presence: 'present', social_presence: 'present', website_url: '', email: 'synthetic@example.invalid', phone: '', social_url: 'https://example.invalid/profile', evidence_ref: 'Synthetic conversation', research_note: '', contact_stage: 'not_interested', follow_up_on: null, registration_date: '2019-01-02', registration_evidence_ref: 'Synthetic history' };
      globalThis.sourceHarness.prospects = { [base.abn]: base, '10000000001': { ...base, abn: '10000000001', business_name: 'Unchecked business', website_presence: 'unknown', contact_stage: 'not_contacted' }, '10000000002': { ...base, abn: '10000000002', business_name: 'Business with website', website_presence: 'present', website_url: 'https://example.invalid', contact_stage: 'interested' } };
    });
    await page.getByRole('button', { name: /^No website/ }).click();
    await page.getByRole('heading', { name: '1 saved businesses' }).waitFor();
    await page.getByRole('heading', { name: 'Established business without website', exact: true }).waitFor();
    await page.getByText('Not interested', { exact: true }).waitFor();
    assert.equal(await page.getByRole('heading', { name: 'Unchecked business', exact: true }).count(), 0);
    await page.getByRole('button', { name: /^Website unchecked/ }).click();
    await page.getByRole('heading', { name: 'Unchecked business', exact: true }).waitFor();
    await page.getByRole('button', { name: /^New · 7 days/ }).click();
    await page.getByText('Website found', { exact: true }).waitFor();
    await page.getByText('Interested', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(output, 'latest-leads-desktop.png'), fullPage: true });
  });
  await check('Unavailable research never turns into a false missing-website claim', async () => {
    await page.evaluate(() => { globalThis.sourceHarness.researchError = 'Synthetic research outage'; });
    await page.getByRole('button', { name: 'Refresh leads', exact: true }).click();
    await page.getByText('Research unavailable', { exact: true }).first().waitFor();
    assert.equal(await page.locator('#view-leads article').count(), 3);
    assert.equal(await page.getByText('Website not checked', { exact: true }).count(), 0);
    await page.evaluate(() => { globalThis.sourceHarness.researchError = null; });
    await page.getByRole('button', { name: 'Refresh leads', exact: true }).click();
    await page.getByText('Website found', { exact: true }).waitFor();
    for (const width of [820, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      for (const button of await page.getByRole('group', { name: 'Choose lead focus' }).getByRole('button').all()) {
        assert.equal(await button.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
      }
      await page.screenshot({ path: path.join(output, `latest-leads-${width}.png`), fullPage: true });
    }
  });
  await check('Research saved from Latest leads updates its website and contact outcome', async () => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: /^New · 30 days/ }).click();
    await page.getByText('Website found', { exact: true }).waitFor();
    const first = page.locator('#view-leads article').first();
    await first.getByRole('button', { name: 'Open research', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Website URL').fill('');
    await dialog.getByLabel('Website presence').selectOption('absent');
    await dialog.getByLabel('Contact stage').selectOption('contacted');
    page.once('dialog', prompt => prompt.dismiss());
    await page.evaluate(() => { window.location.hash = 'sources'; });
    await page.waitForFunction(() => window.location.hash === '#leads');
    assert.equal(await dialog.isVisible(), true, 'Declined navigation keeps unsaved modal visible');
    await dialog.getByRole('button', { name: 'Save research', exact: true }).click();
    await dialog.getByText('Research saved. Find this business in Saved prospects.').waitFor();
    await dialog.getByRole('button', { name: 'Close research' }).click();
    await first.getByText('No website · confirmed', { exact: true }).waitFor();
    await first.getByText('Contacted', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(output, 'latest-leads-default-30-days.png'), fullPage: false });
  });
  await check('Late recent-source response cannot overwrite the chosen saved research focus', async () => {
    await page.evaluate(() => { globalThis.sourceHarness.delay = true; });
    await page.getByRole('button', { name: /^New · 7 days/ }).click();
    await page.waitForFunction(() => globalThis.sourceHarness.pending.length > 0);
    await page.getByRole('button', { name: /^No website/ }).click();
    await page.getByRole('heading', { name: '2 saved businesses' }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.delay = false; globalThis.sourceHarness.release(); });
    assert.equal(await page.getByRole('heading', { name: '2 saved businesses' }).isVisible(), true);
    assert.equal(await page.getByRole('button', { name: /^No website/ }).getAttribute('aria-pressed'), 'true');
  });
  await check('Leads list shows 100 unscored publication rows even when only one Tier A business was qualified', async () => {
    await page.goto(origin);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.requests = []; });
    await openLeadsList();
    await listRows('ABR').nth(49).waitFor();
    await listRows('QBCC').nth(49).waitFor();
    assert.equal(await leadsList().getByRole('button', { name: 'All businesses', exact: true }).getAttribute('aria-pressed'), 'true');
    assert.equal(await listRows('ABR').count() + await listRows('QBCC').count(), 100);
    assert.equal(await page.evaluate(() => globalThis.sourceHarness.engine.data.leads.length), 1);
    assert.equal(await leadsList().getByText('100/100', { exact: true }).isVisible(), false);
    const queries = await page.evaluate(() => globalThis.sourceHarness.requests.filter(item => item.path === 'source-records/query').map(item => JSON.parse(item.options.body)));
    assert.deepEqual(queries.map(query => query.source).sort(), ['abr', 'qbcc']);
    for (const query of queries) { assert.deepEqual(query.filters, {}); assert.equal(query.sort || 'source_order', 'source_order'); assert.equal(query.offset, 0); }
    await page.screenshot({ path: path.join(output, 'leads-list-desktop.png'), fullPage: true });
  });
  await check('ABR and QBCC list pagination use independent offsets pinned to the accepted publications', async () => {
    await leadsList().getByRole('button', { name: 'Next ABR 50', exact: true }).click();
    await listSource('ABR').getByText('Synthetic ABR business 51', { exact: true }).waitFor();
    assert.equal(await listRows('ABR').count(), 2);
    assert.equal(await listRows('QBCC').count(), 50);
    let request = await lastRequest();
    assert.equal(request.source, 'abr'); assert.equal(request.offset, 50); assert.equal(request.run_id, '2f634182-1111-4111-8111-111111111111');
    await leadsList().getByRole('button', { name: 'Next QBCC 50', exact: true }).click();
    await listSource('QBCC').getByText('Synthetic QBCC business 51', { exact: true }).waitFor();
    assert.equal(await listRows('ABR').count(), 2);
    assert.equal(await listRows('QBCC').count(), 2);
    request = await lastRequest();
    assert.equal(request.source, 'qbcc'); assert.equal(request.offset, 50); assert.equal(request.run_id, '692faa4e-2222-4222-8222-222222222222');
    await leadsList().getByRole('button', { name: 'Previous ABR 50', exact: true }).click();
    await listRows('ABR').nth(49).waitFor();
    assert.equal(await listRows('QBCC').count(), 2);
  });
  await check('Leads list search queries both full publications and resets each source page', async () => {
    await leadsList().getByLabel('Search lead list', { exact: true }).fill('business 52');
    await leadsList().getByRole('button', { name: 'Search businesses', exact: true }).click();
    await listSource('ABR').getByText('Synthetic ABR business 52', { exact: true }).waitFor();
    await listSource('QBCC').getByText('Synthetic QBCC business 52', { exact: true }).waitFor();
    assert.equal(await listRows('ABR').count(), 1);
    assert.equal(await listRows('QBCC').count(), 1);
    const queries = await page.evaluate(() => globalThis.sourceHarness.requests.filter(item => item.path === 'source-records/query').slice(-2).map(item => JSON.parse(item.options.body)));
    assert.deepEqual(queries.map(query => query.source).sort(), ['abr', 'qbcc']);
    for (const query of queries) { assert.equal(query.filters.query, 'business 52'); assert.equal(query.offset, 0); }
    await leadsList().getByLabel('Search lead list', { exact: true }).fill('10 000 000 001');
    await leadsList().getByLabel('Search lead list', { exact: true }).press('Enter');
    await listSource('ABR').getByText('Synthetic ABR business 2', { exact: true }).waitFor();
    assert.equal(await listRows('ABR').count(), 1);
    assert.equal(await listRows('QBCC').count(), 0);
    assert.ok(['10 000 000 001', '10000000001'].includes((await lastRequest()).filters.query));
    await leadsList().getByLabel('Search lead list', { exact: true }).fill('');
    await leadsList().getByRole('button', { name: 'Search businesses', exact: true }).click();
    await listRows('ABR').nth(49).waitFor(); await listRows('QBCC').nth(49).waitFor();
  });
  await check('Lead list source controls select ABR and QBCC without qualification or recency requirements', async () => {
    const sourceButtons = leadsList().getByRole('group', { name: 'Lead list sources', exact: true });
    await sourceButtons.getByRole('button', { name: 'QBCC', exact: true }).click();
    await listRows('QBCC').nth(49).waitFor();
    assert.equal(await listSource('ABR').isVisible(), false);
    await sourceButtons.getByRole('button', { name: 'ABR', exact: true }).click();
    await listRows('ABR').nth(49).waitFor();
    assert.equal(await listSource('QBCC').isVisible(), false);
    await sourceButtons.getByRole('button', { name: 'All sources', exact: true }).click();
    await listRows('ABR').nth(49).waitFor(); await listRows('QBCC').nth(49).waitFor();
  });
  await check('An unscored business opens editable research and is saved to Saved prospects', async () => {
    await listRows('ABR').filter({ hasText: 'Synthetic ABR business 2' }).first().click();
    await leadsList().getByRole('button', { name: 'Research selected business', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Website presence').waitFor();
    assert.equal(await dialog.getByLabel('Website presence').inputValue(), 'unknown');
    await dialog.getByLabel('Website presence').selectOption('absent');
    await dialog.getByLabel('Research evidence / source reference').fill('Synthetic business-owner confirmation for unscored source record');
    await dialog.getByLabel('Research & conversation notes').fill('New conversation from the broad leads list');
    await dialog.getByRole('button', { name: 'Save research', exact: true }).click();
    await dialog.getByText('Research saved. Find this business in Saved prospects.').waitFor();
    await dialog.getByRole('button', { name: 'Close research' }).click();
    assert.equal(await page.evaluate(() => globalThis.sourceHarness.prospects['10000000001'].website_presence), 'absent');
    await page.getByRole('link', { name: 'Saved prospects', exact: true }).click();
    await page.getByRole('heading', { name: '1 matching prospects' }).waitFor();
    await page.getByRole('button', { name: /Synthetic ABR business 2/ }).waitFor();
    await page.getByRole('link', { name: 'Latest leads', exact: true }).click();
    await openLeadsList();
  });
  await check('Qualification reviews accepts Tier B and C scores while every source business stays browsable', async () => {
    await page.evaluate(() => {
      const dashboard = globalThis.sourceHarness.engine.data;
      dashboard.leads.push(
        { lead_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', abn: '10000000001', business_name: 'Lower-score Tier B business', source: 'abr', score: 62, tier: 'B' },
        { lead_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', abn: '20000000001', business_name: 'Lower-score Tier C business', source: 'qbcc', score: 25, tier: 'C' },
      );
      dashboard.summary.total_leads = 3;
    });
    await page.getByRole('link', { name: 'Setup and settings', exact: true }).click();
    await page.getByRole('link', { name: 'Latest leads', exact: true }).click();
    await openLeadsList();
    await leadsList().getByRole('button', { name: 'Qualification reviews', exact: true }).click();
    await page.getByText('62/100', { exact: true }).waitFor();
    await page.getByText('25/100', { exact: true }).waitFor();
    assert.equal(await page.locator('#lead-list > button').count(), 3);
    await page.locator('#tier-filter').selectOption('B');
    assert.equal(await page.locator('#lead-list > button').count(), 1);
    await page.locator('#lead-list').getByText('Lower-score Tier B business', { exact: true }).waitFor();
    await page.locator('#tier-filter').selectOption('C');
    await page.locator('#lead-list').getByText('Lower-score Tier C business', { exact: true }).waitFor();
    await page.locator('#tier-filter').selectOption('all');
    await leadsList().getByRole('button', { name: 'All businesses', exact: true }).click();
    await listRows('ABR').nth(49).waitFor(); await listRows('QBCC').nth(49).waitFor();
  });
  await check('A QBCC record without an ABN cannot inherit another unlinked business score or open research', async () => {
    await page.goto(origin);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.evaluate(() => {
      const h = globalThis.sourceHarness;
      h.qbccMissingAbn = true;
      h.engine.data.leads.push({ lead_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', abn: null, business_name: 'Unrelated business without ABN', source: 'qbcc', score: 100, tier: 'A' });
    });
    await openLeadsList();
    const row = listRows('QBCC').first();
    await row.waitFor();
    assert.match(await row.innerText(), /Source candidate/);
    assert.doesNotMatch(await row.innerText(), /Tier A|100\/100/);
    await row.click();
    const detail = leadsList().getByRole('region', { name: 'Selected business details', exact: true });
    await detail.getByText('ABN not supplied', { exact: true }).waitFor();
    await detail.getByText('1000000', { exact: true }).waitFor();
    assert.equal(await detail.getByRole('button', { name: 'Research selected business', exact: true }).isDisabled(), true);
    assert.doesNotMatch(await detail.innerText(), /Tier A|100\/100/);
  });
  await check('Late broad-list responses cannot overwrite a newly selected recent-lead focus', async () => {
    await page.goto(origin);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.delay = true; });
    await openLeadsList();
    await page.waitForFunction(() => globalThis.sourceHarness.pending.length === 2);
    await page.evaluate(() => { globalThis.sourceHarness.delay = false; });
    await page.getByRole('button', { name: /^New · 7 days/ }).click();
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.evaluate(() => globalThis.sourceHarness.release());
    assert.equal(await page.locator('#view-leads article').count(), 3);
    assert.equal(await page.getByRole('button', { name: /^New · 7 days/ }).getAttribute('aria-pressed'), 'true');
    assert.equal(await listSource('ABR').isVisible(), false);
  });
  await check('One failed source does not hide businesses returned by the other publication', async () => {
    await page.goto(origin);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await page.evaluate(() => { globalThis.sourceHarness.sourceErrors.qbcc = 'Synthetic QBCC interruption'; });
    await openLeadsList();
    await listRows('ABR').nth(49).waitFor();
    await listSource('QBCC').getByRole('alert').waitFor();
    assert.equal(await listRows('ABR').count(), 50);
    assert.equal(await listRows('QBCC').count(), 0);
  });
  await check('Lead list rows, filters and selected-business details fit desktop and small phones', async () => {
    await page.goto(origin);
    await page.getByRole('heading', { name: '3 recent candidates' }).waitFor();
    await openLeadsList(); await listRows('ABR').nth(49).waitFor(); await listRows('QBCC').nth(49).waitFor();
    for (const width of [1440, 820, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      assert.equal(await leadsList().getByLabel('Search lead list', { exact: true }).isVisible(), true);
      await leadsList().getByRole('button', { name: 'Research selected business', exact: true }).waitFor();
      await page.screenshot({ path: path.join(output, `leads-list-${width}.png`), fullPage: true });
    }
  });
  await check('Operator access keeps qualification reviews available without requesting restricted discovery', async () => {
    await page.getByRole('button', { name: /^New · 30 days/ }).click();
    await page.getByRole('link', { name: 'Setup and settings', exact: true }).click();
    await page.evaluate(() => { globalThis.sourceHarness.engine.data.scopes = ['operator']; globalThis.sourceHarness.requests = []; });
    await page.getByRole('link', { name: 'Latest leads', exact: true }).click();
    await page.getByText(/A reviewer account is needed to browse source records and saved website research/).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Search leads', exact: true }).isDisabled(), true);
    assert.equal(await page.evaluate(() => globalThis.sourceHarness.requests.length), 0);
    await openLeadsList();
    await leadsList().getByRole('button', { name: 'Qualification reviews', exact: true }).click();
    await page.getByText('100/100', { exact: true }).waitFor();
  });
  assert.deepEqual(errors, []);
  const result = { status: 'passed', checked_at: new Date().toISOString(), scope: 'Local actual React dashboard with synthetic engine responses; excludes Clerk, hosted UI, engine integration, real source records and actual exported CSV contents.', checks, browser_errors: errors, artifacts: output };
  await writeFile(path.join(output, 'results.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
  console.error(JSON.stringify({ status: 'failed', passed_checks: checks, error: error.message, browser_errors: errors, artifacts: output }, null, 2));
  process.exitCode = 1;
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
