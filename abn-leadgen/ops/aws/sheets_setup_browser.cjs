// Isolated browser regression for new setup values; synthetic keys and loopback only.
const { chromium } = require(process.argv[2]);
const url = process.argv[3];
const origin = new URL(url).origin;

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.argv[4] });
  try {
    const context = await browser.newContext();
    let leaked = false;
    await context.route('**/*', route => {
      const request = route.request();
      const body = request.postData() || '';
      if (body.includes('s'.repeat(64)) || body.includes('h'.repeat(64))) leaked = true;
      return new URL(request.url()).origin === origin ? route.continue() : route.abort();
    });
    const page = await context.newPage();
    await page.goto(url);
    const initial = await page.content();
    const initialClear = !initial.includes('s'.repeat(64)) && !initial.includes('h'.repeat(64))
      && await page.locator('input[name="SERVICE_SIGNING_KEY"]').count() === 0;
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.getByRole('button', { name: 'Load new setup values' }).click()]);
    const matches = await page.getByLabel('SERVICE_SIGNING_KEY', { exact: true }).inputValue() === 's'.repeat(64)
      && await page.getByLabel('BRIDGE_SECRET', { exact: true }).inputValue() === 'h'.repeat(64)
      && await page.getByLabel('ENABLED', { exact: true }).inputValue() === 'false';
    const renderedReadonly = await page.getByLabel('SERVICE_SIGNING_KEY', { exact: true }).getAttribute('type') === 'text'
      && await page.getByLabel('BRIDGE_SECRET', { exact: true }).getAttribute('type') === 'text'
      && !await page.getByLabel('SERVICE_SIGNING_KEY', { exact: true }).isEditable()
      && !await page.getByLabel('BRIDGE_SECRET', { exact: true }).isEditable();
    await Promise.all([page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.getByRole('button', { name: 'Clear this page' }).click()]);
    const final = await page.content();
    process.stdout.write(JSON.stringify({ initial_clear: initialClear, pair_matches: matches, rendered_readonly: renderedReadonly,
      final_clear: !final.includes('s'.repeat(64)) && !final.includes('h'.repeat(64)), secret_request_body: leaked }));
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(() => {
  process.stdout.write(JSON.stringify({ status: 'synthetic_browser_check_failed' }));
  process.exitCode = 1;
});
