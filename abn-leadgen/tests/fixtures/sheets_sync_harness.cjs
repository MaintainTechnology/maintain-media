// Execute the actual reviewed Apps Script source against a minimal Sheets API.
const fs = require('node:fs'), vm = require('node:vm'), crypto = require('node:crypto');
const assert = require('node:assert/strict');
const [bundlePath, schemaPath, scenario] = process.argv.slice(2);
const columns = JSON.parse(fs.readFileSync(schemaPath, 'utf8')).required;
const copy = value => JSON.parse(JSON.stringify(value));
const owner = 'owner@example.test', book = 'syntheticBook123';
const worklistId = crypto.randomUUID();
function row(changes = {}) {
  return {...Object.fromEntries(columns.map(name => [name, ''])),
    row_id: crypto.randomUUID(), worklist_id: worklistId, lead_id: crypto.randomUUID(), group_id: crypto.randomUUID(),
    row_version: 1, generated_at: new Date().toISOString(), signal: 'qbcc_backlog', tier: 'A', score: 70,
    business_name: 'Synthetic local test', safe_contact_view: 'synthetic@example.test',
    gate_label: 'Email: needs send-time checks', status: 'not_started', attempts: 0, invitation_state: 'unknown',
    save_state: 'Not started', source: 'QBCC', ...changes};
}
function make(records = [], options = {}) {
  let data = [copy(columns), ...records.map(record => columns.map(name => record[name]))];
  const props = {ENABLED: 'true', INSTALLER_EMAIL: owner, SPREADSHEET_ID: book, WORKLIST_SHEET_ID: '42',
    ALLOWED_EDITOR_EMAILS: JSON.stringify([owner]), API_BASE_URL: 'https://engine.example.test',
    SERVICE_SIGNING_KEY: 'synthetic-test-signing-'+'a'.repeat(32), BRIDGE_SECRET: 'synthetic-test-hmac-'+'b'.repeat(32)};
  let writes = [], fetches = [], triggers = [], maxRows = 2001;
  let next = response(records);
  const user = email => ({getEmail: () => email});
  const sheet = {getLastColumn: () => columns.length, getLastRow: () => data.length, getMaxRows: () => maxRows,
    getSheetId: () => 42, getParent: () => ({getId: () => book}),
    insertRowsAfter: (after, count) => {assert.equal(after, maxRows); maxRows += count;},
    getRange: (r, c, rows = 1, cols = 1) => {
      const range = {getValues: () => Array.from({length: rows}, (_, y) => Array.from({length: cols}, (_, x) => data[r+y-1]?.[c+x-1] ?? '')),
        getValue: () => data[r-1]?.[c-1] ?? '',
        setValue: value => range.setValues([[value]]),
        setValues: values => {
          assert.equal(values.length, rows);
          values.forEach((valuesRow, y) => {assert.equal(valuesRow.length, cols); valuesRow.forEach((value, x) => {
            writes.push({r: r+y, c: c+x, value});
            if (options.ignoreContactWrites && columns[c+x-1] === 'safe_contact_view') return;
            while (data.length < r+y) data.push(Array(columns.length).fill(''));
            data[r+y-1][c+x-1] = value;
          });});
          return range;
        }};
      return range;
    }};
  const ctx = {Date, Set, Map, JSON, Object, Array, Number, String, PropertiesService: {getScriptProperties: () => ({
    getProperty: key => props[key], setProperty: (key, value) => {props[key] = value;},
    getProperties: () => copy(props), deleteProperty: key => {delete props[key];}})},
    Session: {getEffectiveUser: () => user(owner)},
    LockService: {getScriptLock: () => ({tryLock: () => !options.busy, releaseLock: () => {}})},
    SpreadsheetApp: {getActiveSpreadsheet: () => null, openById: id => {assert.equal(id, book); return {getSheets: () => [sheet]};}, flush: () => {}},
    DriveApp: {Access: {PRIVATE: 'private'}, getFileById: () => ({getOwner: () => user(owner),
      getSharingAccess: () => options.public ? 'public' : 'private', getEditors: () => options.unmapped ? [user('other@example.test')] : [], getViewers: () => []})},
    Utilities: {Charset: {UTF_8: 'utf8'}, DigestAlgorithm: {SHA_256: 'sha256'}, getUuid: () => crypto.randomUUID(),
      base64EncodeWebSafe: value => Buffer.from(typeof value === 'string' ? value : Uint8Array.from(value)).toString('base64url'),
      computeDigest: (_, value) => Array.from(crypto.createHash('sha256').update(value).digest()),
      computeHmacSha256Signature: (value, key) => Array.from(crypto.createHmac('sha256', key).update(value).digest())},
    UrlFetchApp: {fetch: (url, request) => {fetches.push({url, request: copy(request)}); return {
      getResponseCode: () => options.unavailable ? 503 : 200, getContentText: () => JSON.stringify(next)};}},
    ScriptApp: {EventType: {CLOCK: 'clock'}, TriggerSource: {CLOCK: 'clock'}, getProjectTriggers: () => triggers,
      newTrigger: handler => {const t = {handler, minutes: null, getHandlerFunction: () => handler,
        getEventType: () => 'clock', getTriggerSource: () => 'clock'};
        const builder = {timeBased: () => builder, everyMinutes: minutes => {t.minutes = minutes; return builder;},
          create: () => {triggers.push(t); return t;}}; return builder;}}};
  vm.createContext(ctx); vm.runInContext(fs.readFileSync(bundlePath, 'utf8'), ctx);
  function response(rows) { const now = Date.now(); return {schema_version: 1, spreadsheet_id: book, sheet_id: 42,
    owner_email: owner, reader_emails: [owner], snapshot_id: crypto.randomUUID(), generated_at: new Date(now).toISOString(),
    expires_at: new Date(now+90000).toISOString(), disclosure_allowed: true, reason_codes: [],
    columns: copy(columns), worklist_id: worklistId, rows: copy(rows)}; }
  return {ctx, sheet, props, writes, fetches, triggers, response, setResponse: value => {next = value;},
    getRows: () => data.slice(1).map(values => Object.fromEntries(columns.map((name, i) => [name, values[i]]))),
    edit: (index, changes) => {for (const [name, value] of Object.entries(changes)) data[index][columns.indexOf(name)] = value;},
    swap: () => {data = [data[0], data[2], data[1]];}};
}
const source = row(), alternate = row({business_name: 'Another synthetic business'});
if (scenario === 'positive_idempotent') {
  const h = make(); h.setResponse(h.response([source, alternate]));
  assert.equal(h.ctx.syncLiveWorklist().addedRows, 2);
  assert.equal(h.ctx.syncLiveWorklist().addedRows, 0);
  assert.equal(h.getRows().length, 2);
  const receipt = JSON.parse(h.props.LAST_PULL_RECEIPT);
  assert.equal(receipt.currentRows, 2); assert.ok(!JSON.stringify(receipt).includes(source.safe_contact_view));
  const req = h.fetches[0].request;
  assert.equal(req.method, 'get'); assert.ok(!Object.hasOwn(req, 'payload'));
  const claims = JSON.parse(Buffer.from(req.headers.Authorization.split('.')[1], 'base64url').toString());
  assert.equal(claims.method, 'GET'); assert.equal(claims.path, '/v1/sheets/worklist');
  assert.equal(claims.body_sha256, crypto.createHash('sha256').update('').digest('hex'));
} else if (scenario === 'pending_sorted') {
  const h = make([source, alternate]); h.swap();
  const changes = {notes: 'unsaved private test note', status: 'meeting_booked', attempts: 5,
    invitation_state: 'invited', invitation_evidence_ref: 'test-reference', occurred_at: '2026-09-01T12:00:00.000Z', row_version: 7};
  h.edit(2, changes);
  h.props['pending:test'] = JSON.stringify({rowId: source.row_id, body: {status: 'meeting_booked'}});
  h.setResponse(h.response([{...source, row_version: 8}, alternate]));
  h.ctx.syncLiveWorklist();
  const preserved = h.getRows().find(r => r.row_id === source.row_id);
  for (const [key, value] of Object.entries(changes)) assert.equal(preserved[key], value);
  assert.match(preserved.save_state, /Pending/);
  assert.ok(h.writes.every(write => !['notes','status','attempts','invitation_state','invitation_evidence_ref','occurred_at'].includes(columns[write.c-1])));
} else if (scenario === 'invalid_unsaved_without_event') {
  const h = make([source]); h.edit(1, {notes: 'unsaved', attempts: 'not valid', row_version: 7});
  h.setResponse(h.response([{...source, row_version: 8}])); h.ctx.syncLiveWorklist();
  assert.equal(h.getRows()[0].notes, 'unsaved'); assert.equal(h.getRows()[0].attempts, 'not valid');
  assert.equal(h.getRows()[0].row_version, 7); assert.match(h.getRows()[0].save_state, /differs/);
} else if (scenario === 'withdrawn_and_retired') {
  const h = make([source, alternate]); h.edit(2, {notes: 'pending outcome remains'});
  h.setResponse(h.response([{...source, safe_contact_view: 'Masked — contact blocked', gate_label: 'Do not contact'}]));
  h.ctx.refreshWorklistRestrictions();
  assert.ok(h.getRows().every(r => r.safe_contact_view === 'Masked — contact blocked'));
  assert.equal(h.getRows()[1].business_name, ''); assert.equal(h.getRows()[1].notes, 'pending outcome remains');
} else if (scenario === 'pending_stop_never_redisclosed') {
  const h = make([source]); h.props['pending:stop'] = JSON.stringify({rowId: source.row_id, body: {status: 'do_not_contact_requested'}});
  h.ctx.syncLiveWorklist(); assert.equal(h.getRows()[0].safe_contact_view, 'Masked — contact blocked');
} else if (scenario === 'closed_gate') {
  const h = make([source]); h.edit(1, {notes: 'unsaved'});
  h.setResponse({...h.response([]), disclosure_allowed: false, reason_codes: ['GATE_G5_CLOSED']});
  assert.equal(h.ctx.syncLiveWorklist().disclosureAllowed, false);
  assert.equal(h.getRows()[0].safe_contact_view, 'Masked — contact blocked'); assert.equal(h.getRows()[0].notes, 'unsaved');
} else if (scenario === 'restriction_tick_never_adds') {
  const h = make([source]); h.setResponse(h.response([source, alternate]));
  assert.equal(h.ctx.refreshWorklistRestrictions().addedRows, 0); assert.equal(h.getRows().length, 1);
} else if (scenario === 'malformed_before_apply') {
  const cases = [p => {p.rows.push(p.rows[0]);}, p => {p.rows[0].raw_endpoint = 'forbidden';},
    p => {p.spreadsheet_id = 'anotherBook';}, p => {p.sheet_id = 0;}, p => {p.rows[0].worklist_id = crypto.randomUUID();},
    p => {p.rows[0].row_id = 'invalid';}, p => {p.expires_at = new Date(Date.now()-1).toISOString();},
    p => {p.reader_emails.push('other@example.test');}];
  for (const change of cases) {
    const h = make([source]); const p = h.response([source]); change(p); h.setResponse(p);
    assert.throws(() => h.ctx.syncLiveWorklist()); assert.ok(!h.props.LAST_PULL_RECEIPT);
    assert.equal(h.getRows()[0].safe_contact_view, 'Masked — contact blocked');
    assert.ok(h.writes.every(write => !['notes','status','attempts','invitation_state','invitation_evidence_ref','occurred_at'].includes(columns[write.c-1])));
  }
} else if (scenario === 'local_identity_conflict') {
  for (const local of [[source, source], [{...source, lead_id: crypto.randomUUID()}]]) {
    const h = make(local); h.setResponse(h.response([source])); assert.throws(() => h.ctx.syncLiveWorklist());
    assert.ok(!h.props.LAST_PULL_RECEIPT); assert.equal(h.getRows()[0].lead_id, local[0].lead_id);
  }
} else if (scenario === 'privacy_and_availability_fail_closed') {
  for (const options of [{public: true}, {unmapped: true}, {unavailable: true}]) {
    const h = make([source], options); assert.throws(() => h.ctx.syncLiveWorklist());
    assert.equal(h.getRows()[0].business_name, ''); assert.equal(h.getRows()[0].safe_contact_view, 'Masked — contact blocked');
    if (!options.unavailable) assert.equal(h.fetches.length, 0);
  }
  const h = make([source]); h.props.ENABLED = 'false';
  assert.equal(h.ctx.syncLiveWorklist().enabled, false); assert.equal(h.fetches.length, 0);
  assert.equal(h.getRows()[0].safe_contact_view, 'Masked — contact blocked');
} else if (scenario === 'literal_formula') {
  const h = make(); const formula = '  =IMPORTXML("https://invalid.test", "//data")';
  h.setResponse(h.response([{...source, business_name: formula, notes: formula, safe_contact_view: '+61400000000'}]));
  h.ctx.syncLiveWorklist(); assert.equal(h.getRows()[0].business_name, "'"+formula);
  assert.equal(h.getRows()[0].notes, "'"+formula); assert.equal(h.getRows()[0].safe_contact_view, "'+61400000000");
} else if (scenario === 'readback_failure_no_receipt') {
  const h = make([source], {ignoreContactWrites: true});
  h.setResponse(h.response([{...source, safe_contact_view: 'Masked — contact blocked', gate_label: 'Do not contact'}]));
  assert.throws(() => h.ctx.syncLiveWorklist()); assert.ok(!h.props.LAST_PULL_RECEIPT);
} else if (scenario === 'activation_idempotent_and_gated') {
  const h = make(); h.props.ENABLED = 'false'; h.setResponse(h.response([]));
  h.ctx.enableVerifiedWorklistSync(); h.ctx.enableVerifiedWorklistSync();
  assert.equal(h.triggers.length, 2); assert.equal(h.props.ENABLED, 'true');
  assert.deepEqual(h.triggers.map(t => t.minutes).sort(), [1,5]);
  const bad = make([source]); bad.setResponse({...bad.response([]), disclosure_allowed: false});
  assert.throws(() => bad.ctx.enableVerifiedWorklistSync()); assert.equal(bad.props.ENABLED, 'false');
  assert.equal(bad.triggers.length, 0); assert.equal(bad.getRows()[0].safe_contact_view, 'Masked — contact blocked');
} else throw new Error('Unknown test scenario');
process.stdout.write('PASS '+scenario);
