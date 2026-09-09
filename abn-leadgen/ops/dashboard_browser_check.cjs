/* Fixture-only browser acceptance. Run from any cwd with the local dashboard up.
 * Uses the repository's existing Playwright dependency. Restores run defaults.
 */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.env.ABR_DASHBOARD_TEST_URL || 'http://127.0.0.1:8767';
const output = process.env.ABR_DASHBOARD_TEST_OUTPUT || path.join(__dirname,'acceptance','dashboard-browser');

(async () => {
  await fs.mkdir(output,{recursive:true});
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  const page = await context.newPage();
  const errors = [];
  const checks = [];
  let original;
  page.on('pageerror',error => errors.push(error.message));
  try {
    await page.goto(base + '/report.html');
    await page.locator('.lead-row').first().waitFor();
    const initial = await (await page.request.get(base + '/api/dashboard')).json();
    original = initial.settings;
    assert.equal(initial.mode,'fixture');
    assert.equal(await page.locator('#connection-label').innerText(),'Engine connected');
    checks.push('Previous report URL opens dashboard with actual stored lead data');

    const linked = initial.leads.find(lead => lead.abn);
    assert.ok(linked,'fixture database must have a linked sample ABN');
    await page.locator('#lead-search').fill(linked.abn);
    assert.ok(await page.locator('.lead-row').count() >= 1);
    await page.locator('.lead-row').first().click();
    assert.ok((await page.locator('#lead-detail').innerText()).includes(linked.business_name));
    await page.locator('#source-filter').selectOption(linked.source === 'abr' ? 'qbcc' : 'abr');
    assert.equal(await page.locator('.lead-row').count(),0);
    await page.locator('#empty-action').click();
    assert.equal(await page.locator('.lead-row').count(),initial.leads.length);
    await page.locator('#tier-filter').selectOption('C');
    assert.equal(await page.locator('.lead-row').count(),initial.leads.filter(lead=>lead.tier==='C').length);
    await page.locator('#tier-filter').selectOption('all');
    checks.push('ABN search, combined source/tier filters, empty-state recovery, lead details');

    await page.locator('.lead-row').first().focus();
    const focusId = await page.locator('.lead-row').first().getAttribute('data-lead-id');
    await page.evaluate(() => loadDashboard());
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.leadId),focusId);
    checks.push('Background refresh preserves keyboard focus on the selected business');

    await page.locator('nav a[data-view="setup"]').click();
    await page.locator('#default-source').selectOption('qbcc');
    await page.locator('#monthly-cap').fill('100.50');
    await page.locator('#save-settings').click();
    await page.waitForFunction(() => document.querySelector('#save-settings').textContent === 'Save changes' && document.querySelector('#save-settings').disabled);
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#monthly-cap').value === '100.50');
    assert.equal(await page.locator('#default-source').inputValue(),'qbcc');
    assert.match(await page.locator('#budget-note').innerText(),/Effective limit this month: \$100\.50/);
    await page.locator('#monthly-cap').fill('151');
    assert.equal(await page.locator('#monthly-cap').evaluate(el=>el.checkValidity()),false);
    await page.locator('#reset-settings').click();
    assert.equal(await page.locator('#monthly-cap').inputValue(),'100.50');
    checks.push('Settings save across reload, effective budget displayed, invalid amount rejected, discard works');

    await page.locator('nav a[data-view="runs"]').click();
    const beforeRun = await (await page.request.get(base + '/api/dashboard')).json();
    await page.locator('#view-runs > .page-heading .run-button').click();
    await page.waitForFunction(() => {
      const text = document.querySelector('#active-run').innerText;
      return text.includes('Your run is complete.') || text.includes('Your run needs attention.');
    },null,{timeout:90000});
    const after = await (await page.request.get(base + '/api/dashboard')).json();
    assert.notEqual(after.latest_job.run_id,beforeRun.latest_job?.run_id);
    assert.equal(after.latest_job.state,'complete');
    assert.equal(after.latest_job.source,'qbcc');
    assert.equal(after.latest_job.monthly_cap_micro_aud,100500000);
    await page.reload();
    await page.locator('#active-run').waitFor({state:'visible'});
    assert.match(await page.locator('#active-run').innerText(),/Your run is complete/);
    checks.push('Actual fixture run uses saved source/cap, reaches completion, receipt survives reload');

    const downloadPromise = page.waitForEvent('download');
    await page.locator('.report-link[data-kind="csv"]').first().click();
    const download = await downloadPromise;
    await download.saveAs(path.join(output,'worklist.csv'));
    const csv = await fs.readFile(path.join(output,'worklist.csv'),'utf8');
    assert.ok(csv.includes('business_name') && csv.includes('row_id'));
    const popupPromise = context.waitForEvent('page');
    await page.locator('.report-link[data-kind="html"]').first().click();
    const report = await popupPromise;
    await report.waitForURL(/\/api\/reports\/.*\/html/);
    await report.locator('h1').waitFor();
    assert.match(await report.locator('h1').innerText(),/Private review worklist/);
    const nestedDownloadPromise = report.waitForEvent('download');
    await report.getByRole('link',{name:'Download private worklist CSV'}).click();
    await nestedDownloadPromise;
    await report.close();
    checks.push('Run CSV downloads, report opens, report’s own CSV link downloads');
    await page.locator('.report-link').first().focus();
    const focusedReport = await page.locator('.report-link').first().getAttribute('href');
    await page.evaluate(() => loadDashboard());
    assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('href')),focusedReport);
    checks.push('Background refresh preserves keyboard focus on report downloads');

    await page.route('**/api/runs', route => route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({code:'DASHBOARD_CSRF_REQUIRED'})}));
    await page.locator('#view-runs > .page-heading .run-button').click();
    await page.locator('#error-banner').waitFor({state:'visible'});
    await page.evaluate(() => loadDashboard());
    assert.equal(await page.locator('#error-banner').isVisible(),true);
    assert.match(await page.locator('#error-text').innerText(),/session changed/);
    await page.unroute('**/api/runs');
    await page.locator('#retry-button').click();
    await page.locator('#error-banner').waitFor({state:'hidden'});
    checks.push('Rejected run remains visible across background refresh and has working recovery');

    await page.locator('nav a[data-view="setup"]').click();
    await page.locator('#default-source').selectOption(original.default_source);
    await page.locator('#monthly-cap').fill((original.monthly_cap_micro_aud / 1e6).toFixed(2));
    await page.locator('#save-settings').click();
    await page.waitForFunction(() => document.querySelector('#save-settings').disabled && document.querySelector('#save-settings').textContent === 'Save changes');
    for (const viewport of [{name:'desktop',width:1440,height:1000},{name:'tablet',width:820,height:1180},{name:'mobile',width:390,height:844},{name:'small-mobile',width:360,height:800}]) {
      await page.setViewportSize(viewport);
      for (const view of ['leads','runs','setup']) {
        await page.locator(`nav a[data-view="${view}"]`).click();
        await page.evaluate(()=>window.scrollTo(0,0));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth),false,`${viewport.name} ${view} overflow`);
        if (viewport.name === 'mobile' && view === 'leads') assert.ok((await page.locator('.lead-row').first().boundingBox()).y < 844,'First lead should enter the opening phone viewport');
        if (viewport.width <= 390 && view === 'runs') {
          const action = await page.locator('.report-link').first().boundingBox();
          assert.ok(action.x >= 0 && action.x + action.width <= viewport.width,'Phone report actions visible without horizontal scrolling');
        }
        await page.screenshot({path:path.join(output,`${viewport.name}-${view}.png`),fullPage:true});
      }
    }
    checks.push('All 3 views fit 1440, 820, 390 and 360px without page overflow');
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.locator('nav a[data-view="leads"]').click();
    assert.equal(await page.locator('.button').first().evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
    assert.deepEqual(errors,[]);
    checks.push('Reduced motion respected; no browser JavaScript errors');
    const receipt = {status:'passed',checked_at:new Date().toISOString(),checks,run_id:after.latest_job.run_id,viewports:[1440,820,390,360],browser_errors:errors};
    await fs.writeFile(path.join(output,'result.json'),JSON.stringify(receipt,null,2));
    console.log(JSON.stringify(receipt,null,2));
  } finally {
    if (original) {
      const latest = await (await page.request.get(base + '/api/dashboard')).json();
      await page.request.patch(base + '/api/settings',{headers:{Origin:base,'X-Dashboard-CSRF':latest.csrf_token},data:{default_source:original.default_source,monthly_cap_micro_aud:original.monthly_cap_micro_aud}});
    }
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
