// Isolated native-form regression. No user browser, credentials, or vendor access.
const { chromium } = require(process.argv[2]);
const url = process.argv[3];
const origin = new URL(url).origin;
const syntheticToken = 'pit-synthetic-' + 'z'.repeat(40);

(async () => {
  const browser = await chromium.launch({ headless: true,
    ...(process.argv[4] ? { executablePath: process.argv[4] } : {}) });
  try {
    const context = await browser.newContext();
    await context.route('**/*', route => new URL(route.request().url()).origin === origin
      ? route.continue() : route.abort());
    const page = await context.newPage();
    await page.goto(url);
    await page.getByLabel('New private-integration token').fill(syntheticToken);
    const [response] = await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
      page.getByRole('button', { name: 'Save and install token' }).click(),
    ]);
    process.stdout.write(JSON.stringify({ status: response.status() }));
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(() => {
  process.stdout.write(JSON.stringify({ status: 'synthetic_browser_check_failed' }));
  process.exitCode = 1;
});
