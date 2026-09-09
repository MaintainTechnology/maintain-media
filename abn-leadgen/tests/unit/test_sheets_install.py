"""Exercise installer authority/idempotency without Google accounts or API writes."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_standalone_sheet_installer_authority_and_idempotency():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node runtime required for Apps Script fixture")
    script = Path(__file__).resolve().parents[2] / "integrations/sheets_install.gs"
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
function make(options = {}) {
  const owner = 'owner@example.test';
  const props = {INSTALLER_EMAIL: owner, SPREADSHEET_ID: 'book1', WORKLIST_SHEET_ID: '7',
    ALLOWED_EDITOR_EMAILS: '["reviewer@example.test"]', ENABLED: 'true'};
  if (options.zeroTab) props.WORKLIST_SHEET_ID = '0';
  if (options.missingId) delete props.WORKLIST_SHEET_ID;
  if (options.emptyId) props.WORKLIST_SHEET_ID = '';
  const saved = [], ranges = [], triggers = [], protections = [];
  const user = email => ({getEmail: () => email});
  const editorEmails = [owner, options.unmapped ? 'stranger@example.test' : 'reviewer@example.test'];
  const protection = {getDescription: () => 'Maintain Media engine-owned worklist',
    setDescription: () => protection, setWarningOnly: value => {assert.equal(value, false);return protection;},
    addEditor: value => {assert.equal(value, owner);return protection;},
    getEditors: () => editorEmails.map(user),
    removeEditors: values => {assert.deepEqual(Array.from(values), ['reviewer@example.test']);return protection;},
    canDomainEdit: () => true, setDomainEdit: value => {assert.equal(value,false);return protection;},
    setUnprotectedRanges: values => {ranges.push(...values);return protection;}};
  const sheet = {getSheetId: () => options.zeroTab ? 0 : options.wrongTab ? 8 : 7, getParent: () => ({getId: () => 'book1'}),
    getProtections: () => protections,
    protect: () => {protections.push(protection);return protection;}, getMaxRows: () => 100,
    getRange: (...args) => ({args, setDataValidation: value => assert.equal(value, 'validation')})};
  const makeTrigger = name => {let id = null, type = null;
    const builder = {forSpreadsheet: value => {id=value;return builder;},
      onEdit: () => {type='edit';return builder;}, timeBased: () => {type='timer';return builder;},
      everyMinutes: value => {assert.equal(value,5);return builder;},
      create: () => {triggers.push({getHandlerFunction:()=>name,getTriggerSourceId:()=>id,type,
        getEventType:()=>type==='edit'?'ON_EDIT':'CLOCK',getTriggerSource:()=>type==='edit'?'SPREADSHEETS':'CLOCK'});}};
    return builder;};
  const context = {console, PropertiesService: {getScriptProperties: () => ({getProperty: key => props[key],
    setProperty: (key,value) => {props[key]=value;saved.push([key,value]);}})},
    Session: {getEffectiveUser: () => user(options.wrongOwner ? 'someone@example.test' : owner)},
    SpreadsheetApp: {getActiveSpreadsheet: () => options.bound ? sheet : null,
      openById: id => {assert.equal(id,'book1');return {getSheets:()=>[sheet]};},
      ProtectionType: {SHEET:'sheet'}, newDataValidation: () => {
        const b={requireValueInList:()=>b,setAllowInvalid:()=>b,build:()=> 'validation'};return b;}},
    DriveApp: {Access:{PRIVATE:'private'},getFileById:()=>({
      getOwner:()=>user(options.otherSheetOwner ? 'different-owner@example.test' : owner),
      getSharingAccess:()=> options.public ? 'public' : 'private',getEditors:()=>editorEmails.map(user),
      getViewers:()=>[],setShareableByEditors:value=>assert.equal(value,false)})},
    ScriptApp:{getProjectTriggers:()=>triggers,newTrigger:makeTrigger,
      EventType:{ON_EDIT:'ON_EDIT',CLOCK:'CLOCK'},TriggerSource:{SPREADSHEETS:'SPREADSHEETS',CLOCK:'CLOCK'}},
    headers_:()=>({status:6,notes:7}),EDITABLE:['status','notes'],STATUSES:['not_started'],
    onWorklistEdit:event=>{saved.push(['edited',event.range.getSheet().getSheetId()]);}};
  vm.createContext(context);vm.runInContext(source,context);
  return {context,props,triggers,protections,saved,ranges,sheet};
}
const good=make();
assert.equal(good.context.installPrivateWorklist().enabled,false);
assert.equal(good.props.ENABLED,'false');
assert.equal(good.triggers.length,2);
assert.equal(good.protections.length,1);
assert.equal(good.ranges.length,2);
good.context.installPrivateWorklist();
assert.equal(good.triggers.length,2);
assert.equal(good.protections.length,1);
for(const options of [{wrongOwner:true},{bound:true},{public:true},{unmapped:true},{wrongTab:true},
  {otherSheetOwner:true},{missingId:true,zeroTab:true},{emptyId:true,zeroTab:true}]) {
  const bad=make(options);assert.throws(()=>bad.context.installPrivateWorklist());assert.equal(bad.triggers.length,0);
  if(!options.wrongOwner && !options.bound) assert.equal(bad.props.ENABLED,'false');
}
const zero=make({zeroTab:true});
assert.equal(zero.context.installPrivateWorklist().installed,true);
zero.context.installedWorklistEdit({range:{getSheet:()=>zero.sheet}});
assert.ok(zero.saved.some(row=>row[0]==='edited'));
good.context.installedWorklistEdit({range:{getSheet:()=>good.sheet}});
assert.ok(good.saved.some(row=>row[0]==='edited'));
const before=good.saved.length;
good.context.installedWorklistEdit({range:{getSheet:()=>({getParent:()=>({getId:()=> 'other-book'}),getSheetId:()=>7})}});
assert.equal(good.saved.length,before);
good.triggers.push({getHandlerFunction:()=> 'installedWorklistEdit',getTriggerSourceId:()=> 'other-book'});
assert.throws(()=>good.context.installPrivateWorklist());
for(const wrong of ['edit_event','edit_source','repair_event','repair_source']) {
  const item=make();item.context.installPrivateWorklist();
  const index=wrong.startsWith('edit')?0:1;
  if(wrong.endsWith('event')) item.triggers[index].getEventType=()=> 'ON_CHANGE';
  else item.triggers[index].getTriggerSource=()=> 'FORMS';
  assert.throws(()=>item.context.installPrivateWorklist());
  assert.equal(item.triggers.length,2);
  assert.equal(item.props.ENABLED,'false');
}
console.log('standalone installer contract passed');
"""
    result = subprocess.run([node, "-e", harness, str(script)], capture_output=True,
                            text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert "standalone installer contract passed" in result.stdout
