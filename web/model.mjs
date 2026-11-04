export const controls = {top:"语音键", middle:"中键", bottom:"下键", knob:"旋钮按下", cw:"顺时针", ccw:"逆时针"};
export const actionNames = {none:"无动作",inherit:"继承底层",shortcut:"快捷键",text:"输入文本",application:"启动应用",website:"打开网站",shell:"Shell 命令",volume:"音量",macro:"顺序宏",layer:"切换层",profile:"切换方案",momentary_layer:"按住切层",voice:"语音"};
export function clone(value) { return JSON.parse(JSON.stringify(value)); }
export function newAction(type) {
  switch(type) {
    case "shortcut": return {type, keys:"CTRL+C"};
    case "text": case "shell": return {type,value:""};
    case "website": return {type,url:"https://example.com"};
    case "application": return {type,argv:["/usr/bin/true"]};
    case "volume": return {type,operation:"up"};
    case "macro": return {type,steps:[{type:"shortcut",keys:"CTRL+C"},{delay_ms:100}]};
    case "layer": case "momentary_layer": return {type,index:0};
    case "profile": return {type,id:"default"};
    case "voice": return {type,operation:"ptt"};
    default: return {type:"none"};
  }
}
export function setBinding(config, profile, layer, control, gesture, action) {
  const bindings = config.profiles[profile].layers[layer].bindings;
  bindings[control] ||= {};
  if (action === null) delete bindings[control][gesture];
  else {
    bindings[control][gesture] = clone(action);
    if (action.type === "momentary_layer" || action.type === "voice" || action.mode === "hold") {
      bindings[control] = {single:clone(action)};
    }
  }
}

export const keyGroups = {
  "常用":["ESC","TAB","ENTER","SPACE","BACKSPACE","DELETE","INSERT","HOME","END","PAGEUP","PAGEDOWN","UP","DOWN","LEFT","RIGHT","CTRL","SHIFT","ALT","SUPER"],
  "字符":[..."ABCDEFGHIJKLMNOPQRSTUVWXYZ",..."1234567890","MINUS","EQUAL","LEFTBRACE","RIGHTBRACE","BACKSLASH","SEMICOLON","APOSTROPHE","GRAVE","COMMA","DOT","SLASH"],
  "功能键":Array.from({length:24},(_,i)=>"F"+(i+1)).concat(["PRINTSCREEN","PAUSE","CAPSLOCK","NUMLOCK","SCROLLLOCK"]),
  "数字键盘":Array.from({length:10},(_,i)=>"KP"+i).concat(["KPDOT","KPPLUS","KPMINUS","KPASTERISK","KPSLASH","KPENTER"]),
  "媒体":["VOLUMEUP","VOLUMEDOWN","MUTE","PLAYPAUSE","NEXTSONG","PREVIOUSSONG","BTN_LEFT","BTN_RIGHT","BTN_MIDDLE"],
};
export const allKeys = new Set(Object.values(keyGroups).flat().concat(["RIGHTCTRL","RIGHTSHIFT","RIGHTALT","META"]));
export function validShortcut(value) {
  if(typeof value!=="string")return false;
  const parts=value.toUpperCase().split("+").map(s=>s.trim());
  return parts.length>0 && parts.length<=12 && parts.every(k=>allKeys.has(k)) && new Set(parts).size===parts.length;
}
export function validateActionDraft(action,macroStep=false) {
  if(!action || typeof action!=="object" || !(action.type in actionNames))throw new Error("未知动作类型");
  const string=(value,label)=>{if(typeof value!=="string" || value.includes("\0"))throw new Error(label+"无效");};
  if(action.type==="shortcut"){
    if(!validShortcut(action.keys))throw new Error("快捷键无效");
    if(!["tap","hold"].includes(action.mode || "tap"))throw new Error("输出模式无效");
    if(!Number.isInteger(action.repeat ?? 1) || (action.repeat ?? 1)<1 || (action.repeat ?? 1)>20)throw new Error("重复次数必须为 1–20");
    if(action.mode==="hold" && (macroStep || (action.repeat ?? 1)!==1))throw new Error("宏步骤和重复输出不支持保持按住");
  }
  if(action.type==="website"){
    string(action.url,"网站地址");
    let url;try{url=new URL(action.url);}catch{throw new Error("请输入完整的 HTTP(S) 网站地址");}
    if(!/^https?:\/\/[^/?#]/i.test(action.url) || !["http:","https:"].includes(url.protocol) || !url.hostname || /[\s\x00-\x1f\x7f\\]/.test(action.url) || action.url.length>8192)throw new Error("请输入完整的 HTTP(S) 网站地址");
  }
  if(action.type==="application"){
    if(!Array.isArray(action.argv)||!action.argv.length||!action.argv[0]?.trim()||action.argv.length>128)throw new Error("请输入有效的应用启动命令");
    for(const arg of action.argv)string(arg,"应用参数");
  }
  if(["text","shell"].includes(action.type))string(action.value ?? "","文本或命令");
  if(["layer","momentary_layer"].includes(action.type)&&(!Number.isInteger(action.index)||action.index<0||action.index>3))throw new Error("层编号必须为 0–3");
  if(action.type==="profile")string(action.id,"方案");
  if(action.type==="volume"&&!["up","down","mute"].includes(action.operation))throw new Error("音量操作无效");
  if(action.type==="voice"&&!["ptt","confirm","cancel"].includes(action.operation))throw new Error("语音操作无效");
  if(macroStep && ["macro","voice","momentary_layer","inherit"].includes(action.type))throw new Error("不支持的宏步骤");
  if(action.type==="macro") {
    if(!Array.isArray(action.steps)||action.steps.length>100)throw new Error("宏最多 100 步");
    for(const step of action.steps){
      if(step&&"delay_ms" in step){if(!Number.isInteger(step.delay_ms)||step.delay_ms<0||step.delay_ms>30000)throw new Error("等待时间为 0–30000 ms");}
      else validateActionDraft(step,true);
    }
  }
  return action;
}
export function shortcutFromEvent(event) {
  const aliases={Escape:"ESC",Space:"SPACE",ArrowUp:"UP",ArrowDown:"DOWN",ArrowLeft:"LEFT",ArrowRight:"RIGHT",Backspace:"BACKSPACE",PageUp:"PAGEUP",PageDown:"PAGEDOWN",BracketLeft:"LEFTBRACE",BracketRight:"RIGHTBRACE",Backquote:"GRAVE",Quote:"APOSTROPHE",Period:"DOT",NumpadDecimal:"KPDOT",NumpadAdd:"KPPLUS",NumpadSubtract:"KPMINUS",NumpadMultiply:"KPASTERISK",NumpadDivide:"KPSLASH",NumpadEnter:"KPENTER"};
  if (/^(Control|Shift|Alt|Meta)/.test(event.code)) return null;
  const code=event.code.replace(/^Key/,"").replace(/^Digit/,"").replace(/^Numpad(\d)$/,"KP$1");
  const key=aliases[event.code] || code.toUpperCase();
  if (!allKeys.has(key)) return null;
  return [event.ctrlKey&&"CTRL",event.shiftKey&&"SHIFT",event.altKey&&"ALT",event.metaKey&&"SUPER",key].filter(Boolean).join("+");
}
export function actionLabel(action) {
  if (!action) return "—";
  if (action.label) return action.label;
  switch(action.type) {
    case "none":return "×";
    case "inherit":return "▽";
    case "shortcut":return action.keys+(action.mode==="hold"?" ↓":action.repeat>1?" ×"+action.repeat:"");
    case "volume":return {up:"Vol +",down:"Vol −",mute:"Mute"}[action.operation];
    case "layer":return "TO("+action.index+")";
    case "momentary_layer":return "MO("+action.index+")";
    case "application":return (action.argv?.[0] || "APP").split("/").pop();
    case "macro":return "Macro · "+(action.steps?.length || 0);
    case "voice":return {ptt:"按住说话",confirm:"确认文本",cancel:"取消转写"}[action.operation];
    case "profile":return action.id;
    case "text":return action.value || "文本";
    case "website":return action.url || "网站";
    case "shell":return "Shell";
    default:return "—";
  }
}
export function resolveBinding(config,profile,layer,control,gesture) {
  let action=config.profiles[profile].layers[layer].bindings[control]?.[gesture];
  while (action?.type==="inherit" && layer>0) action=config.profiles[profile].layers[--layer].bindings[control]?.[gesture];
  return action?.type==="inherit" ? {type:"none"} : action;
}
export function ensureLibrary(config) { return config.library ||= {applications:[],macros:[]}; }
export function libraryUsage(config,id) {
  let count=0;
  const visit=action=>{if(action?.library_id===id)count++;action?.steps?.forEach(visit);};
  for(const p of Object.values(config.profiles))for(const l of p.layers)for(const b of Object.values(l.bindings))Object.values(b).forEach(visit);
  for(const item of config.library?.macros || [])item.action.steps.forEach(visit);
  return count;
}
export function saveLibraryItem(config,category,item) {
  const library=ensureLibrary(config), items=library[category];
  const index=items.findIndex(i=>i.id===item.id);
  if(index<0 && items.length>=16)throw new Error("每个分类最多 16 个动作");
  if(!item.name.trim())throw new Error("请输入动作名称");
  if(index<0)items.push(clone(item));else items[index]=clone(item);
  const replace=action=>{
    if(action?.library_id===item.id)Object.assign(action,clone(item.action),{label:item.name,library_id:item.id});
    else action?.steps?.forEach(replace);
  };
  for(const p of Object.values(config.profiles))for(const l of p.layers)for(const b of Object.values(l.bindings))Object.values(b).forEach(replace);
  for(const macro of library.macros)if(macro.id!==item.id)macro.action.steps.forEach(replace);
}
const qmkAliases={ENT:"ENTER",BSPC:"BACKSPACE",SPC:"SPACE",DEL:"DELETE",INS:"INSERT",PGUP:"PAGEUP",PGDN:"PAGEDOWN",LCTL:"CTRL",LSFT:"SHIFT",LALT:"ALT",LGUI:"SUPER"};
export function macroToCode(steps) {
  return steps.map(step=>{
    if("delay_ms" in step)return `wait_ms(${step.delay_ms});`;
    if(step.type==="shortcut" && !step.repeat && !step.mode) {
      const parts=step.keys.split("+");
      const mods={CTRL:"LCTL",SHIFT:"LSFT",ALT:"LALT",SUPER:"LGUI"};
      if(parts.slice(0,-1).every(p=>mods[p])) {
        let value="KC_"+parts.pop();
        for(const mod of parts.reverse())value=mods[mod]+"("+value+")";
        return "tap_code16("+value+");";
      }
    }
    return "VIBEKEY_ACTION("+JSON.stringify(step)+");";
  }).join("\n");
}
export function macroFromCode(source) {
  const steps=[];
  for (const line of source.split("\n")) {
    const value=line.trim();
    if(!value || value.startsWith("//"))continue;
    let match=value.match(/^wait_ms\((\d+)\);$/);
    if(match){const ms=Number(match[1]);if(ms>30000)throw new Error("等待时间最多 30000 ms");steps.push({delay_ms:ms});continue;}
    match=value.match(/^VIBEKEY_ACTION\((.*)\);$/);
    if(match) {
      const step=JSON.parse(match[1]);
      if(!step || typeof step!=="object" || Array.isArray(step) ||
        !["shortcut","application","website","text","volume","shell","layer","profile"].includes(step.type) ||
        step.mode==="hold")throw new Error("不支持的宏步骤");
      if(step.type==="shortcut" && !validShortcut(step.keys || ""))throw new Error("无效的快捷键");
      steps.push(step);continue;
    }
    match=value.match(/^tap_code16\((.*)\);$/);
    if(!match)throw new Error("无法识别的宏代码："+value);
    let key=match[1], mods=[];
    while(true) {
      const nested=key.match(/^(LCTL|LSFT|LALT|LGUI)\((.*)\)$/);
      if(!nested)break;
      mods.push(qmkAliases[nested[1]]);key=nested[2];
    }
    if(!/^KC_[A-Z0-9_]+$/.test(key))throw new Error("无效的 QMK 键码");
    const name=key.slice(3), keys=mods.concat(qmkAliases[name] || name).join("+");
    if(!validShortcut(keys))throw new Error("不支持的快捷键："+keys);
    steps.push({type:"shortcut",keys});
  }
  if(steps.length>100)throw new Error("宏最多 100 步");
  validateActionDraft({type:"macro",steps});
  return steps;
}
export function addProfile(config, id, name, source) {
  if (!id || config.profiles[id]) throw new Error("配置方案 ID 重复");
  if (Object.keys(config.profiles).length >= 32) throw new Error("最多 32 个方案");
  config.profiles[id] = clone(config.profiles[source]);
  config.profiles[id].name = name;
}
