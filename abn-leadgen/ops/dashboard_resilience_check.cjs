/* Read-only browser regression suite. Every API mutation is intercepted.
 * Requires the local dashboard, Playwright, and one stored fixture report.
 */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.env.ABR_DASHBOARD_TEST_URL || 'http://127.0.0.1:8767';
const output = path.join(__dirname, 'acceptance', 'dashboard-resilience');

(async () => {
  const browser = await chromium.launch({headless:true});
  const reader = await browser.newContext();
  let baseline;
  const checks = [];
  try {
    baseline = await (await reader.request.get(base + '/api/dashboard')).json();
    assert.equal(baseline.mode, 'fixture');
    assert.ok(baseline.leads.length && baseline.runs.some(run => run.reports?.html));
    baseline.active_job = null;
    baseline.operational_notices = [];
    await reader.close();

    async function probe(name, run) {
      const context = await browser.newContext({acceptDownloads:true, viewport:{width:1280,height:900}});
      const page = await context.newPage();
      const errors = [];
      const blockedMutations = [];
      page.on('pageerror', error => errors.push(error.message));
      // Unhandled API calls never reach the live engine, including all writes.
      await context.route('**/api/**', route => {
        if (route.request().method() !== 'GET') blockedMutations.push(route.request().url());
        return route.abort('blockedbyclient');
      });
      try {
        const evidence = await run(page, context);
        assert.deepEqual(errors, [], `${name}: browser errors`);
        assert.deepEqual(blockedMutations, [], `${name}: unexpected mutation attempt`);
        checks.push({name, status:'passed', ...evidence, browser_errors:errors});
        console.log(`PASS: ${name}`);
      } finally { await context.close(); }
    }
    const ready = page => page.waitForFunction(() => state.data && !state.loading && !state.loadPromise);
    const fixture = page => page.route('**/api/dashboard', route => route.fulfill({json:baseline}));

    await probe('Saved settings survive an older in-flight refresh', async page => {
      let releaseRefresh;
      let refreshStarted;
      const started = new Promise(resolve => { refreshStarted = resolve; });
      let calls = 0;
      let saved;
      const cap = baseline.settings.monthly_cap_micro_aud === 99000000 ? 88000000 : 99000000;
      const source = baseline.settings.default_source === 'abr' ? 'qbcc' : 'abr';
      await page.route('**/api/dashboard', async route => {
        calls++;
        if (calls === 2) {
          refreshStarted();
          await new Promise(resolve => { releaseRefresh = resolve; });
          return route.fulfill({json:baseline});
        }
        return route.fulfill({json:saved ? {...baseline,settings:saved} : baseline});
      });
      await page.route('**/api/settings', route => {
        saved = {...baseline.settings,...route.request().postDataJSON()};
        return route.fulfill({json:saved});
      });
      await page.goto(base + '/#setup');
      await ready(page);
      await page.locator('#monthly-cap').fill((cap / 1e6).toFixed(2));
      await page.locator('#default-source').selectOption(source);
      await page.evaluate(() => { void loadDashboard(); });
      await started;
      await page.locator('#save-settings').click();
      await page.waitForFunction(() => !state.saving);
      assert.equal(saved.monthly_cap_micro_aud, cap);
      releaseRefresh();
      await ready(page);
      assert.equal(await page.locator('#monthly-cap').inputValue(), (cap / 1e6).toFixed(2));
      assert.equal(await page.locator('#default-source').inputValue(), source);
      assert.equal(await page.evaluate(() => state.dirty), false);
      assert.ok(calls >= 3, 'Save queues and awaits a new snapshot after the old GET');
      return {saved_cap:cap / 1e6, saved_source:source, dashboard_requests:calls};
    });

    await probe('Malformed snapshots preserve usable data and run recovery', async page => {
      let response = baseline;
      let nonJSON = false;
      let posts = 0;
      await page.route('**/api/dashboard', route => nonJSON ? route.fulfill({status:502,contentType:'text/html',body:'<h1>Gateway unavailable</h1>'}) : route.fulfill({json:response}));
      await page.route('**/api/runs', route => { posts++; return route.fulfill({status:403,json:{code:'DASHBOARD_CSRF_REQUIRED'}}); });
      await page.goto(base);
      await ready(page);
      for (const malformed of [{}, {...baseline,leads:[{...baseline.leads[0],reason_codes:'bad'}]}]) {
        response = malformed;
        await page.evaluate(() => loadDashboard());
        assert.match(await page.locator('#error-text').innerText(), /incomplete workspace response/);
        assert.equal(await page.locator('.lead-row').count(), baseline.leads.length);
        assert.equal(await page.evaluate(() => state.data.settings.default_source), baseline.settings.default_source);
      }
      nonJSON = true;
      await page.evaluate(() => loadDashboard());
      assert.match(await page.locator('#error-text').innerText(), /incomplete workspace response/);
      assert.equal(await page.locator('.lead-row').count(), baseline.leads.length);
      nonJSON = false;
      await page.locator('#view-leads .run-button').click();
      await page.waitForFunction(() => !state.running && !state.loadPromise);
      assert.equal(posts, 1);
      assert.equal(await page.locator('#view-leads .run-button').isEnabled(), true);
      response = baseline;
      await page.locator('#retry-button').click();
      await page.locator('#error-banner').waitFor({state:'hidden'});
      return {malformed_cases:3, intercepted_run_requests:posts, recovered:true};
    });

    await probe('Skip link preserves each view and focuses its main content', async page => {
      await fixture(page);
      for (const view of ['leads','runs','setup']) {
        await page.goto(base + '/#' + view);
        await ready(page);
        await page.locator('.skip-link').focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => location.hash), '#' + view);
        assert.equal(await page.locator('.view:visible').getAttribute('id'), 'view-' + view);
        assert.equal(await page.evaluate(() => document.activeElement.id), 'main');
      }
      return {views:['leads','runs','setup']};
    });

    await probe('Initial loading disables dependent controls until a valid snapshot', async page => {
      let release;
      let signal;
      const started = new Promise(resolve => { signal = resolve; });
      await page.route('**/api/dashboard', async route => {
        signal();
        await new Promise(resolve => { release = resolve; });
        return route.fulfill({json:baseline});
      });
      await page.goto(base + '/#setup', {waitUntil:'domcontentloaded'});
      await started;
      for (const selector of ['#monthly-cap','#default-source','#lead-search','#source-filter','#tier-filter']) {
        assert.equal(await page.locator(selector).isDisabled(), true, selector);
      }
      assert.equal(await page.locator('.run-button').evaluateAll(buttons => buttons.every(button => button.disabled)), true);
      release();
      await ready(page);
      assert.equal(await page.locator('#monthly-cap').isEnabled(), true);
      await page.locator('#monthly-cap').fill('75.00');
      assert.equal(await page.evaluate(() => state.dirty), baseline.settings.monthly_cap_micro_aud !== 75000000);
      return {controls_enabled_after_load:true};
    });

    await probe('Empty workspace run prevents duplicate clicks and recovers from rejection', async page => {
      const empty = {...baseline,leads:[],runs:[],active_job:null,latest_job:null,summary:{total_leads:0,selected:0,needs_review:0,last_run_at:null}};
      let posts = 0;
      let release;
      await page.route('**/api/dashboard', route => route.fulfill({json:empty}));
      await page.route('**/api/runs', async route => {
        posts++;
        await new Promise(resolve => { release = resolve; });
        return route.fulfill({status:403,json:{code:'DASHBOARD_CSRF_REQUIRED'}});
      });
      await page.goto(base);
      await ready(page);
      const submitted = page.waitForRequest(request => request.url().endsWith('/api/runs'));
      await page.locator('#empty-action').click();
      await submitted;
      assert.equal(await page.locator('#empty-action').isDisabled(), true);
      await page.evaluate(() => { document.querySelector('#empty-action').click(); void beginRun(); });
      release();
      await page.waitForFunction(() => !state.running && !state.loadPromise);
      assert.equal(posts, 1);
      assert.equal(await page.locator('#empty-action').isEnabled(), true);
      assert.match(await page.locator('#error-text').innerText(), /session changed/);
      return {intercepted_run_requests:posts};
    });

    await probe('Offline first load keeps an honest disabled state and recovers', async page => {
      let online = false;
      await page.route('**/api/dashboard', route => online ? route.fulfill({json:baseline}) : route.abort('connectionrefused'));
      await page.goto(base);
      await page.locator('#error-banner').waitFor({state:'visible'});
      const offline = await page.locator('#lead-list').innerText();
      assert.match(offline, /engine is not connected/);
      assert.equal(await page.locator('#lead-search').isDisabled(), true);
      await page.evaluate(() => {
        document.querySelector('#lead-search').value = 'test';
        document.querySelector('#lead-search').dispatchEvent(new Event('input',{bubbles:true}));
      });
      assert.equal(await page.locator('#lead-list').innerText(), offline);
      assert.equal(await page.locator('#empty-action').count(), 0);
      online = true;
      await page.locator('#retry-button').click();
      await ready(page);
      assert.equal(await page.locator('#lead-search').isEnabled(), true);
      assert.equal(await page.locator('#error-banner').isVisible(), false);
      return {recovered:true};
    });

    await probe('Unsaved settings survive ordinary background refresh', async page => {
      await fixture(page);
      await page.goto(base + '/#setup');
      await ready(page);
      const cap = baseline.settings.monthly_cap_micro_aud === 89000000 ? '88.00' : '89.00';
      await page.locator('#monthly-cap').fill(cap);
      await page.evaluate(() => loadDashboard());
      assert.equal(await page.locator('#monthly-cap').inputValue(), cap);
      assert.equal(await page.evaluate(() => state.dirty), true);
      await page.locator('#reset-settings').click();
      assert.equal(await page.locator('#monthly-cap').inputValue(), (baseline.settings.monthly_cap_micro_aud / 1e6).toFixed(2));
      return {unsaved_input_preserved:true, discard_restores_saved_value:true};
    });

    await probe('Stale report errors persist across polling and recover explicitly', async page => {
      await fixture(page);
      let nonJSON = false;
      await page.route('**/api/reports/**/csv', route => nonJSON ? route.fulfill({status:502,contentType:'text/html',body:'<h1>Unavailable</h1>'}) : route.fulfill({status:409,json:{code:'REPORT_STALE'}}));
      await page.goto(base);
      await ready(page);
      await page.locator('.export-latest').click();
      await page.locator('#error-banner').waitFor({state:'visible'});
      assert.match(await page.locator('#error-text').innerText(), /needs to be refreshed/);
      await page.evaluate(() => loadDashboard());
      assert.equal(await page.locator('#error-banner').isVisible(), true);
      await page.locator('#retry-button').click();
      await page.locator('#error-banner').waitFor({state:'hidden'});
      nonJSON = true;
      await page.locator('.export-latest').click();
      await page.locator('#error-banner').waitFor({state:'visible'});
      assert.match(await page.locator('#error-text').innerText(), /incomplete report response/);
      return {error_persisted:true, recovered:true, non_json_error_explained:true};
    });

    await probe('Blocked popup opens report in this tab with a working CSV and Back', async page => {
      await fixture(page);
      const report = baseline.runs.find(run => run.reports?.html).reports;
      await page.route('**/api/reports/**/html', route => route.fulfill({contentType:'text/html',body:`<h1>Fixture report</h1><a href="${report.csv}">Download CSV</a>`}));
      await page.route('**/api/reports/**/csv', route => route.fulfill({contentType:'text/csv',headers:{'Content-Disposition':'attachment; filename="worklist.csv"'},body:'business_name\nFixture\n'}));
      await page.addInitScript(() => { window.open = () => null; });
      await page.goto(base + '/#runs');
      await ready(page);
      await page.locator('.report-link[data-kind="html"]').first().click();
      await page.waitForURL(base + report.html);
      const pending = page.waitForEvent('download');
      await page.getByRole('link',{name:'Download CSV'}).click();
      const download = await pending;
      assert.equal(await download.failure(), null);
      await page.goBack();
      await ready(page);
      assert.equal(await page.locator('.view:visible').getAttribute('id'), 'view-runs');
      return {csv_download:download.suggestedFilename(), back_restores_dashboard:true};
    });

    await probe('Blocked-popup report navigation respects unsaved-settings protection', async page => {
      await fixture(page);
      await page.route('**/api/reports/**/html', route => route.fulfill({contentType:'text/html',body:'<h1>Fixture report</h1>'}));
      await page.addInitScript(() => { window.open = () => null; });
      await page.goto(base + '/#setup');
      await ready(page);
      await page.locator('#monthly-cap').fill(baseline.settings.monthly_cap_micro_aud === 77000000 ? '76.00' : '77.00');
      await page.locator('nav a[data-view="runs"]').click();
      const pending = page.waitForEvent('dialog');
      page.once('dialog', dialog => dialog.dismiss());
      await page.locator('.report-link[data-kind="html"]').first().click();
      const dialog = await pending;
      assert.equal(dialog.type(), 'beforeunload');
      assert.equal(await page.evaluate(() => location.hash), '#runs');
      assert.equal(await page.evaluate(() => state.dirty), true);
      return {unsaved_dialog:'beforeunload', cancelled_navigation_preserves_changes:true};
    });

    await probe('Operational notices stay visible while other workflows remain usable', async page => {
      const message = 'One run receipt needs repair. Other workspace actions remain available. <img src=x>';
      const data = {...baseline,operational_notices:[{code:'DASHBOARD_JOB_RECEIPTS_UNAVAILABLE',count:1,message}]};
      await page.route('**/api/dashboard', route => route.fulfill({json:data}));
      await page.goto(base);
      await ready(page);
      assert.equal(await page.locator('#operational-notices').getAttribute('role'), 'status');
      assert.equal(await page.locator('#operational-notices').innerText(), message);
      assert.equal(await page.locator('#operational-notices img').count(), 0);
      await page.evaluate(() => {
        window.noticeChanges = 0;
        new MutationObserver(() => { window.noticeChanges++; }).observe(document.querySelector('#operational-notices'),{childList:true,subtree:true});
      });
      await page.locator('#lead-search').fill(baseline.leads[0].business_name);
      assert.ok(await page.locator('.lead-row').count() > 0);
      await page.locator('nav a[data-view="setup"]').click();
      await page.evaluate(() => loadDashboard(true));
      assert.equal(await page.locator('#operational-notices').isVisible(), true);
      assert.equal(await page.locator('#monthly-cap').isEnabled(), true);
      assert.equal(await page.evaluate(() => window.noticeChanges), 0, 'Unchanged notices should not be announced again on each refresh');
      return {notice_persistent:true, text_escaped:true, controls_usable:true, unchanged_notices_not_reannounced:true};
    });

    await probe('Malformed action confirmations do not claim success or corrupt data', async page => {
      await fixture(page);
      await page.route('**/api/settings', route => route.fulfill({json:{}}));
      await page.route('**/api/runs', route => route.fulfill({json:{}}));
      await page.goto(base + '/#setup');
      await ready(page);
      await page.locator('#monthly-cap').fill(baseline.settings.monthly_cap_micro_aud === 66000000 ? '65.00' : '66.00');
      await page.locator('#save-settings').click();
      await page.waitForFunction(() => !state.saving);
      assert.match(await page.locator('#settings-error').innerText(), /did not confirm the saved settings/);
      assert.equal(await page.evaluate(() => state.dirty), true);
      assert.equal(await page.evaluate(() => state.data.settings.monthly_cap_micro_aud), baseline.settings.monthly_cap_micro_aud);
      await page.locator('#reset-settings').click();
      await page.locator('nav a[data-view="runs"]').click();
      await page.locator('#view-runs > .page-heading .run-button').click();
      await page.waitForFunction(() => !state.running && !state.loadPromise);
      assert.match(await page.locator('#error-text').innerText(), /did not confirm the run status/);
      assert.ok(await page.evaluate(() => state.requestId), 'Uncertain run response retains its retry identity');
      return {settings_remain_unsaved:true, run_retry_identity_preserved:true};
    });

    await fs.mkdir(output,{recursive:true});
    const receipt = {status:'passed',checked_at:new Date().toISOString(),suite:'intercepted resilience regressions',checks,actual_api_mutations:0,browser_errors:[]};
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify(receipt,null,2));
    console.log(JSON.stringify(receipt,null,2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
