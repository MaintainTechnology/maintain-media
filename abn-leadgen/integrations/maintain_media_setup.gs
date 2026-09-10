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
