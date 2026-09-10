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
