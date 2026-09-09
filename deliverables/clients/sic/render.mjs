#!/usr/bin/env node
/**
 * Render a Maintain Media client brochure (HTML) to a print-ready A4 PDF.
 *
 * Usage:  node render.mjs [input.html] [output.pdf]
 * Defaults to sic-marketing-summary-aug-2026.html -> .pdf in this folder.
 *
 * Requires Playwright (already available in this repo via npx).
 */
import { chromium } from 'playwright';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const input = path.resolve(here, process.argv[2] ?? 'sic-marketing-summary-aug-2026.html');
const output = path.resolve(here, process.argv[3] ?? input.replace(/\.html$/, '.pdf'));

const browser = await chromium.launch();
const page = await browser.newPage();

await page.goto(pathToFileURL(input).href, { waitUntil: 'networkidle' });
await page.emulateMedia({ media: 'print' });
await page.evaluate(() => document.fonts.ready);

await page.pdf({
  path: output,
  format: 'A4',
  printBackground: true,
  margin: { top: '0', right: '0', bottom: '0', left: '0' },
});

await browser.close();
console.log(`PDF written: ${output}`);
