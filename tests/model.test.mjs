import test from "node:test";
import assert from "node:assert/strict";
import {newAction,setBinding,addProfile,shortcutFromEvent,resolveBinding,saveLibraryItem,libraryUsage,macroFromCode,macroToCode,validShortcut,activeVoiceBinding,setRotationMode,rotationModeFor,rotationModes} from "../web/model.mjs";

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

test("preset voice copy resolves inherited bindings from the active layer",()=>{
  const value=config();value.active_profile="default";value.active_layer=2;
  value.profiles.default.layers[0].bindings.top={single:{type:"shortcut",keys:"RIGHTALT",mode:"hold"}};
  value.profiles.default.layers[1].bindings.top={single:{type:"inherit"}};
  value.profiles.default.layers[2].bindings.top={single:{type:"inherit"}};
  const binding=activeVoiceBinding(value);
  assert.deepEqual(binding,{single:{type:"shortcut",keys:"RIGHTALT",mode:"hold"}});
  binding.single.keys="CTRL+D";
  assert.equal(value.profiles.default.layers[0].bindings.top.single.keys,"RIGHTALT");
});

test("rotation modes preserve other controls, layers and profiles",()=>{
  const value=config();addProfile(value,"terminal","Terminal","default");
  const before=structuredClone(value);
  setRotationMode(value,"terminal",0,"terminator-panes");
  assert.equal(rotationModeFor(value,"terminal",0),"terminator-panes");
  const bindings=value.profiles.terminal.layers[0].bindings;
  assert.equal(bindings.cw.single.keys,"CTRL+SHIFT+N");
  assert.equal(bindings.ccw.single.keys,"CTRL+SHIFT+P");
  assert.deepEqual(bindings.top,before.profiles.terminal.layers[0].bindings.top);
  assert.deepEqual(value.profiles.default,before.profiles.default);
  assert.deepEqual(value.profiles.terminal.layers.slice(1),before.profiles.terminal.layers.slice(1));
  bindings.cw.single.label="Changed";
  assert.equal(rotationModeFor(value,"terminal",0),"terminator-panes");
  assert.equal(rotationModes["terminator-panes"].cw.label,"下一个终端");
  const snapshot=structuredClone(value);
  assert.throws(()=>setRotationMode(value,"terminal",0,"invalid"));
  assert.deepEqual(value,snapshot);
});
test("rotation mode detection resolves inheritance and rejects modified output",()=>{
  const value=config();
  setRotationMode(value,"default",0,"terminal-tabs");
  assert.equal(value.profiles.default.layers[0].bindings.cw.single.keys,"CTRL+PAGEDOWN");
  assert.equal(value.profiles.default.layers[0].bindings.ccw.single.keys,"CTRL+PAGEUP");
  for(const control of ["cw","ccw"])setBinding(value,"default",1,control,"single",{type:"inherit"});
  assert.equal(rotationModeFor(value,"default",1),"terminal-tabs");
  value.profiles.default.layers[0].bindings.cw.single.repeat=2;
  assert.equal(rotationModeFor(value,"default",1),"custom");
  value.profiles.default.layers[0].bindings.cw.single.repeat=1;
  value.profiles.default.layers[0].bindings.cw.single.mode="hold";
  assert.equal(rotationModeFor(value,"default",0),"custom");
  setRotationMode(value,"default",1,"volume");
  assert.equal(rotationModeFor(value,"default",1),"volume");
  assert.equal(rotationModeFor(value,"default",2),"custom");
});
