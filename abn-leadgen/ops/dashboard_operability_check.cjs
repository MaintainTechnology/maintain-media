/* Real fixture workflows across every dashboard entry point; restores preferences.
 * Backend fault cases are isolated in pytest; browser fault cases use intercepted I/O.
 */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = 'http://127.0.0.1:8767';
const destination = path.join(__dirname,'acceptance',`operability-${new Date().toISOString().replace(/[:.]/g,'-')}`);
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));

(async () => {
  await fs.mkdir(destination,{recursive:true});
  const browser = await chromium.launch();
  const context = await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  const page = await context.newPage();
  const errors = [];
  const checks = [];
  const runs = [];
  const controls = new Map();
  let original;
  page.on('pageerror',error=>errors.push(error.message));
  async function snapshot() {
    const response = await page.request.get(base+'/api/dashboard');
    assert.equal(response.status(),200);
    return response.json();
  }
  async function switchView(view) {
    await page.locator(`nav [data-view="${view}"]`).click();
    await page.locator(`#view-${view}`).waitFor({state:'visible'});
    assert.equal(await page.locator(`nav [data-view="${view}"]`).getAttribute('aria-current'),'page');
    for (const control of await page.locator('button:visible,a:visible,input:visible,select:visible').evaluateAll(elements=>elements.map(el=>({tag:el.tagName,text:(el.textContent||'').trim().replace(/\s+/g,' '),id:el.id,href:el.getAttribute('href')})))) {
      controls.set(`${view}:${control.tag}:${control.id || control.text}:${control.href}`,{view,...control});
    }
  }
  async function save(source,cap) {
    await switchView('setup');
    await page.locator('#default-source').selectOption(source);
    await page.locator('#monthly-cap').fill(cap);
    if (await page.locator('#save-settings').isEnabled()) {
      const response = page.waitForResponse(r=>r.url().endsWith('/api/settings') && r.request().method()==='PATCH');
      await page.locator('#save-settings').click();
      assert.equal((await response).status(),200);
      await page.waitForFunction(()=>!state.saving && !state.loading);
    }
    const saved = await snapshot();
    assert.equal(saved.settings.default_source,source);
    assert.equal(saved.settings.monthly_cap_micro_aud,Math.round(Number(cap)*1e6));
  }
  try {
    await page.goto(base+'/report.html');
    await page.locator('.lead-row').first().waitFor();
    original = (await snapshot()).settings;
    for (const view of ['leads','runs','setup']) await switchView(view);
    await page.locator('.brand').click();
    await page.locator('#view-leads').waitFor({state:'visible'});
    await page.locator('.demo-note a').click();
    await page.locator('#view-setup').waitFor({state:'visible'});
    await page.locator('.sidebar-bottom a').click();
    assert.equal(page.url(),base+'/report.html#setup');
    checks.push('All navigation, brand/home and setup entry links operate');

    for (const [source,view,cap,width] of [['all','leads','150.00',1440],['abr','runs','150.00',1440],['qbcc','leads','149.99',390]]) {
      await page.setViewportSize({width,height:900});
      await save(source,cap);
      await page.reload();
      await page.waitForFunction(()=>state.data && !state.loading);
      assert.equal(await page.locator('#default-source').inputValue(),source);
      await switchView(view);
      const response = page.waitForResponse(r=>r.url().endsWith('/api/runs') && r.request().method()==='POST');
      await page.locator(`#view-${view} > .page-heading .run-button`).click();
      const submitted = await response;
      assert.equal(submitted.status(),202);
      const job = await submitted.json();
      let final = job;
      for (let tries=0; ['queued','running'].includes(final.state) && tries<120; tries++) {
        await delay(400);
        final = await (await page.request.get(base+'/api/jobs/'+job.job_id)).json();
      }
      assert.equal(final.state,'complete',JSON.stringify(final));
      assert.equal(final.source,source);
      assert.equal(final.monthly_cap_micro_aud,Math.round(Number(cap)*1e6));
      await page.locator('#view-runs .refresh-button').click();
      await page.waitForFunction(()=>!state.loading);
      assert.match(await page.locator('#active-run').innerText(),/Your run is complete/);
      const current = await snapshot();
      const run = current.runs.find(run=>run.run_id===final.run_id);
      assert.ok(run?.reports);
      for (const kind of ['html','csv','markdown']) {
        const download = await page.request.get(base+run.reports[kind]);
        assert.equal(download.status(),200,`${source} ${kind}`);
        assert.ok((await download.body()).length>0);
      }
      runs.push(final);
      checks.push(`${source.toUpperCase()} run from ${view} at ${width}px: persisted configuration, actual completion, HTML/CSV/Markdown valid`);
    }
    await save(original.default_source,(original.monthly_cap_micro_aud/1e6).toFixed(2));

    await switchView('leads');
    const stateBefore = await snapshot();
    for (const lead of stateBefore.leads) {
      await page.locator('#lead-search').fill(lead.business_name);
      assert.ok(await page.locator('.lead-row').count()>0);
      await page.locator('.lead-row').first().click();
      assert.match(await page.locator('#lead-detail').innerText(),new RegExp(lead.business_name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
      if (lead.abn) {
        await page.locator('#lead-search').fill(lead.abn.replace(/^(\d{2})(\d{3})(\d{3})(\d{3})$/,'$1 $2 $3 $4'));
        assert.ok(await page.locator('.lead-row').count()>0);
      }
    }
    await page.locator('#lead-search').fill('no-such-business-for-operability-check');
    assert.equal(await page.locator('.lead-row').count(),0);
    await page.locator('#empty-action').click();
    for (const source of ['abr','qbcc','all']) {
      await page.locator('#source-filter').selectOption(source);
      for (const tier of ['A','B','C','all']) {
        await page.locator('#tier-filter').selectOption(tier);
        assert.equal(await page.locator('.lead-row').count(),stateBefore.leads.filter(lead=>(source==='all'||lead.source===source)&&(tier==='all'||lead.tier===tier)).length);
      }
    }
    checks.push('Every stored lead opens; name/formatted ABN search and all 12 source/tier combinations match the database');
    const exportPromise = page.waitForEvent('download');
    await page.locator('.export-latest').click();
    const exported = await exportPromise;
    assert.equal(exported.suggestedFilename(),'worklist.csv');
    await exported.saveAs(path.join(destination,'latest.csv'));
    checks.push('Latest-leads Export CSV button downloads the current selected worklist');
    await page.locator('#view-leads .refresh-button').click();
    await page.waitForFunction(()=>!state.loading);
    checks.push('Both screen Refresh buttons work');

    for (const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844},{width:360,height:800}]) {
      await page.setViewportSize(viewport);
      for (const view of ['leads','runs','setup']) {
        await switchView(view);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      }
    }
    assert.deepEqual(errors,[]);
    checks.push('All views remain operable at desktop/tablet/phone widths; zero uncaught browser errors');
    await page.setViewportSize({width:1440,height:1000});
    await switchView('leads');
    await page.screenshot({path:path.join(destination,'desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(destination,'mobile.png'),fullPage:true});
    const receipt = {status:'passed',checked_at:new Date().toISOString(),checks,runs,controls:[...controls.values()],browser_errors:errors};
    await fs.writeFile(path.join(destination,'result.json'),JSON.stringify(receipt,null,2));
    console.log(JSON.stringify({status:receipt.status,evidence:destination,checks,runs:runs.map(({source,run_id,state})=>({source,run_id,state})),controls:controls.size,browser_errors:errors},null,2));
  } finally {
    if (original) {
      const current = await snapshot();
      const restored = await page.request.patch(base+'/api/settings',{headers:{Origin:base,'X-Dashboard-CSRF':current.csrf_token},data:{default_source:original.default_source,monthly_cap_micro_aud:original.monthly_cap_micro_aud}});
      assert.equal(restored.status(),200,'Original settings must be restored');
    }
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
