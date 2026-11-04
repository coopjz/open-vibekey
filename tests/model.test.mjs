import test from "node:test";
import assert from "node:assert/strict";
import {newAction,setBinding,addProfile,shortcutFromEvent,resolveBinding,saveLibraryItem,libraryUsage,macroFromCode,macroToCode,validShortcut} from "../web/model.mjs";

function config() {
  return {profiles:{default:{name:"Default",layers:Array.from({length:4},()=>({bindings:{top:{single:{type:"none"}}}}))}}};
}
test("all editable actions have independent serializable defaults",()=>{
  for(const type of ["none","shortcut","text","application","shell","volume","macro","layer","profile","momentary_layer","voice"]) {
    assert.equal(newAction(type).type,type);
    assert.deepEqual(JSON.parse(JSON.stringify(newAction(type))),newAction(type));
  }
});
test("edge binding clears incompatible gestures",()=>{
  const value=config();
  setBinding(value,"default",0,"top","double",{type:"text",value:"d"});
  setBinding(value,"default",0,"top","single",{type:"voice",operation:"ptt"});
  assert.deepEqual(Object.keys(value.profiles.default.layers[0].bindings.top),["single"]);
});
test("new profile does not share nested bindings",()=>{
  const value=config();
  addProfile(value,"work","工作","default");
  setBinding(value,"work",0,"top","single",{type:"text",value:"test"});
  assert.equal(value.profiles.default.layers[0].bindings.top.single.type,"none");
  assert.throws(()=>addProfile(value,"work","duplicate","default"));
});
test("unset removes a gesture",()=>{
  const value=config();
  setBinding(value,"default",0,"top","single",null);
  assert.deepEqual(value.profiles.default.layers[0].bindings.top,{});
});
test("shortcut recording covers modifiers, punctuation, numpad and unsupported keys",()=>{
  assert.equal(shortcutFromEvent({code:"KeyA",ctrlKey:true,shiftKey:true}),"CTRL+SHIFT+A");
  assert.equal(shortcutFromEvent({code:"BracketLeft",altKey:true}),"ALT+LEFTBRACE");
  assert.equal(shortcutFromEvent({code:"NumpadEnter"}),"KPENTER");
  assert.equal(shortcutFromEvent({code:"ControlLeft",ctrlKey:true}),null);
  assert.equal(shortcutFromEvent({code:"Unidentified"}),null);
  assert.equal(validShortcut("CTRL+CTRL+A"),false);
});
test("holding output clears incompatible gestures",()=>{
  const value=config();
  setBinding(value,"default",0,"top","double",{type:"shortcut",keys:"B"});
  setBinding(value,"default",0,"top","single",{type:"shortcut",keys:"A",mode:"hold"});
  assert.deepEqual(Object.keys(value.profiles.default.layers[0].bindings.top),["single"]);
});
test("inheritance resolves through multiple levels and respects explicit none",()=>{
  const value=config();
  setBinding(value,"default",0,"top","single",{type:"shortcut",keys:"A"});
  setBinding(value,"default",1,"top","single",{type:"inherit"});
  setBinding(value,"default",2,"top","single",{type:"inherit"});
  assert.equal(resolveBinding(value,"default",2,"top","single").keys,"A");
  setBinding(value,"default",1,"top","single",{type:"none"});
  assert.equal(resolveBinding(value,"default",2,"top","single").type,"none");
});
test("editing a reusable library action updates all assigned copies",()=>{
  const value=config(),item={id:"app1",name:"Test",action:{type:"application",argv:["old"]}};
  saveLibraryItem(value,"applications",item);
  setBinding(value,"default",0,"top","single",{...item.action,label:item.name,library_id:item.id});
  value.library.macros.push({id:"macro1",name:"macro",action:{type:"macro",steps:[{...item.action,library_id:item.id}]}});
  assert.equal(libraryUsage(value,"app1"),2);
  saveLibraryItem(value,"applications",{...item,name:"Updated",action:{type:"application",argv:["new"]}});
  assert.equal(value.profiles.default.layers[0].bindings.top.single.argv[0],"new");
  assert.equal(value.library.macros[0].action.steps[0].argv[0],"new");
});
test("macro Code round trips without executing arbitrary code",()=>{
  const steps=[{type:"application",argv:["/usr/bin/true"]},{delay_ms:500},{type:"shortcut",keys:"CTRL+ALT+I"}];
  assert.deepEqual(macroFromCode(macroToCode(steps)),steps);
  assert.deepEqual(macroFromCode("tap_code16(LCTL(KC_BSPC));"),[{type:"shortcut",keys:"CTRL+BACKSPACE"}]);
  for(const text of ["process.exit();","wait_ms(30001);",'VIBEKEY_ACTION({"type":"macro","steps":[]});',"tap_code16(KC_UNSUPPORTED);"]) {
    assert.throws(()=>macroFromCode(text));
  }
});

test("website URL validates and survives macro code round trip",async()=>{
  const {validateActionDraft}=await import("../web/model.mjs");
  const action={type:"website",url:"https://example.com/a?q=one%20two#part"};
  assert.equal(newAction("website").type,"website");
  validateActionDraft(action);
  assert.deepEqual(macroFromCode(macroToCode([action])),[action]);
  for(const url of ["example.com","file:///etc/passwd","javascript:alert(1)","https:///path","https://host/a b","https://host\\evil"])
    assert.throws(()=>validateActionDraft({type:"website",url}));
});
