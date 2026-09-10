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
