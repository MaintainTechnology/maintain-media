/* eslint-disable @typescript-eslint/no-require-imports -- Node CommonJS browser harness. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const origin = process.env.ABN_DASHBOARD_TEST_URL || 'http://127.0.0.1:3001';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(origin);
    await page.getByRole('button', { name: 'Open menu' }).click();
    await page.getByRole('navigation', { name: 'Mobile', exact: true }).getByRole('link', { name: 'Services' }).click();
    await page.waitForURL('**/services');
    await page.getByRole('button', { name: 'Open menu' }).waitFor();
    assert.equal(await page.getByRole('navigation', { name: 'Mobile', exact: true }).count(), 0);
    for (const route of ['/services', '/about', '/contact']) {
      const response = await page.goto(origin + route);
      assert.equal(response.status(), 200);
      assert.equal(await page.locator('header').count(), 1);
      assert.equal(await page.locator('footer').count(), 1);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    }
    await page.goto(origin + '/abn-lead-gen/sign-in');
    await page.getByRole('heading', { name: 'Your lead workspace.' }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Open menu' }).count(), 0);
    assert.equal(await page.locator('footer').count(), 0);
    assert.deepEqual(errors, []);
    const result = { status: 'passed', checked_at: new Date().toISOString(), checks: ['Public mobile menu closes after navigation', 'Services, About and Contact retain header/footer and fit390px', 'Admin sign-in has dedicated chrome'], browser_errors: errors };
    const directory = path.join(__dirname, '../acceptance/abn-lead-gen');
    await fs.mkdir(directory, { recursive: true });
    await fs.writeFile(path.join(directory, 'site-shell.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
