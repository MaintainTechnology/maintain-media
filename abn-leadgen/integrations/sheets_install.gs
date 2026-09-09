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
