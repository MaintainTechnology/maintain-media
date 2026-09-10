"""Execute owner-only non-secret worklist preparation without Google network access."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_owner_setup_preserves_existing_data_and_stays_disabled():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for Apps Script setup verification")
    root = Path(__file__).resolve().parents[2]
    harness = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8');
function make(options={}) {
 const owner='jeph@quotemax.com.au',book='1-PEySaH7AAod3hoFqZZf7zMYMWyQ3qIAWQzxnrq6K58';
 const props=options.foreignProject?{SPREADSHEET_ID:'other'}:{ENABLED:'true'};
 let created=0,writes=0,installed=0,cols=26,header=options.existingDifferent?['user-owned content']:[];
 const user=email=>({getEmail:()=>email});
 const sheet={getSheetId:()=>42,getLastRow:()=>header.length?1:0,getLastColumn:()=>header.length,
   getMaxColumns:()=>cols,insertColumnsAfter:(after,count)=>{assert.equal(after,cols);cols+=count;},
   setFrozenRows:()=>{},setColumnWidths:()=>{},setColumnWidth:()=>{},
   getRange:()=>{const r={getValues:()=>[header],setValues:values=>{header=Array.from(values[0]);writes++;return r;},
   setFontWeight:()=>r,setBackground:()=>r,setFontColor:()=>r};return r;}};
 let existing=options.existingDifferent?sheet:null;
 const context={Session:{getEffectiveUser:()=>user(options.wrongOwner?'other@example.test':owner)},
  SpreadsheetApp:{getActiveSpreadsheet:()=>options.bound?{}:null,openById:id=>{
   assert.equal(id,book);return {getSheetByName:name=>{assert.equal(name,'ABN Worklist');return existing;},
   insertSheet:name=>{assert.equal(name,'ABN Worklist');created++;existing=sheet;return sheet;}};}},
  PropertiesService:{getScriptProperties:()=>({getProperty:key=>props[key],setProperty:(key,value)=>props[key]=value})},
  DriveApp:{Access:{PRIVATE:'private'},getFileById:()=>({getOwner:()=>user(owner),
   getSharingAccess:()=>options.public?'anyone':'private',getEditors:()=>options.unmapped?[user('other@example.test')]:[],getViewers:()=>[]})}};
 vm.createContext(context);vm.runInContext(source,context);
 context.installPrivateWorklist=()=>{installed++;assert.equal(props.ENABLED,'false');assert.equal(props.WORKLIST_SHEET_ID,'42');return {installed:true};};
 return {context,props,read:()=>({created,writes,installed,cols,header})};
}
const good=make();const receipt=good.context.prepareMaintainMediaWorklist();
assert.equal(receipt.enabled,false);assert.equal(receipt.businessRowsCreated,0);assert.equal(receipt.endpointConfigured,false);
good.context.prepareMaintainMediaWorklist();
assert.equal(good.read().created,1);assert.equal(good.read().writes,1);assert.equal(good.read().cols,29);
for(const option of [{wrongOwner:true},{bound:true},{public:true},{unmapped:true},{foreignProject:true},{existingDifferent:true}]) {
 const bad=make(option);assert.throws(()=>bad.context.prepareMaintainMediaWorklist());
 assert.equal(bad.read().created,0);assert.equal(bad.read().writes,0);assert.equal(bad.read().installed,0);
}
process.stdout.write(JSON.stringify(good.read().header));
"""
    completed = subprocess.run([node, "-e", harness, str(root/"integrations/maintain_media_standalone.gs")],
        text=True, capture_output=True, timeout=15, check=True)
    assert json.loads(completed.stdout) == json.loads((root/"templates/worklist_schema.json").read_text())["required"]


def test_standalone_bundle_exactly_matches_reviewed_sources():
    directory = Path(__file__).resolve().parents[2] / "integrations"
    bundle = (directory/"maintain_media_standalone.gs").read_text(encoding="utf-8")
    expected = "\n".join((directory/name).read_text(encoding="utf-8") for name in
                         ("sheets_bridge.gs", "sheets_install.gs", "maintain_media_setup.gs", "sheets_sync.gs"))
    assert bundle.endswith(expected)
