/* Browser acceptance for the native, authenticated ABN dashboard.
 * Run only against an explicitly started local fixture environment.
 * Credentials come from ABN_TEST_USERNAME / ABN_TEST_PASSWORD or the ignored
 * ABN_TEST_CREDENTIALS file. No credentials, cookies or CSRF tokens are written
 * to evidence. Original engine preferences are restored even after a failure.
 */
/* eslint-disable @typescript-eslint/no-require-imports -- Executable CommonJS browser harness shares the repository Playwright dependency. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const base = process.env.ABN_DASHBOARD_TEST_URL || 'http://127.0.0.1:3001';
const origin = new URL(base).origin;
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname), 'Acceptance is restricted to a local fixture server');
const dashboardPath = '/abn-lead-gen/dashboard';
const signinPath = '/abn-lead-gen/sign-in';
const api = '/api/abn-lead-gen';
const output = process.env.ABN_DASHBOARD_TEST_OUTPUT || path.join(__dirname, '..', 'acceptance', 'abn-lead-gen', new Date().toISOString().replace(/[:.]/g, '-'));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const clone = value => JSON.parse(JSON.stringify(value));
const probeFilter = process.env.ABN_DASHBOARD_TEST_PROBE || '';

async function credentials() {
  if (process.env.ABN_TEST_USERNAME && process.env.ABN_TEST_PASSWORD) return { username: process.env.ABN_TEST_USERNAME, password: process.env.ABN_TEST_PASSWORD };
  const file = process.env.ABN_TEST_CREDENTIALS || path.join(__dirname, '..', '.local', 'admin-access.txt');
  const text = await fs.readFile(file, 'utf8');
  if (text.trim().startsWith('{')) {
    const parsed = JSON.parse(text);
    assert.ok(parsed.username && parsed.password, 'Credential file must define username and password');
    return { username: parsed.username, password: parsed.password };
  }
  const username = text.match(/^\s*(?:username|admin username)\s*:\s*(.+?)\s*$/im)?.[1];
  const password = text.match(/^\s*(?:password|admin password)\s*:\s*(.+?)\s*$/im)?.[1];
  assert.ok(username && password, 'Ignored credential file must contain Username: and Password: lines');
  return { username, password };
}

async function eventually(check, message, timeout = 15000) {
  const started = Date.now();
  let last;
  while (Date.now() - started < timeout) {
    try { if (await check()) return; } catch (error) { last = error; }
    await delay(100);
  }
  throw new Error(message + (last ? ` (${last.message})` : ''));
}

async function main() {
  const account = await credentials();
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  page.setDefaultNavigationTimeout(60000);
  const checks = [];
  const browserErrors = [];
  const runs = [];
  const safeError = value => [account.password, account.username].reduce((text, secret) => text.split(secret).join('[redacted]'), String(value));
  let original;
  let authState;
  let passed = false;
  let failureReason;
  const captureError = error => browserErrors.push(safeError(error.message));
  page.on('pageerror', captureError);
  context.on('page', nextPage => nextPage.on('pageerror', captureError));

  async function snapshot(request = context.request) {
    const response = await request.get(origin + api + '/dashboard');
    assert.equal(response.status(), 200, 'Authenticated dashboard snapshot');
    assert.match(response.headers()['cache-control'] || '', /no-store/, 'Private data must not be cached');
    const data = await response.json();
    assert.equal(data.mode, 'fixture', 'Browser acceptance must never run against live collection');
    assert.ok(data.admin?.csrfToken, 'Authenticated snapshot provides session-bound CSRF');
    assert.equal(data.csrf_token, undefined, 'Upstream engine CSRF is never exposed');
    return data;
  }

  async function apiLogin(request = context.request) {
    const response = await request.post(origin + api + '/auth/login', { headers: { Origin: origin }, data: account });
    assert.equal(response.status(), 200, 'Local administrator can authenticate');
  }

  async function ready(target = page) {
    await target.locator('#lead-search').waitFor({ state: 'attached' });
    await eventually(() => target.locator('#lead-search').isEnabled(), 'Usable dashboard snapshot loaded');
  }

  async function switchView(view, target = page) {
    await target.locator(`nav [data-view="${view}"]`).click();
    await target.locator(`#view-${view}`).waitFor({ state: 'visible' });
    assert.equal(await target.locator(`nav [data-view="${view}"]`).getAttribute('aria-current'), 'page');
  }

  async function refresh(target = page) {
    const current = await target.locator('.view:visible').getAttribute('id');
    if (current === 'view-setup') await switchView('leads', target);
    const response = target.waitForResponse(r => new URL(r.url()).pathname === api + '/dashboard');
    await target.locator('.refresh-button:visible').first().click();
    await response;
    if (current === 'view-setup') await switchView('setup', target);
  }

  async function backgroundRefresh(target = page) {
    const response = target.waitForResponse(r => new URL(r.url()).pathname === api + '/dashboard');
    await target.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await response;
  }

  async function save(source, cap) {
    await switchView('setup');
    await page.locator('#default-source').selectOption(source);
    await page.locator('#monthly-cap').fill(cap);
    if (await page.locator('#save-settings').isEnabled()) {
      const response = page.waitForResponse(r => new URL(r.url()).pathname === api + '/settings' && r.request().method() === 'PATCH');
      await page.locator('#save-settings').click();
      assert.equal((await response).status(), 200, 'Settings update accepted');
      await eventually(async () => await page.locator('#save-settings').isDisabled() && (await page.locator('#save-settings').innerText()) === 'Save changes', 'Saved configuration settles');
    }
    const saved = await snapshot();
    assert.equal(saved.settings.default_source, source);
    assert.equal(saved.settings.monthly_cap_micro_aud, Math.round(Number(cap) * 1e6));
  }

  async function denied(request) {
    const id = '00000000-0000-4000-8000-000000000001';
    const routes = [
      ['GET', '/dashboard'], ['GET', '/jobs/' + id],
      ['GET', '/reports/' + id + '/html'], ['GET', '/reports/' + id + '/csv'], ['GET', '/reports/' + id + '/markdown'],
      ['PATCH', '/settings'], ['POST', '/runs'], ['POST', '/auth/logout'],
    ];
    for (const [method, suffix] of routes) {
      const response = await request.fetch(origin + api + suffix, { method, headers: { Origin: origin }, data: method === 'GET' ? undefined : {}, maxRedirects: 0 });
      assert.equal(response.status(), 401, `${method} ${suffix} denies anonymous access before processing`);
      assert.match(response.headers()['cache-control'] || '', /no-store/);
    }
    return routes.length;
  }

  async function probe(name, baseline, run) {
    if (probeFilter && !name.toLowerCase().includes(probeFilter.toLowerCase())) return;
    const isolated = await browser.newContext({ storageState: authState, viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    const target = await isolated.newPage();
    target.setDefaultTimeout(15000);
    target.setDefaultNavigationTimeout(60000);
    const errors = [];
    const unexpected = [];
    target.on('pageerror', error => errors.push(error.message));
    await isolated.route('**/api/abn-lead-gen/**', route => {
      unexpected.push(new URL(route.request().url()).pathname);
      return route.abort('blockedbyclient');
    });
    await target.route('**/api/abn-lead-gen/dashboard', route => route.fulfill({ json: baseline }));
    try {
      await run(target, isolated);
      assert.deepEqual(errors, [], `${name}: browser errors`);
      assert.deepEqual(unexpected, [], `${name}: unexpected API request`);
      checks.push({ name, status: 'passed', isolated_api_mutations: true });
      console.log('PASS: ' + name);
    } finally { await isolated.close(); }
  }

  try {
    if (!probeFilter) {
    await page.goto(origin + dashboardPath);
    await page.waitForURL('**' + signinPath + '**');
    assert.equal(await page.locator('.lead-row').count(), 0);
    const deniedRoutes = await denied(context.request);
    checks.push({ name: 'Anonymous page redirects and every protected API family denies access', status: 'passed', denied_routes: deniedRoutes });

    await page.locator('input[name="username"]').fill(account.username);
    await page.locator('input[name="password"]').fill(account.password + '-invalid-acceptance');
    await page.getByRole('button', { name: 'Show', exact: true }).click();
    assert.equal(await page.locator('input[name="password"]').getAttribute('type'), 'text');
    await page.getByRole('button', { name: 'Hide', exact: true }).click();
    assert.equal(await page.locator('input[name="password"]').getAttribute('type'), 'password');
    const rejected = page.waitForResponse(r => new URL(r.url()).pathname === api + '/auth/login');
    await page.locator('button[type="submit"]').click();
    assert.equal((await rejected).status(), 401, 'Wrong password rejected');
    await eventually(() => page.locator('button[type="submit"]').isEnabled(), 'Sign-in recovers after wrong password');
    assert.ok(page.url().includes(signinPath));
    await page.locator('input[name="password"]').fill(account.password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**' + dashboardPath + '**');
    await ready();
    const baseline = await snapshot();
    original = baseline.settings;
    authState = await context.storageState();
    checks.push({ name: 'Rejected sign-in recovers and the configured administrator signs in', status: 'passed' });

    for (const suffix of ['/settings', '/runs']) {
      const method = suffix === '/settings' ? 'PATCH' : 'POST';
      const missing = await context.request.fetch(origin + api + suffix, { method, headers: { Origin: origin }, data: {} });
      assert.equal(missing.status(), 403, 'Authenticated writes still require the admin CSRF token');
      const crossSite = await context.request.fetch(origin + api + suffix, { method, headers: { Origin: 'https://hostile.example', 'X-Admin-CSRF': baseline.admin.csrfToken }, data: {} });
      assert.equal(crossSite.status(), 403, 'Cross-site writes are rejected before engine access');
    }
    checks.push({ name: 'Authenticated writes reject missing CSRF and a hostile origin', status: 'passed' });

    const cookies = await context.cookies();
    const session = cookies.find(cookie => cookie.httpOnly);
    assert.ok(session, 'Administrator session uses an HttpOnly cookie');
    assert.ok(['Strict', 'Lax'].includes(session.sameSite));
    assert.ok(session.expires > Date.now() / 1000, 'Session expires rather than lasting indefinitely');
    assert.equal(await page.locator('script[src*="127.0.0.1:8767"]').count(), 0);
    assert.equal(await page.locator('iframe').count(), 0, 'Dashboard is native React rather than an embedded HTML page');
    const privateRequests = [];
    page.on('request', request => { if (new URL(request.url()).port === '8767') privateRequests.push(new URL(request.url()).pathname); });

    for (const view of ['leads', 'runs', 'setup']) await switchView(view);
    await page.locator('.brand').click();
    await page.locator('#view-leads').waitFor({ state: 'visible' });
    const websiteLink = page.getByRole('link', { name: /(?:back|return).*website|maintain media website/i }).first();
    assert.equal(new URL(await websiteLink.getAttribute('href'), origin).pathname, '/');
    checks.push({ name: 'All workspace views, brand navigation and return-to-website link operate', status: 'passed' });

    const leads = baseline.leads;
    assert.ok(leads.length, 'Existing fixture leads available');
    for (const lead of leads) {
      await page.locator('#lead-search').fill(lead.business_name);
      await eventually(async () => (await page.locator('.lead-row').count()) > 0, 'Name search returns a stored business');
      await page.locator('.lead-row').first().click();
      assert.ok((await page.locator('#lead-detail').innerText()).includes(lead.business_name));
      if (lead.abn) {
        await page.locator('#lead-search').fill(lead.abn.replace(/^(\d{2})(\d{3})(\d{3})(\d{3})$/, '$1 $2 $3 $4'));
        assert.ok(await page.locator('.lead-row').count() > 0, 'Formatted ABN search works');
      }
    }
    await page.locator('#lead-search').fill('no-such-business-for-acceptance');
    assert.equal(await page.locator('.lead-row').count(), 0);
    await page.locator('#empty-action').click();
    for (const source of ['all', 'abr', 'qbcc']) {
      await page.locator('#source-filter').selectOption(source);
      for (const tier of ['all', 'A', 'B', 'C']) {
        await page.locator('#tier-filter').selectOption(tier);
        assert.equal(await page.locator('.lead-row').count(), leads.filter(lead => (source === 'all' || lead.source === source) && (tier === 'all' || lead.tier === tier)).length);
      }
    }
    await page.locator('#source-filter').selectOption('all');
    await page.locator('#tier-filter').selectOption('all');
    checks.push({ name: 'Every business opens, names and formatted ABNs search, all 12 filters match stored data, empty state clears', status: 'passed', leads: leads.length });

    await save('all', '0.00');
    await page.reload();
    await ready();
    await switchView('setup');
    assert.equal(await page.locator('#monthly-cap').inputValue(), '0.00');
    for (const invalid of ['-1', '151']) {
      await page.locator('#monthly-cap').fill(invalid);
      assert.equal(await page.locator('#monthly-cap').evaluate(input => input.checkValidity()), false, 'Invalid budget rejected before mutation');
    }
    await page.locator('#reset-settings').click();
    assert.equal(await page.locator('#monthly-cap').inputValue(), '0.00');
    await save('all', '150.00');
    await page.reload();
    await ready();
    await switchView('setup');
    assert.equal(await page.locator('#monthly-cap').inputValue(), '150.00');
    checks.push({ name: 'A$0 and A$150 save across reload, out-of-range budgets fail validation, discard restores the saved value', status: 'passed' });

    for (const [source, view, cap, width] of [['all', 'leads', '150.00', 1440], ['abr', 'runs', '150.00', 1440], ['qbcc', 'leads', '149.99', 390]]) {
      await page.setViewportSize({ width, height: 950 });
      await save(source, cap);
      await switchView(view);
      let postCount = 0;
      const countPost = request => { if (new URL(request.url()).pathname === api + '/runs' && request.method() === 'POST') postCount++; };
      page.on('request', countPost);
      const submitted = page.waitForResponse(r => new URL(r.url()).pathname === api + '/runs' && r.request().method() === 'POST');
      await page.locator(`#view-${view} .run-button`).first().evaluate(button => { button.click(); button.click(); });
      const response = await submitted;
      assert.equal(response.status(), 202, 'Fixture run accepted');
      let final = await response.json();
      const jobId = final.job_id;
      await eventually(async () => {
        const job = await context.request.get(origin + api + '/jobs/' + jobId);
        assert.equal(job.status(), 200);
        final = await job.json();
        return !['queued', 'running'].includes(final.state);
      }, 'Fixture run reaches a terminal state', 90000);
      assert.equal(final.state, 'complete', 'Actual fixture run completes');
      assert.equal(final.source, source);
      assert.equal(final.monthly_cap_micro_aud, Math.round(Number(cap) * 1e6));
      assert.equal(postCount, 1, 'Rapid duplicate clicks produce one run request');
      page.off('request', countPost);
      await switchView('runs');
      await refresh();
      await eventually(async () => /complete/i.test(await page.locator('#active-run').innerText()), 'Run completion displayed');
      const updated = await snapshot();
      const run = updated.runs.find(item => item.run_id === final.run_id);
      assert.ok(run?.reports?.html && run.reports.csv && run.reports.markdown, 'Every report format available');
      for (const kind of ['html', 'csv', 'markdown']) {
        assert.ok(run.reports[kind].startsWith(api + '/reports/'), 'Report stays inside authenticated website routes');
        const report = await context.request.get(origin + run.reports[kind]);
        assert.equal(report.status(), 200, `${source} ${kind} report`);
        assert.match(report.headers()['cache-control'] || '', /no-store/);
        const body = await report.text();
        assert.ok(body.length > 0);
        assert.equal(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(body), false, 'Raw contact email is masked in dashboard reports');
        if (kind !== 'csv') {
          assert.ok(body.includes(run.reports.csv), 'Report CSV links point back through protected website route');
          assert.equal(body.includes('href="/api/reports/'), false);
        }
      }
      runs.push({ source, run_id: final.run_id, state: final.state, run_requests: postCount, viewport: width });
      checks.push({ name: `${source.toUpperCase()} actual fixture run uses saved source and cap, prevents double click, and serves all 3 masked report formats`, status: 'passed' });
    }

    await save(original.default_source, (original.monthly_cap_micro_aud / 1e6).toFixed(2));
    await switchView('runs');
    const popupPending = context.waitForEvent('page');
    await page.locator('.report-link[data-kind="html"]').first().click();
    const reportPage = await popupPending;
    await reportPage.waitForURL('**' + api + '/reports/**/html');
    await reportPage.locator('h1').waitFor();
    const nestedPending = reportPage.waitForEvent('download');
    await reportPage.getByRole('link', { name: /download.*CSV/i }).click();
    assert.equal(await (await nestedPending).failure(), null);
    await reportPage.close();
    for (const kind of ['csv', 'markdown']) {
      const pending = page.waitForEvent('download');
      await page.locator(`.report-link[data-kind="${kind}"]`).first().click();
      const download = await pending;
      assert.equal(await download.failure(), null);
      await download.saveAs(path.join(output, kind === 'csv' ? 'worklist.csv' : 'worklist.md'));
    }
    await switchView('leads');
    const exported = page.waitForEvent('download');
    await page.locator('.export-latest').click();
    assert.equal(await (await exported).failure(), null);
    await refresh();
    checks.push({ name: 'HTML popup and nested CSV, direct CSV/Markdown downloads, latest export and both refresh controls operate', status: 'passed' });

    for (const viewport of [{ width: 1440, height: 1000 }, { width: 820, height: 1180 }, { width: 390, height: 844 }, { width: 360, height: 800 }]) {
      await page.setViewportSize(viewport);
      for (const view of ['leads', 'runs', 'setup']) {
        await switchView(view);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${viewport.width}px ${view} fits without horizontal page scroll`);
        await page.getByRole('link', { name: 'Skip to content', exact: true }).focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'main');
        assert.equal(await page.locator('.view:visible').getAttribute('id'), 'view-' + view);
        await page.screenshot({ path: path.join(output, `${viewport.width}-${view}.png`), fullPage: true });
      }
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    assert.equal(await page.locator('.button').first().evaluate(element => getComputedStyle(element).transitionDuration), '0s');
    assert.deepEqual(privateRequests, [], 'Browser must never call the Python bridge directly');
    checks.push({ name: 'All views fit 1440/820/390/360px, keyboard skip preserves the view, reduced motion is respected, bridge remains server-side', status: 'passed' });
    } else {
      await apiLogin();
      await page.goto(origin + dashboardPath);
      await ready();
      original = (await snapshot()).settings;
      authState = await context.storageState();
    }

    const data = clone(await snapshot());
    data.active_job = null;
    await probe('Malformed and non-JSON refreshes preserve usable data and recover', data, async target => {
      let response = data;
      let nonJSON = false;
      await target.route('**/api/abn-lead-gen/dashboard', route => nonJSON ? route.fulfill({ status: 502, contentType: 'text/html', body: '<h1>Unavailable</h1>' }) : route.fulfill({ json: response }));
      await target.goto(origin + dashboardPath);
      await ready(target);
      for (const malformed of [{}, { ...data, leads: [{ ...data.leads[0], reason_codes: 'malformed' }] }]) {
        response = malformed;
        await refresh(target);
        await target.locator('#error-banner').waitFor({ state: 'visible' });
        assert.equal(await target.locator('.lead-row').count(), data.leads.length);
        assert.equal(await target.locator('#lead-search').isEnabled(), true);
      }
      nonJSON = true;
      await refresh(target);
      assert.equal(await target.locator('#error-banner').isVisible(), true);
      assert.equal(await target.locator('.lead-row').count(), data.leads.length);
      response = data;
      nonJSON = false;
      await target.locator('#retry-button').click();
      await target.locator('#error-banner').waitFor({ state: 'hidden' });
    });

    await probe('Offline first load disables dependent controls then recovers', data, async target => {
      let online = false;
      await target.route('**/api/abn-lead-gen/dashboard', route => online ? route.fulfill({ json: data }) : route.abort('connectionrefused'));
      await target.goto(origin + dashboardPath);
      await target.locator('#error-banner').waitFor({ state: 'visible' });
      assert.equal(await target.locator('#lead-search').isDisabled(), true);
      assert.equal(await target.locator('.run-button').evaluateAll(buttons => buttons.every(button => button.disabled)), true);
      online = true;
      await target.locator('#retry-button').click();
      await ready(target);
      await target.locator('#error-banner').waitFor({ state: 'hidden' });
    });

    await probe('Initial loading protects settings and every dependent action until data arrives', data, async target => {
      let release;
      await target.route('**/api/abn-lead-gen/dashboard', async route => {
        await new Promise(resolve => { release = resolve; });
        return route.fulfill({ json: data });
      });
      await target.goto(origin + dashboardPath + '#setup', { waitUntil: 'domcontentloaded' });
      await eventually(() => Boolean(release), 'Initial dashboard read is pending');
      for (const selector of ['#monthly-cap', '#default-source', '#lead-search', '#source-filter', '#tier-filter']) {
        assert.equal(await target.locator(selector).isDisabled(), true, 'Loading control is disabled: ' + selector);
      }
      assert.equal(await target.locator('.run-button').evaluateAll(buttons => buttons.every(button => button.disabled)), true);
      release();
      await ready(target);
      assert.equal(await target.locator('#monthly-cap').isEnabled(), true);
    });

    await probe('Settings draft survives refresh and rejected saves; recovery and discard work', data, async target => {
      let saved;
      let fail = true;
      await target.route('**/api/abn-lead-gen/dashboard', route => route.fulfill({ json: saved ? { ...data, settings: saved } : data }));
      await target.route('**/api/abn-lead-gen/settings', route => {
        if (fail) return route.fulfill({ status: 503, json: { code: 'DASHBOARD_STORAGE_UNAVAILABLE' } });
        saved = { ...data.settings, ...route.request().postDataJSON() };
        return route.fulfill({ json: saved });
      });
      await target.goto(origin + dashboardPath);
      await ready(target);
      await switchView('setup', target);
      const draft = data.settings.monthly_cap_micro_aud === 77000000 ? '76.00' : '77.00';
      await target.locator('#monthly-cap').fill(draft);
      await refresh(target);
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
      await target.locator('#save-settings').click();
      await target.locator('#settings-error').waitFor({ state: 'visible' });
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
      assert.equal(await target.locator('#save-settings').isEnabled(), true);
      fail = false;
      await target.locator('#save-settings').click();
      await eventually(() => target.locator('#save-settings').isDisabled(), 'Retried save settles');
      assert.equal(saved.monthly_cap_micro_aud, Number(draft) * 1e6);
      await target.locator('#monthly-cap').fill('33.00');
      await target.locator('#reset-settings').click();
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
    });

    await probe('Saved settings cannot be replaced by an older in-flight refresh', data, async target => {
      let calls = 0;
      let release;
      let saved;
      await target.route('**/api/abn-lead-gen/dashboard', async route => {
        calls++;
        if (calls === 2) { await new Promise(resolve => { release = resolve; }); return route.fulfill({ json: data }); }
        return route.fulfill({ json: saved ? { ...data, settings: saved } : data });
      });
      await target.route('**/api/abn-lead-gen/settings', route => {
        saved = { ...data.settings, ...route.request().postDataJSON() };
        return route.fulfill({ json: saved });
      });
      await target.goto(origin + dashboardPath);
      await ready(target);
      await target.locator('.refresh-button:visible').first().click();
      await eventually(() => Boolean(release), 'Old dashboard refresh is in flight');
      await switchView('setup', target);
      const draft = data.settings.monthly_cap_micro_aud === 99000000 ? '98.00' : '99.00';
      await target.locator('#monthly-cap').fill(draft);
      const updated = target.waitForResponse(r => new URL(r.url()).pathname === api + '/settings');
      await target.locator('#save-settings').click();
      await updated;
      release();
      await eventually(() => calls >= 3, 'Save queues a fresh snapshot after stale response');
      await eventually(() => target.locator('#save-settings').isDisabled(), 'Mutation finishes with current settings');
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
    });

    await probe('Rejected and ambiguous run attempts recover without duplicate clicks or lost retry identity', data, async target => {
      let failure = 'network';
      const requests = [];
      await target.route('**/api/abn-lead-gen/runs', route => {
        requests.push(route.request().postDataJSON());
        return failure === 'network' ? route.abort('connectionreset') : route.fulfill({ status: 409, json: { code: 'DASHBOARD_RUN_ACTIVE' } });
      });
      await target.goto(origin + dashboardPath);
      await ready(target);
      const button = target.locator('#view-leads .run-button').first();
      await button.evaluate(element => { element.click(); element.click(); });
      await target.locator('#error-banner').waitFor({ state: 'visible' });
      assert.equal(requests.length, 1);
      await eventually(() => button.isEnabled(), 'Network failure releases run control');
      failure = 'rejected';
      await button.click();
      await eventually(() => requests.length === 2 && button.isEnabled(), 'Rejected run releases control');
      assert.equal(requests[0].request_id, requests[1].request_id, 'An uncertain run retry keeps its original identity');
      await target.locator('#error-banner').waitFor({ state: 'visible' });
      await backgroundRefresh(target);
      assert.equal(await target.locator('#error-banner').isVisible(), true, 'Background snapshot does not hide an action failure');
      await target.locator('#retry-button').click();
      await target.locator('#error-banner').waitFor({ state: 'hidden' });
    });

    await probe('Malformed save and run confirmations preserve drafts and explain the unconfirmed action', data, async target => {
      await target.route('**/api/abn-lead-gen/settings', route => route.fulfill({ json: {} }));
      await target.route('**/api/abn-lead-gen/runs', route => route.fulfill({ json: {} }));
      await target.goto(origin + dashboardPath);
      await ready(target);
      await switchView('setup', target);
      const draft = data.settings.monthly_cap_micro_aud === 66000000 ? '65.00' : '66.00';
      await target.locator('#monthly-cap').fill(draft);
      await target.locator('#save-settings').click();
      await target.locator('#settings-error').waitFor({ state: 'visible' });
      assert.match(await target.locator('#settings-error').innerText(), /did not confirm/);
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
      assert.equal(await target.locator('#save-settings').isEnabled(), true);
      await target.locator('#reset-settings').click();
      await switchView('runs', target);
      await target.locator('#view-runs .run-button').first().click();
      await target.locator('#error-banner').waitFor({ state: 'visible' });
      assert.match(await target.locator('#error-text').innerText(), /did not confirm/);
      assert.equal(await target.locator('#view-runs .run-button').first().isEnabled(), true);
    });

    await probe('A run confirmed by polling clears an ambiguous retry identity before the next new run', data, async target => {
      const requests = [];
      let confirmation;
      await target.route('**/api/abn-lead-gen/dashboard', route => route.fulfill({ json: confirmation ? { ...data, active_job: null, latest_job: confirmation } : data }));
      await target.route('**/api/abn-lead-gen/runs', route => {
        const request = route.request().postDataJSON();
        requests.push(request);
        if (requests.length === 1) {
          confirmation = { job_id: request.request_id, run_id: data.runs[0].run_id, state: 'complete', source: request.source, error_code: null };
          return route.abort('connectionreset');
        }
        return route.fulfill({ status: 503, json: { code: 'ENGINE_UNAVAILABLE' } });
      });
      await target.goto(origin + dashboardPath);
      await ready(target);
      const button = target.locator('#view-leads .run-button').first();
      await button.click();
      await target.locator('#error-banner').waitFor({ state: 'visible' });
      await eventually(() => button.isEnabled(), 'Confirmed first attempt releases run control');
      await button.click();
      await eventually(() => requests.length === 2, 'New run request is issued');
      assert.notEqual(requests[0].request_id, requests[1].request_id, 'Completed receipt from polling releases the old request identity');
    });

    await probe('Unsaved settings prevent accidental page exit and can be kept after cancelling sign-out', data, async target => {
      await target.goto(origin + dashboardPath);
      await ready(target);
      await switchView('setup', target);
      const draft = data.settings.monthly_cap_micro_aud === 55000000 ? '54.00' : '55.00';
      await target.locator('#monthly-cap').fill(draft);
      const pending = target.waitForEvent('dialog');
      target.once('dialog', dialog => dialog.dismiss());
      await target.locator('#admin-logout').click();
      assert.equal((await pending).type(), 'confirm');
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
      assert.equal(await target.locator('#save-settings').isEnabled(), true);
      const leave = target.waitForEvent('dialog');
      target.once('dialog', dialog => dialog.dismiss());
      await target.locator('.website-link').click({ noWaitAfter: true });
      assert.ok(['beforeunload', 'confirm'].includes((await leave).type()), 'Unsaved changes require confirmation before leaving the workspace');
      assert.ok(target.url().includes(dashboardPath));
      assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
      await target.locator('#reset-settings').click();
    });

    await probe('Failed sign-out keeps the unsaved draft and a persistent actionable error', data, async target => {
      let failure = 'unavailable';
      await target.route('**/api/abn-lead-gen/auth/logout', route => failure === 'unavailable'
        ? route.fulfill({ status: 503, json: { code: 'ADMIN_AUTH_UNAVAILABLE' } })
        : failure === 'malformed' ? route.fulfill({ json: {} })
        : route.fulfill({ status: 200, contentType: 'text/html', body: '<h1>Unexpected proxy response</h1>' }));
      await target.goto(origin + dashboardPath);
      await ready(target);
      await switchView('setup', target);
      const draft = data.settings.monthly_cap_micro_aud === 44000000 ? '43.00' : '44.00';
      await target.locator('#monthly-cap').fill(draft);
      for (failure of ['unavailable', 'malformed', 'non-json']) {
        target.once('dialog', dialog => dialog.accept());
        await target.locator('#admin-logout').click();
        await target.locator('#error-banner').waitFor({ state: 'visible' });
        await eventually(() => target.locator('#admin-logout').isEnabled(), 'Failed sign-out releases the control');
        await backgroundRefresh(target);
        assert.match(await target.locator('#error-text').innerText(), /Sign-out could not be confirmed/);
        assert.equal(await target.locator('#monthly-cap').inputValue(), draft);
        assert.equal(await target.locator('#save-settings').isEnabled(), true);
      }
      await target.locator('#reset-settings').click();
    });

    await probe('Stale report error recovers and blocked popup retains the report CSV link', data, async target => {
      let stale = true;
      const reports = data.runs.find(run => run.reports?.html).reports;
      await target.route('**/api/abn-lead-gen/reports/**/html', route => stale ? route.fulfill({ status: 409, json: { code: 'REPORT_STALE' } }) : route.fulfill({ contentType: 'text/html', body: `<h1>Masked fixture report</h1><a href="${reports.csv}">Download CSV</a>` }));
      await target.route('**/api/abn-lead-gen/reports/**/csv', route => route.fulfill({ contentType: 'text/csv', headers: { 'Content-Disposition': 'attachment; filename="worklist.csv"' }, body: 'business_name\nFixture\n' }));
      await target.addInitScript(() => { window.open = () => null; });
      await target.goto(origin + dashboardPath);
      await ready(target);
      await switchView('runs', target);
      await target.locator('.report-link[data-kind="html"]').first().click();
      await target.locator('#error-banner').waitFor({ state: 'visible' });
      await backgroundRefresh(target);
      assert.equal(await target.locator('#error-banner').isVisible(), true);
      await target.locator('#retry-button').click();
      await target.locator('#error-banner').waitFor({ state: 'hidden' });
      stale = false;
      await target.locator('.report-link[data-kind="html"]').first().click();
      await target.waitForURL(origin + reports.html);
      const download = target.waitForEvent('download');
      await target.getByRole('link', { name: 'Download CSV' }).click();
      assert.equal(await (await download).failure(), null);
      await target.goBack();
      await ready(target);
      await target.locator('#view-runs').waitFor({ state: 'visible' });
    });

    await probe('Expired authentication clears protected content and returns to sign-in', data, async (target, isolated) => {
      let expired = false;
      await target.route('**/api/abn-lead-gen/dashboard', route => expired ? route.fulfill({ status: 401, json: { code: 'ADMIN_AUTH_REQUIRED' } }) : route.fulfill({ json: data }));
      await target.goto(origin + dashboardPath);
      await ready(target);
      await isolated.clearCookies();
      expired = true;
      await target.locator('.refresh-button:visible').first().click();
      await target.getByRole('heading', { name: 'Your admin workspace is locked.' }).waitFor();
      assert.equal(await target.locator('.lead-row').count(), 0);
      await target.getByRole('link', { name: /Sign in again/ }).click();
      await target.waitForURL('**' + signinPath + '**');
      assert.equal(await target.locator('.lead-row').count(), 0);
      assert.equal(await target.locator('#admin-logout').count(), 0);
    });

    if (probeFilter) assert.ok(checks.some(check => check.isolated_api_mutations), 'The requested regression filter must match at least one completed probe');
    await page.locator('#admin-logout').click();
    await page.waitForURL('**' + signinPath + '**');
    await denied(context.request);
    await page.goto(origin + dashboardPath);
    await page.waitForURL('**' + signinPath + '**');
    assert.equal(await page.locator('.lead-row').count(), 0);
    checks.push({ name: 'Sign-out revokes access, API routes deny reuse and direct dashboard re-entry requires sign-in', status: 'passed' });
    assert.deepEqual(browserErrors, [], 'No uncaught browser JavaScript errors');
    passed = true;
  } catch (error) {
    failureReason = safeError(error.message);
    throw new Error(failureReason);
  } finally {
    let restoration = original ? 'pending' : 'not needed';
    try {
      if (original) {
        await apiLogin();
        const current = await snapshot();
        const restored = await context.request.patch(origin + api + '/settings', { headers: { Origin: origin, 'X-Admin-CSRF': current.admin.csrfToken }, data: { default_source: original.default_source, monthly_cap_micro_aud: original.monthly_cap_micro_aud } });
        assert.equal(restored.status(), 200, 'Original preferences restored');
        const final = await snapshot();
        assert.equal(final.settings.default_source, original.default_source);
        assert.equal(final.settings.monthly_cap_micro_aud, original.monthly_cap_micro_aud);
        restoration = 'passed';
      }
    } catch (error) { passed = false; restoration = 'failed'; console.error('Original preferences could not be restored: ' + error.message); }
    const receipt = { status: passed ? 'passed' : 'failed', checked_at: new Date().toISOString(), origin, mode: 'fixture', suite: probeFilter ? 'targeted resilience regression' : 'full browser acceptance', ...(probeFilter ? { probe_filter: probeFilter } : {}), checks, runs, viewports: probeFilter ? [1280] : [1440, 820, 390, 360], preference_restoration: restoration, browser_errors: browserErrors, ...(failureReason ? { failure: failureReason } : {}) };
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(receipt, null, 2));
    console.log(JSON.stringify({ status: receipt.status, evidence: output, checks: checks.length, runs, preference_restoration: restoration, browser_errors: browserErrors }, null, 2));
    await browser.close();
    if (!passed) process.exitCode = 1;
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
