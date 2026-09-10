/** Reviewed standalone bundle. Generated from the named integration sources.
 * Run prepareMaintainMediaWorklist as jeph@quotemax.com.au. Leaves all API access disabled.
 */
/** Private Sheet bridge v1. Install only after G5 sandbox certification.
 * Script properties: ENABLED=false, API_BASE_URL, SERVICE_SIGNING_KEY, BRIDGE_SECRET.
 * Server must validate signed editor context, body digest, timestamp freshness and
 * assigned actor scopes; service credentials alone must not impersonate reviewers.
 * Installable edit trigger uses onWorklistEdit; repair trigger uses repairPendingEdits
 * every five minutes. Never deploy as a public web app or use a weekly opt-out sync.
 */
const EDITABLE = ['status', 'attempts', 'invitation_state', 'invitation_evidence_ref', 'notes', 'occurred_at'];
const STATUSES = ['not_started', 'no_usable_contact', 'attempted_no_answer', 'contacted_not_interested', 'contacted_nurture', 'meeting_booked', 'meeting_held', 'disqualified', 'do_not_contact_requested'];
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function headers_(sheet) {
  const names = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  if (new Set(names).size !== names.length) throw new Error('Duplicate column names; not saved');
  const map = {};
  names.forEach((name, index) => { map[name] = index + 1; });
  ['row_id', 'worklist_id', 'lead_id', 'group_id', 'row_version', 'save_state'].concat(EDITABLE).forEach(name => {
    if (!map[name]) throw new Error('Missing required worklist column');
  });
  return map;
}

function findRow_(sheet, map, id) {
  const rows = sheet.getLastRow() > 1 ? sheet.getRange(2, map.row_id, sheet.getLastRow() - 1, 1).getValues() : [];
  const matches = [];
  rows.forEach((value, i) => { if (String(value[0]) === id) matches.push(i + 2); });
  if (matches.length !== 1) throw new Error('Missing or duplicate immutable row ID; refresh worklist');
  return matches[0];
}

function saveState_(sheet, id, message) {
  const map = headers_(sheet);
  sheet.getRange(findRow_(sheet, map, id), map.save_state).setValue(message);
}

function onWorklistEdit(event) {
  if (!event || event.range.getRow() === 1) return;
  const sheet = event.range.getSheet();
  const map = headers_(sheet);
  const touched = Object.keys(map).find(name => map[name] === event.range.getColumn());
  if (!EDITABLE.includes(touched)) return;
  // Bulk ordinary edits need explicit row-by-row review. Stop requests are routed now.
  if (event.range.getNumRows() !== 1 || event.range.getNumColumns() !== 1) {
    if (event.range.getColumn() <= map.status && event.range.getLastColumn() >= map.status) {
      for (let index = event.range.getRow(); index <= event.range.getLastRow(); index++) {
        if (sheet.getRange(index, map.status).getValue() === 'do_not_contact_requested') {
          onWorklistEdit({range: sheet.getRange(index, map.status), user: event.user});
        }
      }
    }
    throw new Error('Not saved: edit one outcome field at a time; use immediate control opt-out for stop requests');
  }
  const actor = event.user && event.user.getEmail();
  const values = sheet.getRange(event.range.getRow(), 1, 1, sheet.getLastColumn()).getValues()[0];
  const get = name => values[map[name] - 1];
  const id = String(get('row_id'));
  const isOptout = get('status') === 'do_not_contact_requested';
  const failure = isOptout ? 'Do not contact; opt-out not yet saved. Retry control API immediately; escalate to operator.' : 'Not saved; refresh or retry.';
  try {
    if (!actor) throw new Error('Editor identity unavailable');
    ['row_id', 'worklist_id', 'lead_id', 'group_id'].forEach(name => {
      if (!UUID_RE.test(String(get(name)))) throw new Error('Invalid immutable identity');
    });
    findRow_(sheet, map, id);
    const attempts = Number(get('attempts'));
    const version = Number(get('row_version'));
    if (!isOptout && (!Number.isInteger(attempts) || attempts < 0 || !Number.isInteger(version) || version < 1)) throw new Error('Invalid attempts/version');
    if (!STATUSES.includes(get('status'))) throw new Error('Invalid status');
    const invitation = String(get('invitation_state'));
    if (!isOptout && !['invited', 'uninvited', 'unknown'].includes(invitation)) throw new Error('Invalid invitation state');
    if (!isOptout && invitation === 'invited' && !get('invitation_evidence_ref')) throw new Error('Invitation needs evidence');
    const notes = String(get('notes') || '');
    if (!isOptout && notes.length > 2000) throw new Error('Notes too long');
    const occurred = new Date(get('occurred_at'));
    if (!isOptout && (isNaN(occurred.getTime()) || occurred.getTime() > Date.now() + 300000)) throw new Error('Invalid activity time');
    const pending = {
      eventId: Utilities.getUuid(), suppressionKey: Utilities.getUuid(), actor: actor,
      spreadsheetId: sheet.getParent().getId(), sheetId: sheet.getSheetId(), rowId: id,
      leadId: String(get('lead_id')), createdAt: new Date().toISOString(), attempts: 0,
      body: isOptout ? {expected_version: Number.isInteger(version) && version > 0 ? version : 1,
        status: 'do_not_contact_requested', attempts: 0, invitation_state: 'unknown',
        invitation_evidence_ref: null, notes: '', occurred_at: new Date().toISOString()} :
        {expected_version: version, status: get('status'), attempts: attempts,
          invitation_state: invitation, invitation_evidence_ref: String(get('invitation_evidence_ref') || '') || null,
          notes: notes, occurred_at: occurred.toISOString()}
    };
    // Preserve each event independently. A later edit never overwrites an earlier opt-out.
    PropertiesService.getScriptProperties().setProperty('pending:' + pending.eventId, JSON.stringify(pending));
    saveState_(sheet, id, isOptout ? 'Do not contact; opt-out pending' : 'Pending');
    submit_(pending);
  } catch (error) {
    saveState_(sheet, id, failure);
    // Deliberately do not log exception bodies, notes, endpoints or cell contents.
    throw new Error(failure);
  }
}

function signedRequest_(method, path, body, actor, key) {
  const properties = PropertiesService.getScriptProperties();
  if (properties.getProperty('ENABLED') !== 'true') throw new Error('Bridge release gate closed');
  const base = properties.getProperty('API_BASE_URL');
  const secret = properties.getProperty('BRIDGE_SECRET');
  const signingKey = properties.getProperty('SERVICE_SIGNING_KEY');
  if (!base || !/^https:\/\/[^/@]+$/.test(base) || !secret || !signingKey ||
      secret.length < 32 || signingKey.length < 32 || secret === signingKey) throw new Error('Invalid protected configuration');
  const timestamp = new Date().toISOString();
  const raw = method.toUpperCase() === 'GET' ? '' : JSON.stringify(body);
  const token = serviceToken_(method, path, raw, actor, signingKey, properties);
  const canonical = [method.toUpperCase(), path, timestamp, actor, key, raw].join('\n');
  const bytes = Utilities.computeHmacSha256Signature(canonical, secret, Utilities.Charset.UTF_8);
  const signature = bytes.map(value => ('0' + ((value + 256) % 256).toString(16)).slice(-2)).join('');
  const options = {method: method, contentType: 'application/json',
    followRedirects: false, muteHttpExceptions: true, headers: {
      Authorization: 'Bearer ' + token, 'Idempotency-Key': key, 'X-Request-ID': Utilities.getUuid(),
      'X-Bridge-Actor': actor, 'X-Bridge-Timestamp': timestamp, 'X-Bridge-Signature': signature
    }};
  if (method.toUpperCase() !== 'GET') options.payload = raw;
  const response = UrlFetchApp.fetch(base + path, options);
  const status = response.getResponseCode();
  if (status < 200 || status >= 300) throw new Error(status === 409 ? 'Revision conflict' : 'Control request failed');
  return JSON.parse(response.getContentText());
}

function serviceToken_(method, path, raw, actor, signingKey, properties) {
  const encode = value => Utilities.base64EncodeWebSafe(value, Utilities.Charset.UTF_8).replace(/=+$/, '');
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, raw, Utilities.Charset.UTF_8)
    .map(value => ('0' + ((value + 256) % 256).toString(16)).slice(-2)).join('');
  const now = Math.floor(Date.now() / 1000);
  const sheetId = properties.getProperty('WORKLIST_SHEET_ID');
  const spreadsheetId = properties.getProperty('SPREADSHEET_ID');
  if (!spreadsheetId || !/^(0|[1-9][0-9]*)$/.test(sheetId || '') || !Number.isSafeInteger(Number(sheetId))) {
    throw new Error('Bridge workbook identity missing');
  }
  const claims = {iss: 'maintain-media-sheets', aud: 'abr-engine-sheets', sub: 'private-worklist-bridge',
    iat: now, exp: now + 60, method: method.toUpperCase(), path: path, body_sha256: digest,
    editor: actor, spreadsheet_id: spreadsheetId, sheet_id: Number(sheetId)};
  const unsigned = encode(JSON.stringify({alg: 'HS256', typ: 'JWT'})) + '.' + encode(JSON.stringify(claims));
  const signature = Utilities.computeHmacSha256Signature(unsigned, signingKey, Utilities.Charset.UTF_8);
  return unsigned + '.' + Utilities.base64EncodeWebSafe(signature).replace(/=+$/, '');
}

function submit_(pending) {
  const sheet = SpreadsheetApp.openById(pending.spreadsheetId).getSheets().find(item => item.getSheetId() === pending.sheetId);
  if (!sheet) throw new Error('Worklist unavailable');
  const properties = PropertiesService.getScriptProperties();
  const key = 'pending:' + pending.eventId;
  const optout = pending.body.status === 'do_not_contact_requested';
  try {
    if (optout) {
      const receipt = signedRequest_('post', '/v1/suppressions', {lead_id: pending.leadId,
        reason: 'unsubscribe', source: 'sheets', requested_at: pending.createdAt}, pending.actor, pending.suppressionKey);
      if (!receipt.receipt_id || !receipt.committed_at) throw new Error('Missing durable suppression receipt');
      saveState_(sheet, pending.rowId, 'Do not contact; suppression saved: ' + receipt.receipt_id);
    }
    const receipt = signedRequest_('patch', '/v1/worklist-rows/' + pending.rowId, pending.body, pending.actor, pending.eventId);
    if (receipt.outcome_conflict) {
      saveState_(sheet, pending.rowId, 'Do not contact; suppression saved. Outcome conflict: refresh row.');
    } else {
      if (receipt.row_id !== pending.rowId || !Number.isInteger(receipt.version)) throw new Error('Invalid row receipt');
      const map = headers_(sheet);
      sheet.getRange(findRow_(sheet, map, pending.rowId), map.row_version).setValue(receipt.version);
      saveState_(sheet, pending.rowId, 'Saved: ' + pending.eventId);
    }
    properties.deleteProperty(key);
  } catch (error) {
    pending.attempts += 1;
    properties.setProperty(key, JSON.stringify(pending));
    saveState_(sheet, pending.rowId, optout ? 'Do not contact; confirm opt-out receipt in control API immediately. Operator escalation required.' : 'Not saved; revision conflict or service unavailable. Refresh before retry.');
    throw error;
  }
}

function repairPendingEdits() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const values = PropertiesService.getScriptProperties().getProperties();
    const pending = Object.keys(values).filter(key => key.startsWith('pending:')).map(key => JSON.parse(values[key]));
    // Stop requests first; five-minute repair is never their primary path.
    pending.sort((a, b) => Number(b.body.status === 'do_not_contact_requested') - Number(a.body.status === 'do_not_contact_requested') || a.createdAt.localeCompare(b.createdAt));
    pending.slice(0, 50).forEach(item => {
      if (item.attempts >= 5) return; // Visible operator repair; no endless stale update loop.
      try { submit_(item); } catch (error) { /* Visible state already set; never log cell data. */ }
    });
  } finally { lock.releaseLock(); }
}

function protectWorklist() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const map = headers_(sheet);
  const protection = sheet.protect().setDescription('Engine-owned immutable identity and computed fields');
  protection.setWarningOnly(false);
  protection.removeEditors(protection.getEditors());
  if (protection.canDomainEdit()) protection.setDomainEdit(false);
  protection.setUnprotectedRanges(EDITABLE.map(name => sheet.getRange(2, map[name], Math.max(1, sheet.getMaxRows() - 1), 1)));
  sheet.getRange(2, map.status, Math.max(1, sheet.getMaxRows() - 1), 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  // Sharing restrictions and editor/service scopes require an owner-reviewed G5 setup.
}

/** Standalone, owner-restricted Apps Script installation helper.
 * Add alongside sheets_bridge.gs in a standalone project owned only by the
 * operator. Do not bind this privileged project to the reviewer-editable Sheet.
 * Required nonsecret properties: INSTALLER_EMAIL, SPREADSHEET_ID,
 * WORKLIST_SHEET_ID, ALLOWED_EDITOR_EMAILS (JSON string array).
 * Existing secret properties remain server-managed and never logged/displayed.
 * Installation leaves ENABLED=false; real actor/sandbox certification is separate.
 */
function installPrivateWorklist() {
  const properties = PropertiesService.getScriptProperties();
  const owner = String(properties.getProperty('INSTALLER_EMAIL') || '').toLowerCase();
  if (!owner || Session.getEffectiveUser().getEmail().toLowerCase() !== owner) {
    throw new Error('Run installation as the configured workspace operator');
  }
  if (SpreadsheetApp.getActiveSpreadsheet()) {
    throw new Error('Use an owner-restricted standalone script, not a bound Sheet script');
  }
  properties.setProperty('ENABLED', 'false');
  const spreadsheetId = properties.getProperty('SPREADSHEET_ID');
  const rawSheetId = properties.getProperty('WORKLIST_SHEET_ID');
  if (typeof rawSheetId !== 'string' || !/^(0|[1-9][0-9]*)$/.test(rawSheetId)) {
    throw new Error('Worklist mapping incomplete');
  }
  const sheetId = Number(rawSheetId);
  if (!spreadsheetId || !Number.isSafeInteger(sheetId)) throw new Error('Worklist mapping incomplete');
  const allowed = JSON.parse(properties.getProperty('ALLOWED_EDITOR_EMAILS') || '[]');
  if (!Array.isArray(allowed) || allowed.some(value => typeof value !== 'string' || !value.includes('@'))) {
    throw new Error('Named editor mapping invalid');
  }
  const file = DriveApp.getFileById(spreadsheetId);
  const sheetOwner = file.getOwner();
  if (!sheetOwner || sheetOwner.getEmail().toLowerCase() !== owner) {
    throw new Error('The configured operator must own the private worklist');
  }
  if (file.getSharingAccess() !== DriveApp.Access.PRIVATE) {
    throw new Error('Worklist must use named-person sharing only');
  }
  const permitted = new Set(allowed.map(value => value.toLowerCase()).concat(owner));
  if (file.getEditors().concat(file.getViewers()).some(user => !permitted.has(user.getEmail().toLowerCase()))) {
    throw new Error('Worklist contains an unmapped editor or viewer');
  }
  file.setShareableByEditors(false);
  const sheet = SpreadsheetApp.openById(spreadsheetId).getSheets().find(item => item.getSheetId() === sheetId);
  if (!sheet) throw new Error('Configured worklist tab unavailable');
  const map = headers_(sheet);
  const existing = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET).filter(item =>
    item.getDescription() === 'Maintain Media engine-owned worklist');
  if (existing.length > 1) throw new Error('Duplicate worklist protection needs operator review');
  const protection = existing[0] || sheet.protect().setDescription('Maintain Media engine-owned worklist');
  protection.setWarningOnly(false);
  protection.addEditor(owner);
  protection.removeEditors(protection.getEditors().filter(user => user.getEmail().toLowerCase() !== owner)
    .map(user => user.getEmail()));
  if (protection.canDomainEdit()) protection.setDomainEdit(false);
  const rows = Math.max(1, sheet.getMaxRows() - 1);
  protection.setUnprotectedRanges(EDITABLE.map(name => sheet.getRange(2, map[name], rows, 1)));
  sheet.getRange(2, map.status, rows, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  const triggers = ScriptApp.getProjectTriggers();
  const edits = triggers.filter(item => item.getHandlerFunction() === 'installedWorklistEdit');
  if (edits.length > 1 || edits.some(item => item.getTriggerSourceId() !== spreadsheetId ||
      item.getEventType() !== ScriptApp.EventType.ON_EDIT ||
      item.getTriggerSource() !== ScriptApp.TriggerSource.SPREADSHEETS)) {
    throw new Error('Existing edit trigger belongs to another worklist; review it manually');
  }
  const repair = triggers.filter(item => item.getHandlerFunction() === 'repairPendingEdits');
  if (repair.length > 1 || repair.some(item => item.getEventType() !== ScriptApp.EventType.CLOCK ||
      item.getTriggerSource() !== ScriptApp.TriggerSource.CLOCK)) {
    throw new Error('Existing repair trigger needs operator review');
  }
  // Gate stays closed throughout installation; this never certifies a live bridge.
  properties.setProperty('ENABLED', 'false');
  if (!edits.length) ScriptApp.newTrigger('installedWorklistEdit').forSpreadsheet(spreadsheetId).onEdit().create();
  if (!repair.length) ScriptApp.newTrigger('repairPendingEdits').timeBased().everyMinutes(5).create();
  return {installed: true, enabled: false, worklistProtected: true};
}

function installedWorklistEdit(event) {
  if (!event || !event.range) return;
  const properties = PropertiesService.getScriptProperties();
  const sheet = event.range.getSheet();
  if (sheet.getParent().getId() !== properties.getProperty('SPREADSHEET_ID') ||
      String(sheet.getSheetId()) !== properties.getProperty('WORKLIST_SHEET_ID')) return;
  onWorklistEdit(event);
}

/** Owner-run, empty private worklist setup. No API credentials or business rows are installed. */
function prepareMaintainMediaWorklist() {
  const owner = 'jeph@quotemax.com.au';
  const spreadsheetId = '1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58';
  const sheetName = 'ABN Worklist';
  if (Session.getEffectiveUser().getEmail().toLowerCase() !== owner || SpreadsheetApp.getActiveSpreadsheet()) {
    throw new Error('Run this standalone project as the private Sheet owner');
  }
  const properties = PropertiesService.getScriptProperties();
  if ((properties.getProperty('SPREADSHEET_ID') && properties.getProperty('SPREADSHEET_ID') !== spreadsheetId) ||
      (properties.getProperty('INSTALLER_EMAIL') && properties.getProperty('INSTALLER_EMAIL') !== owner)) {
    throw new Error('This project is configured for another operator or workbook');
  }
  const file = DriveApp.getFileById(spreadsheetId);
  if (!file.getOwner() || file.getOwner().getEmail().toLowerCase() !== owner ||
      file.getSharingAccess() !== DriveApp.Access.PRIVATE ||
      file.getEditors().concat(file.getViewers()).some(user => user.getEmail().toLowerCase() !== owner)) {
    throw new Error('Keep the workbook Restricted and owner-only before initial installation');
  }
  properties.setProperty('ENABLED', 'false');
  const book = SpreadsheetApp.openById(spreadsheetId);
  const columns = ['row_id', 'worklist_id', 'lead_id', 'group_id', 'row_version', 'generated_at',
    'signal', 'tier', 'score', 'business_name', 'safe_contact_view', 'gate_label', 'gate_checked_at',
    'next_action', 'opener', 'status', 'attempts', 'invitation_state', 'occurred_at', 'save_state',
    'invitation_evidence_ref', 'notes', 'source', 'source_age', 'source_published_at',
    'signal_description', 'reasons', 'gate_expires_at', 'policy_version'];
  let sheet = book.getSheetByName(sheetName);
  if (sheet && sheet.getLastRow() > 0) {
    const existing = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    if (JSON.stringify(existing) !== JSON.stringify(columns)) throw new Error('Existing worklist schema differs; nothing overwritten');
  }
  if (!sheet) sheet = book.insertSheet(sheetName);
  if (sheet.getMaxColumns() < columns.length) sheet.insertColumnsAfter(sheet.getMaxColumns(), columns.length-sheet.getMaxColumns());
  if (sheet.getLastRow() === 0) sheet.getRange(1, 1, 1, columns.length).setValues([columns]);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, columns.length).setFontWeight('bold').setBackground('#213D33').setFontColor('#FFFFFF');
  sheet.setColumnWidths(1, columns.length, 160);
  sheet.setColumnWidth(10, 250);
  sheet.setColumnWidth(11, 250);
  sheet.setColumnWidth(22, 300);
  properties.setProperty('INSTALLER_EMAIL', owner);
  properties.setProperty('SPREADSHEET_ID', spreadsheetId);
  properties.setProperty('WORKLIST_SHEET_ID', String(sheet.getSheetId()));
  properties.setProperty('ALLOWED_EDITOR_EMAILS', JSON.stringify([owner]));
  const result = installPrivateWorklist();
  return {installed: result.installed, enabled: false, spreadsheetId: spreadsheetId,
    sheetId: sheet.getSheetId(), sheetName: sheetName, headers: columns.length,
    businessRowsCreated: 0, endpointConfigured: false, messagesSent: 0};
}

/** Private live worklist pull. The engine, not this script, approves disclosure.
 * Timed refreshes never overwrite staff outcome cells on existing rows. A newer
 * server outcome produces a visible revision conflict instead of losing edits.
 * Five-minute full pulls add current rows. One-minute refreshes mask withdrawn
 * contacts; Apps Script timer latency must still pass a measured G5 pilot.
 */
const WORKLIST_COLUMNS = ['row_id', 'worklist_id', 'lead_id', 'group_id', 'row_version', 'generated_at',
  'signal', 'tier', 'score', 'business_name', 'safe_contact_view', 'gate_label', 'gate_checked_at',
  'next_action', 'opener', 'status', 'attempts', 'invitation_state', 'occurred_at', 'save_state',
  'invitation_evidence_ref', 'notes', 'source', 'source_age', 'source_published_at',
  'signal_description', 'reasons', 'gate_expires_at', 'policy_version'];
const SYNC_IDENTITY = ['row_id', 'worklist_id', 'lead_id', 'group_id'];

function syncSheet_() {
  const properties = PropertiesService.getScriptProperties();
  const owner = properties.getProperty('INSTALLER_EMAIL');
  const bookId = properties.getProperty('SPREADSHEET_ID');
  const tabId = properties.getProperty('WORKLIST_SHEET_ID');
  if (!owner || Session.getEffectiveUser().getEmail().toLowerCase() !== owner ||
      SpreadsheetApp.getActiveSpreadsheet() || !bookId || !/^(0|[1-9][0-9]*)$/.test(tabId || '')) {
    throw new Error('Owner-only standalone workbook configuration required');
  }
  const sheet = SpreadsheetApp.openById(bookId).getSheets().find(item => String(item.getSheetId()) === tabId);
  if (!sheet) throw new Error('Configured private worklist unavailable');
  const map = headers_(sheet);
  if (JSON.stringify(Object.keys(map)) !== JSON.stringify(WORKLIST_COLUMNS) ||
      sheet.getLastRow() > 2001) throw new Error('Worklist schema or history limit needs owner review');
  return sheet;
}

function verifyPrivateReaders_(payload) {
  const properties = PropertiesService.getScriptProperties();
  const owner = properties.getProperty('INSTALLER_EMAIL');
  const readers = JSON.parse(properties.getProperty('ALLOWED_EDITOR_EMAILS') || '[]');
  if (!Array.isArray(readers) || readers.some(email => typeof email !== 'string' || email !== email.toLowerCase()) ||
      !readers.includes(owner) || new Set(readers).size !== readers.length) throw new Error('Invalid named reader mapping');
  const file = DriveApp.getFileById(properties.getProperty('SPREADSHEET_ID'));
  if (!file.getOwner() || file.getOwner().getEmail().toLowerCase() !== owner ||
      file.getSharingAccess() !== DriveApp.Access.PRIVATE ||
      file.getEditors().concat(file.getViewers()).some(user => !readers.includes(user.getEmail().toLowerCase()))) {
    throw new Error('Private workbook readers changed; owner review required');
  }
  if (payload && (payload.owner_email !== owner || !Array.isArray(payload.reader_emails) ||
      JSON.stringify(payload.reader_emails.slice().sort()) !== JSON.stringify(readers.slice().sort()))) {
    throw new Error('Service and Google reader mappings differ');
  }
}

function validatePull_(payload) {
  const properties = PropertiesService.getScriptProperties();
  const now = Date.now(), generated = Date.parse(payload.generated_at), expires = Date.parse(payload.expires_at);
  if (payload.schema_version !== 1 || payload.spreadsheet_id !== properties.getProperty('SPREADSHEET_ID') ||
      payload.sheet_id !== Number(properties.getProperty('WORKLIST_SHEET_ID')) || !UUID_RE.test(payload.snapshot_id) ||
      !Number.isFinite(generated) || !Number.isFinite(expires) || generated > now + 5000 ||
      generated < now - 90000 || expires <= now || expires > generated + 90000 ||
      typeof payload.disclosure_allowed !== 'boolean' || !Array.isArray(payload.reason_codes) ||
      !Array.isArray(payload.columns) || JSON.stringify(payload.columns.slice().sort()) !== JSON.stringify(WORKLIST_COLUMNS.slice().sort()) ||
      !Array.isArray(payload.rows) || payload.rows.length > 60 ||
      (!payload.disclosure_allowed && payload.rows.length)) throw new Error('Invalid or stale private worklist response');
  verifyPrivateReaders_(payload);
  const ids = new Set(), groups = new Set();
  payload.rows.forEach(row => {
    if (!row || JSON.stringify(Object.keys(row).sort()) !== JSON.stringify(WORKLIST_COLUMNS.slice().sort()) ||
        SYNC_IDENTITY.some(name => typeof row[name] !== 'string' || !UUID_RE.test(row[name])) ||
        row.worklist_id !== payload.worklist_id || ids.has(row.row_id) || groups.has(row.group_id) ||
        !Number.isInteger(row.row_version) || row.row_version < 1 ||
        !Number.isInteger(row.attempts) || row.attempts < 0 || row.attempts > 100000 ||
        !STATUSES.includes(row.status) || !['invited', 'uninvited', 'unknown'].includes(row.invitation_state) ||
        Object.values(row).some(value => typeof value !== 'string' && typeof value !== 'number') ||
        String(row.notes).length > 2000) throw new Error('Invalid immutable worklist row');
    ids.add(row.row_id); groups.add(row.group_id);
  });
  return payload;
}

function literalCell_(value) {
  // Apps Script setValues interprets formula-leading strings. Keep publisher and
  // staff strings literal, including a formula preceded by whitespace.
  return typeof value === 'string' && /^[\s]*[=+@-]/.test(value) ? "'" + value : value;
}

function normalizeOutcome_(value, name) {
  if (name === 'attempts') return Number(value);
  if (name === 'occurred_at' && value) {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toISOString() : String(value);
  }
  return String(value || '');
}

function maskRow_(sheet, map, index, message) {
  sheet.getRange(index, map.business_name, 1, 6).setValues([['', 'Masked — contact blocked', 'Do not contact', '', '', '']]);
  sheet.getRange(index, map.save_state).setValue(message);
}

function redactWorklist_(sheet, message) {
  const map = headers_(sheet);
  for (let index = 2; index <= sheet.getLastRow(); index++) {
    if (sheet.getRange(index, map.row_id).getValue()) maskRow_(sheet, map, index, message);
  }
  SpreadsheetApp.flush();
  for (let index = 2; index <= sheet.getLastRow(); index++) {
    if (sheet.getRange(index, map.row_id).getValue() &&
        (sheet.getRange(index, map.safe_contact_view).getValue() !== 'Masked — contact blocked' ||
         sheet.getRange(index, map.business_name).getValue() !== '')) throw new Error('Contact redaction read-back failed');
  }
}

function applyPull_(sheet, payload, addRows) {
  const map = headers_(sheet), properties = PropertiesService.getScriptProperties();
  const pending = Object.entries(properties.getProperties()).filter(([key]) => key.startsWith('pending:'))
    .map(([, value]) => JSON.parse(value));
  const existing = new Map();
  for (let index = 2; index <= sheet.getLastRow(); index++) {
    const values = sheet.getRange(index, 1, 1, WORKLIST_COLUMNS.length).getValues()[0];
    const id = String(values[map.row_id - 1] || '');
    if (!id && values.some(value => value !== '')) throw new Error('Unidentified row contains staff data; nothing overwritten');
    if (!id) continue;
    if (!UUID_RE.test(id) || existing.has(id)) throw new Error('Duplicate or invalid local immutable row ID');
    existing.set(id, {index: index, values: values});
  }
  // Validate every match before the first write. Sorting never changes identity.
  payload.rows.forEach(row => {
    const local = existing.get(row.row_id);
    if (local && SYNC_IDENTITY.some(name => String(local.values[map[name]-1]) !== row[name])) {
      throw new Error('Worklist identity changed; owner review required');
    }
  });
  if (!payload.disclosure_allowed) {
    redactWorklist_(sheet, 'Live disclosure paused; local outcomes retained. Check dashboard setup.');
    return {currentRows: 0, addedRows: 0, redacted: true};
  }
  let added = 0;
  const verify = [];
  const received = new Set();
  payload.rows.forEach(row => {
    received.add(row.row_id);
    const local = existing.get(row.row_id);
    if (!local) {
      if (!addRows) return;
      const index = sheet.getLastRow() + 1;
      if (index > 2001) throw new Error('Worklist history capacity needs owner archive review');
      if (index > sheet.getMaxRows()) {
        sheet.insertRowsAfter(sheet.getMaxRows(), Math.min(100, 2001-sheet.getMaxRows()));
        const protection = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET).find(item =>
          item.getDescription() === 'Maintain Media engine-owned worklist');
        if (!protection) throw new Error('Engine-owned worklist protection is missing');
        protection.setUnprotectedRanges(EDITABLE.map(name => sheet.getRange(2, map[name], sheet.getMaxRows()-1, 1)));
      }
      sheet.getRange(index, 1, 1, WORKLIST_COLUMNS.length).setValues([
        WORKLIST_COLUMNS.map(name => literalCell_(row[name]))]);
      verify.push({rowId: row.row_id, contact: row.safe_contact_view, label: row.gate_label});
      added++;
      return;
    }
    const queued = pending.filter(item => item.rowId === row.row_id);
    // Read outcomes immediately before writing computed fields. Existing outcome
    // cells are never overwritten by timers, including unsaved invalid edits.
    const values = sheet.getRange(findRow_(sheet, map, row.row_id), 1, 1, WORKLIST_COLUMNS.length).getValues()[0];
    const sameOutcome = EDITABLE.every(name => normalizeOutcome_(values[map[name]-1], name) === normalizeOutcome_(row[name], name));
    const index = findRow_(sheet, map, row.row_id);
    // Only these two contiguous blocks are engine-owned computed fields. No
    // outcome range is rewritten, and no row is moved or deleted by a timer.
    for (const [first, last] of [[5, 15], [22, 29]]) {
      sheet.getRange(index, first+1, 1, last-first).setValues([
        WORKLIST_COLUMNS.slice(first, last).map(name => literalCell_(row[name]))]);
    }
    if (sameOutcome && !queued.length) {
      sheet.getRange(index, map.row_version).setValue(row.row_version);
      sheet.getRange(index, map.save_state).setValue(row.save_state);
    } else {
      sheet.getRange(index, map.save_state).setValue(queued.length ? 'Pending local outcome; edits and version retained.' :
        'Local outcome differs from server; edits and version retained. Compare in dashboard before retry.');
    }
    if (values[map.status-1] === 'do_not_contact_requested' || queued.some(item => item.body.status === 'do_not_contact_requested')) {
      maskRow_(sheet, map, index, 'Do not contact; local stop request retained. Confirm durable receipt in dashboard.');
      verify.push({rowId: row.row_id, contact: 'Masked — contact blocked', label: 'Do not contact'});
    } else {
      verify.push({rowId: row.row_id, contact: row.safe_contact_view, label: row.gate_label});
    }
  });
  existing.forEach((local, id) => {
    if (!received.has(id)) {
      maskRow_(sheet, map, findRow_(sheet, map, id),
        'Previous worklist; contact removed. Local outcomes retained for review.');
      verify.push({rowId: id, contact: 'Masked — contact blocked', label: 'Do not contact'});
    }
  });
  SpreadsheetApp.flush();
  verify.forEach(expected => {
    const index = findRow_(sheet, map, expected.rowId);
    const actual = sheet.getRange(index, map.safe_contact_view).getValue();
    if ((actual !== expected.contact && actual !== literalCell_(expected.contact)) ||
        sheet.getRange(index, map.gate_label).getValue() !== expected.label) {
      throw new Error('Contact projection read-back failed');
    }
  });
  return {currentRows: payload.rows.length, addedRows: added, redacted: false};
}

function pullIntoWorklist_(addRows) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return {busy: true};
  let sheet;
  try {
    sheet = syncSheet_();
    const properties = PropertiesService.getScriptProperties();
    if (properties.getProperty('ENABLED') !== 'true') {
      redactWorklist_(sheet, 'Live bridge disabled; local outcomes retained.');
      return {enabled: false};
    }
    verifyPrivateReaders_();
    const payload = validatePull_(signedRequest_('get', '/v1/sheets/worklist', null,
      properties.getProperty('INSTALLER_EMAIL'), Utilities.getUuid()));
    const result = applyPull_(sheet, payload, addRows);
    // Receipt contains no business values or outcome text. It records a local
    // application, not a remote certification or a proved latency measurement.
    properties.setProperty('LAST_PULL_RECEIPT', JSON.stringify({snapshotId: payload.snapshot_id,
      appliedAt: new Date().toISOString(), expiresAt: payload.expires_at,
      currentRows: result.currentRows, addedRows: result.addedRows, redacted: result.redacted}));
    return {enabled: true, disclosureAllowed: payload.disclosure_allowed, ...result};
  } catch (error) {
    if (sheet) redactWorklist_(sheet, 'Refresh failed; contact hidden. Local outcomes retained. Check dashboard.');
    throw new Error('Private worklist refresh failed; no outcome was overwritten');
  } finally { lock.releaseLock(); }
}

function syncLiveWorklist() { return pullIntoWorklist_(true); }
function refreshWorklistRestrictions() { return pullIntoWorklist_(false); }

function enableVerifiedWorklistSync() {
  syncSheet_(); verifyPrivateReaders_();
  const properties = PropertiesService.getScriptProperties();
  try {
    properties.setProperty('ENABLED', 'true');
    const result = syncLiveWorklist();
    if (!result || result.busy || !result.disclosureAllowed) throw new Error('Live disclosure approval is not current');
    for (const [handler, minutes] of [['syncLiveWorklist', 5], ['refreshWorklistRestrictions', 1]]) {
      const triggers = ScriptApp.getProjectTriggers().filter(item => item.getHandlerFunction() === handler);
      if (triggers.length > 1 || triggers.some(item => item.getEventType() !== ScriptApp.EventType.CLOCK ||
          item.getTriggerSource() !== ScriptApp.TriggerSource.CLOCK)) throw new Error('Refresh trigger needs owner review');
      if (!triggers.length) ScriptApp.newTrigger(handler).timeBased().everyMinutes(minutes).create();
    }
    return {enabled: true, fullRefreshMinutes: 5, restrictionRefreshMinutes: 1, messagesSent: 0};
  } catch (error) {
    properties.setProperty('ENABLED', 'false');
    redactWorklist_(syncSheet_(), 'Live activation failed; contact hidden. Check dashboard setup.');
    throw new Error('Live sync remains disabled; finish verified server and vendor setup first');
  }
}
