import {controls, actionNames, clone, newAction, setBinding, addProfile, keyGroups, actionLabel, resolveBinding, ensureLibrary, libraryUsage, saveLibraryItem, validShortcut,validateActionDraft} from "/model.mjs";
import {node,button,option,actionFields,macroEditor,recordShortcut,stopRecorders} from "/editors.mjs";
import {setupLanguage} from "/i18n.mjs";

const $ = id => document.getElementById(id);
let config, token, state, capabilities, profile, layer = 0, selected = "top";
let dirty = false, rawSignal = null, previewTimer, refreshTimer, noticeTimer;
let gesture="single", category="常用", search="", libraryDraft=null, libraryCategory="", macroDraftEditor=null;
const gestureNames={single:"单击",double:"双击",hold:"长按"};
const categories=["常用","字符","功能键","数字键盘","组合键","Layer","APP","宏","媒体","其他"];
let currentPage="workspace";
function showPage(page) {
  stopRecorders();currentPage=page;
  document.querySelectorAll(".page").forEach(section=>section.hidden=section.id!==page);
  document.querySelectorAll("[data-page]").forEach(item=>item.classList.toggle("current",item.dataset.page===page));
  if(page!=="workspace")ensurePageSave();
  window.scrollTo(0,0);
}
function ensurePageSave() {
  for(const page of ["voice","settings"])if(!$(page).querySelector(".page-save")){
    const bar=node("div","save-bar page-save");bar.append(node("span","muted","修改保存在当前草稿，保存后生效"),button("保存到本机",guarded(save),"primary"));$(page).append(bar);
  }
}
for(const item of document.querySelectorAll("[data-page]"))item.onclick=()=>showPage(item.dataset.page);
document.querySelector(".brand").onclick=event=>{event.preventDefault();showPage("workspace");};
const eventLines = [];
const rotationCounts = {cw:0, ccw:0}, pulseTimers = new Map();
function inputFeedback(data) {
  if (!(data.control in controls)) return;
  const buttons = document.querySelectorAll(`[data-control="${data.control}"]`);
  if (data.pulse && data.pressed) {
    clearTimeout(pulseTimers.get(data.control));
    if (data.control === "cw" || data.control === "ccw") {
      const other = data.control === "cw" ? "ccw" : "cw";
      clearTimeout(pulseTimers.get(other));
      document.querySelectorAll(`[data-control="${other}"]`).forEach(button => button.classList.remove("active"));
      rotationCounts[data.control]++;
      $(data.control+"-count").textContent=String(rotationCounts[data.control]);
    }
    pulseTimers.set(data.control,setTimeout(()=>buttons.forEach(button=>button.classList.remove("active")),250));
  }
  buttons.forEach(button=>button.classList.toggle("active",data.pressed));
  document.querySelectorAll(`[data-block="${data.control}"]`).forEach(block=>block.classList.toggle("active",data.pressed));
  if (data.pressed) $("last-input").textContent="最近输入："+controls[data.control];
}
$("reset-input").onclick=()=>{
  rotationCounts.cw=rotationCounts.ccw=0;
  $("cw-count").textContent=$("ccw-count").textContent="0";
};
function notice(message) {
  clearTimeout(noticeTimer);$("notice").textContent=message;$("notice").hidden=!message;
  if(message)noticeTimer=setTimeout(()=>$("notice").hidden=true,8000);
}
function changed() { dirty = true; $("dirty").textContent = "有未保存的修改"; $("config-json").value = JSON.stringify(config,null,2); }
async function api(path, body, method = "POST") {
  const response = await fetch(path, body === undefined ? {} : {
    method, headers:{"Content-Type":"application/json","X-VibeKey-Token":token},body:JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function guarded(fn) { return async (...args) => { try { await fn(...args); } catch(e) { notice(e.message); } }; }
function renderProfiles() {
  $("profile").replaceChildren();
  for (const [id,p] of Object.entries(config.profiles)) option($("profile"),id,p.name);
  $("profile").value=profile;$("profile-name").value=config.profiles[profile].name;
  $("layer").replaceChildren();$("layer-tabs").replaceChildren();
  config.profiles[profile].layers.forEach((l,i)=>{
    option($("layer"),String(i),`${i} · ${l.name}`);
    const tab=button(String(i),()=>{layer=i;renderProfiles();renderBindings();},i===layer?"current":"");
    tab.setAttribute("aria-label","Layer "+i);tab.setAttribute("aria-pressed",String(i===layer));$("layer-tabs").append(tab);
  });
  $("layer").value=String(layer);$("layer-name").textContent=config.profiles[profile].layers[layer].name;
  renderActivation();
}
function renderActivation() {
  if(!config)return;
  const activeProfile=state?.active_profile ?? config.active_profile;
  const activeLayer=state?.active_layer ?? config.active_layer;
  const different=profile!==activeProfile || layer!==activeLayer;
  $("activate").classList.toggle("primary",different);
  $("activation-warning").hidden=!different;
  if(different)$("activation-warning").textContent=`当前仅在编辑「${config.profiles[profile].name}」Layer ${layer}；设备仍使用「${config.profiles[activeProfile]?.name || activeProfile}」Layer ${activeLayer}。点击“启用此方案与层”才会切换。`;
}
function currentAction() { return config.profiles[profile].layers[layer].bindings[selected]?.[gesture]; }
function isRotation() { return ["cw","ccw"].includes(selected); }
function edgeAction(action) { return ["voice","momentary_layer"].includes(action?.type) || action?.mode==="hold"; }
function selectControl(control,which="single") {
  stopRecorders();selected=control;gesture=["cw","ccw"].includes(control)?"single":which;renderBindings();
}
function assign(action) {
  if(action?.type==="voice" && gesture!=="single")throw new Error("语音动作仅支持单击绑定");
  if(action?.type==="momentary_layer" && (gesture!=="single" || isRotation()))throw new Error("按住切层仅支持按键的单击绑定");
  if(action?.type==="voice" && action.operation==="ptt" && isRotation())throw new Error("旋转无法按住录音");
  setBinding(config,profile,layer,selected,gesture,action);changed();renderBindings();
}
function renderMatrix() {
  document.querySelectorAll("[data-control]").forEach(item=>{
    item.classList.toggle("selected",item.dataset.control===selected);item.setAttribute("aria-pressed",String(item.dataset.control===selected));
  });
  for(const matrix of document.querySelectorAll("[data-matrix]")){
    const control=matrix.dataset.matrix;matrix.replaceChildren();
    const single=resolveBinding(config,profile,layer,control,"single");
    for(const [which,label] of Object.entries(gestureNames)){
      const action=config.profiles[profile].layers[layer].bindings[control]?.[which];
      const cell=button("",()=>selectControl(control,which),"gesture-cell"+(selected===control&&gesture===which?" selected":"")+(!action?" unset":""));
      cell.dataset.gesture=which;cell.dataset.gestureControl=control;
      cell.disabled=which!=="single"&&edgeAction(single);
      const inherited=action?.type==="inherit"?resolveBinding(config,profile,layer,control,which):null;
      cell.title=controlName(control)+" · "+label+"："+actionLabel(action)+(inherited?" → "+actionLabel(inherited):"");
      cell.setAttribute("aria-label",controlName(control)+" · "+label);
      cell.append(node("small","",label),node("strong","",actionLabel(action)));matrix.append(cell);
    }
  }
  for(const item of document.querySelectorAll("[data-summary]"))item.textContent=actionLabel(config.profiles[profile].layers[layer].bindings[item.dataset.summary]?.single);
}
function controlName(control) { return control==="top"?"上键":controls[control]; }
function renderBindings() {
  if(gesture!=="single" && edgeAction(resolveBinding(config,profile,layer,selected,"single")))gesture="single";
  renderMatrix();
  $("control-title").textContent=controlName(selected);$("gesture-title").textContent=isRotation()?"转动":gestureNames[gesture];
  const action=currentAction();$("mapping-label").textContent=actionLabel(action);$("binding-kind").textContent=actionNames[action?.type] || "未设置";
  const parent=$("bindings");parent.replaceChildren();
  const stack=node("div","field-stack"),label=node("label"),select=node("select");
  select.setAttribute("aria-label","动作类型");option(select,"unset","未设置");
  for(const [kind,name] of Object.entries(actionNames)){
    if(gesture!=="single" && ["voice","momentary_layer"].includes(kind))continue;
    if(isRotation()&&kind==="momentary_layer")continue;
    option(select,kind,name);
  }
  select.value=action?.type || "unset";
  select.onchange=guarded(()=>{
    let next=select.value==="unset"?null:newAction(select.value);
    if(next?.type==="profile")next.id=profile;
    if(next?.type==="voice"&&isRotation())next.operation="confirm";
    assign(next);
  });
  label.append(node("span","","动作类型"),select);stack.append(label);parent.append(stack);
  if(action)actionFields(parent,action,assign,{config,rotation:isRotation(),notice,editMacro:()=>openLibrary("macros",null,action,true)});
  $("output-options").replaceChildren();
  if(action?.type==="shortcut"){
    const mode=node("select"),options=$("output-options"),wrapper=node("div","output-mode");
    option(mode,"tap","短按一次 / 连按");if(!isRotation()&&gesture==="single")option(mode,"hold","保持按住");
    mode.value=action.mode || "tap";mode.setAttribute("aria-label","按键输出模式");
    mode.onchange=guarded(()=>assign({...clone(action),mode:mode.value,repeat:1}));wrapper.append(mode);
    if(mode.value!=="hold"){
      const count=node("input");count.type="number";count.min="1";count.max="20";count.value=action.repeat || 1;count.setAttribute("aria-label","重复次数");
      count.onchange=guarded(()=>{const repeat=Number(count.value);if(!Number.isInteger(repeat)||repeat<1||repeat>20)throw new Error("重复次数必须为 1–20");assign({...clone(action),repeat});});
      wrapper.append(count,node("span","muted","次"));
    }
    options.append(wrapper);
  }
  renderPalette();
}
function renderPalette() {
  $("palette-tabs").replaceChildren();
  for(const name of categories){
    const tab=button(name,()=>{stopRecorders();category=name;search="";$("key-search").value="";renderPalette();},name===category?"current":"");
    tab.setAttribute("role","tab");tab.setAttribute("aria-selected",String(name===category));tab.dataset.category=name;$("palette-tabs").append(tab);
  }
  const parent=$("palette-content");parent.replaceChildren();
  if(category==="组合键"){renderCombo(parent);return;}
  if(category==="APP"||category==="宏"){renderLibrary(parent,category==="APP"?"applications":"macros");return;}
  const grid=node("div","key-grid");parent.append(grid);
  const add=(text,action,title=text)=>{
    if(search && ![text,title].some(value=>value.toLowerCase().includes(search)))return;
    const keycap=button(text,guarded(()=>assign(action)),"keycap"+(JSON.stringify(action)===JSON.stringify(currentAction())?" assigned":""));keycap.title=title;keycap.dataset.key=text;grid.append(keycap);
  };
  if(category==="Layer")for(let index=0;index<4;index++){
    add(`TO(${index})`,{type:"layer",index},"切换到 Layer "+index);
    if(!isRotation()&&gesture==="single")add(`MO(${index})`,{type:"momentary_layer",index},"按住启用 Layer "+index);
  }
  else if(category==="其他"){
    add("×",{type:"none"},"不执行动作");add("▽",{type:"inherit"},"继承底层");
    if(gesture==="single" && !isRotation())add("fcitx5-vinput",{type:"shortcut",keys:"RIGHTALT",mode:"hold",label:"fcitx5-vinput"},"按住说话，松开识别；需先启动 fcitx5-vinput");
    add("打开网站",newAction("website"));add("文本",{type:"text",value:""});add("Shell",{type:"shell",value:""});
    if(gesture==="single")for(const operation of ["ptt","confirm","cancel"]){if(isRotation()&&operation==="ptt")continue;add({ptt:"按住说话",confirm:"确认文本",cancel:"取消转写"}[operation],{type:"voice",operation});}
    add("切换方案",{type:"profile",id:profile});
  }else{
    if(category==="常用"){add("×",{type:"none"},"不执行动作");add("▽",{type:"inherit"},"继承底层");}
    const keys=search?Object.values(keyGroups).flat():keyGroups[category] || [];
    for(const keyspec of new Set(keys))add(keyspec,{type:"shortcut",keys:keyspec});
  }
  if(!grid.children.length)parent.append(node("p","empty-note","没有匹配的按键"));
}
function renderCombo(parent) {
  const panel=node("div","combo-panel");parent.append(panel);
  const current=currentAction(), initial=current?.type==="shortcut"?current.keys:"CTRL+C";
  let keys=initial;
  const preview=node("div","combo-preview",keys),row=node("div","field-row"),input=node("input");input.value=keys;input.setAttribute("aria-label","组合键内容");
  const update=value=>{keys=value;input.value=value;preview.textContent=value;};
  input.oninput=()=>{keys=input.value.toUpperCase();preview.textContent=keys;};
  row.append(input,button("分配组合键",guarded(()=>{if(!validShortcut(keys))throw new Error("组合键无效");assign({type:"shortcut",keys});}),"primary"));
  const record=button("录制快捷键",()=>recordShortcut(record,update,notice));row.append(record);
  const mods=node("div","combo-modifiers");
  for(const modifier of ["CTRL","SHIFT","ALT","SUPER"])mods.append(button(modifier,()=>{
    let parts=keys.split("+").filter(Boolean);parts=parts.includes(modifier)?parts.filter(p=>p!==modifier):[modifier,...parts];update(parts.join("+"));
  }));
  panel.append(node("p","palette-message","按下组合键录制，或选择修饰键后输入主键。浏览器可能截获部分系统快捷键，可手动填写。"),preview,mods,row);
}
function renderLibrary(parent,collection) {
  const library=ensureLibrary(config),items=library[collection],macro=collection==="macros";
  const heading=node("div","library-toolbar");heading.append(node("span","muted",`${macro?"宏":"APP"} 动作库 · ${items.length} / 16`),button(macro?"＋ 新建宏":"＋ 添加 APP",()=>openLibrary(collection),"primary"));parent.append(heading);
  if(!items.length)parent.append(node("div","library-empty",macro?"暂无宏 · 录制或编排一组操作，再分配给任意控件":"暂无 APP · 从已安装应用中选择，或填写启动命令"));
  const grid=node("div","library-grid");parent.append(grid);
  items.forEach((item,index)=>{
    if(search&&!item.name.toLowerCase().includes(search))return;
    const card=node("div","library-card"),assignButton=button("",guarded(()=>assign({...clone(item.action),label:item.name,library_id:item.id})),"library-assign");
    assignButton.title="分配 "+item.name;assignButton.append(node("span","library-slot",(macro?"M":"A")+index),node("span","",item.name));
    const actions=node("div","library-actions");actions.append(button("编辑",()=>openLibrary(collection,item)),button("删除",guarded(()=>{
      if(libraryUsage(config,item.id))throw new Error("该动作仍被绑定或被宏引用，请先移除引用");
      library[collection]=items.filter(i=>i.id!==item.id);changed();renderPalette();
    }),"danger"));card.append(assignButton,node("small","",macro?item.action.steps.length+" 个步骤":(item.action.argv[0] || "启动命令")),actions);grid.append(card);
  });
  if(currentAction()?.type===(macro?"macro":"application")&&!currentAction()?.library_id)parent.append(button("从当前动作创建",()=>openLibrary(collection,null,currentAction())));
  parent.append(node("p","palette-message","点击动作卡片分配；编辑库动作会同步更新其所有绑定，保存到本机后生效。"));
}
async function openLibrary(collection,item=null,initial=null,direct=false) {
  stopRecorders();libraryCategory=collection;
  libraryDraft=item?clone(item):{id:"action-"+Date.now().toString(36),name:"",action:clone(initial || (collection==="macros"?{type:"macro",steps:[]}:newAction("application")))};
  delete libraryDraft.action.label;delete libraryDraft.action.library_id;
  libraryDraft.direct=direct;libraryDraft.target={profile,layer,selected,gesture};
  $("library-title").textContent=collection==="macros"?(direct?"编辑宏步骤":item?"编辑宏":"新建宏"):(item?"编辑 APP":"添加 APP");
  $("library-name").value=libraryDraft.name;$("library-name").required=!direct;$("library-name").closest("label").hidden=direct;
  $("library-error").textContent="";$("library-dialog").showModal();
  await renderLibraryEditor();
}
async function renderLibraryEditor() {
  const parent=$("library-editor");parent.replaceChildren();macroDraftEditor=null;
  const context={config,library:ensureLibrary(config),notice:message=>$("library-error").textContent=message};
  if(libraryCategory==="macros")macroDraftEditor=macroEditor(parent,libraryDraft.action.steps,steps=>libraryDraft.action.steps=steps,context);
  else{
    const draft=libraryDraft;
    const label=node("label"),searchInput=node("input");searchInput.type="search";searchInput.placeholder="搜索已安装应用";searchInput.setAttribute("aria-label","搜索已安装应用");
    label.append(node("span","","已安装的 Ubuntu 应用"),searchInput);parent.append(label);
    const list=node("div","library-application-list");parent.append(list);
    try{
      const response=await api("/api/applications");if(libraryDraft!==draft)return;
      const render=()=>{
        list.replaceChildren();const query=searchInput.value.toLowerCase();
        for(const app of response.applications.filter(a=>a.name.toLowerCase().includes(query)).slice(0,30)){
          const item=button("",()=>{libraryDraft.action={type:"application",argv:clone(app.argv),wm_class:app.wm_class || ""};if(!$("library-name").value)$("library-name").value=app.name;renderLibraryEditor();});
          item.append(node("span","",app.name),node("small","",app.argv[0]));list.append(item);
        }
        if(!list.children.length)list.append(node("p","muted","没有匹配的应用，可手动填写命令"));
      };searchInput.oninput=render;render();
    }catch(error){list.append(node("p","muted","应用目录暂不可用，可手动填写命令"));}
    actionFields(parent,libraryDraft.action,value=>{libraryDraft.action=value;renderLibraryEditor();},context);
  }
}
function closeLibrary(){stopRecorders();$("library-dialog").close();libraryDraft=null;}
$("close-library").onclick=$("cancel-library").onclick=closeLibrary;
$("library-dialog").addEventListener("cancel",()=>{stopRecorders();libraryDraft=null;});
$("library-form").onsubmit=event=>{
  event.preventDefault();
  try{
    if(macroDraftEditor)libraryDraft.action.steps=macroDraftEditor.getSteps();
    validateActionDraft(libraryDraft.action);
    stopRecorders();
    if(libraryDraft.action.type==="application"&&!libraryDraft.action.argv?.[0]?.trim())throw new Error("请输入可执行文件");
    if(libraryDraft.action.type==="macro"&&!libraryDraft.action.steps.length)throw new Error("请至少添加一个宏步骤");
    const {direct,target,...item}=libraryDraft;item.name=$("library-name").value.trim();
    if(direct){setBinding(config,target.profile,target.layer,target.selected,target.gesture,item.action);changed();}
    else{saveLibraryItem(config,libraryCategory,item);changed();}
    closeLibrary();renderBindings();
  }catch(error){$("library-error").textContent=error.message;}
};
$("key-search").oninput=()=>{search=$("key-search").value.toLowerCase();renderPalette();};
const voiceFields = {
  "voice-source":"source", "voice-language":"language", "voice-executable":"whisper_executable",
  "voice-model-path":"model_path", "voice-api-url":"api_url", "voice-api-model":"api_model", "voice-api-env":"api_key_env"
};
function renderForms() {
  $("voice-backend").value = config.voice.backend;
  for (const [id,key] of Object.entries(voiceFields)) $(id).value=config.voice[key];
  $("voice-max").value=config.voice.max_seconds;
  $("voice-timeout").value=config.voice.timeout_seconds;
  $("voice-auto").checked=config.voice.auto_insert;
  $("voice-command").value=JSON.stringify(config.voice.command);
  $("double-ms").value=config.gestures.double_ms;
  $("hold-ms").value=config.gestures.hold_ms;
  $("device-serial").value=config.device.serial;
  $("device-path").value=config.device.usb_path;
  $("config-json").value=JSON.stringify(config,null,2);
  renderBackend();
}
function renderBackend() { for (const backend of ["command","whisper","api"]) $("backend-"+backend).hidden=backend!==config.voice.backend; }
function updateVoice(voice) {
  $("voice-status").textContent = {idle:"空闲",recording:"正在录音",transcribing:"正在转写",ready:"等待确认",delivered:"已交付",error:"出错"}[voice.state] || voice.state;
  $("voice-result").value=voice.text || "";
  $("record").disabled=["recording","transcribing"].includes(voice.state);
  $("stop-record").disabled=voice.state!=="recording";
  $("confirm-voice").disabled=voice.state!=="ready";
  if (voice.error) notice(voice.error);
}
async function refresh() {
  state = await api("/api/state"); token=state.token;
  const connected=state.device.connected;
  $("connection").textContent=state.simulate ? "● 模拟模式" : connected ? "● AU05 已连接" : "○ 等待设备";
  $("connection").className="status "+(connected ? "online":"error");
  $("active-state").textContent=`正在使用：${config.profiles[state.active_profile]?.name || state.active_profile} · Layer ${state.active_layer}${state.preview ? " · 预览中":""}`;
  renderActivation();
  const battery=state.device.battery;
  $("battery").textContent=battery?.percent!==null&&battery?.percent!==undefined?`${battery.charging?"ϟ ":""}${battery.percent}%`:"电量未知";
  $("device-cards").replaceChildren();
  for(const [title,value] of [["连接状态",connected?"AU05 已连接":"等待设备"],["设备序列号",state.selected?.serial || "—"],["会话",capabilities.session.toUpperCase()]]){
    const card=node("div","device-card");card.append(node("small","",title),node("strong","",value));$("device-cards").append(card);
  }
  $("simulate-input").disabled=!state.simulate;
  if (!state.simulate) $("simulate-input").checked=false;
  $("session").textContent=`${capabilities.session.toUpperCase()} · Python ${capabilities.languages.core}`;
  $("diagnostics").textContent=JSON.stringify({capabilities,...state,token:undefined},null,2);
  updateVoice(state.voice);
  if (state.config_error || state.device.error) notice(state.config_error || state.device.error);
}
function scheduleRefresh() { clearTimeout(refreshTimer); refreshTimer=setTimeout(guarded(refresh),100); }
async function load() {
  config=await api("/api/config");
  profile=config.active_profile; layer=config.active_layer; dirty=false;ensureLibrary(config);
  renderProfiles(); renderBindings(); renderForms(); $("dirty").textContent="配置已加载";
  await refresh();
}
$("profile").onchange=() => { stopRecorders();profile=$("profile").value; renderProfiles(); renderBindings(); };
$("layer").onchange=() => { stopRecorders();layer=Number($("layer").value);renderProfiles(); renderBindings(); };
$("add-profile").onclick=guarded(() => {
  const name=window.prompt("新方案名称"); if (!name?.trim()) return;
  const id="profile-"+Date.now().toString(36);
  addProfile(config,id,name.trim(),profile); profile=id; changed(); renderProfiles(); renderBindings();
});
$("delete-profile").onclick=guarded(() => {
  for(const item of config.library?.macros || [])if(item.action.steps.some(step=>step.type==="profile" && step.id===profile))throw new Error("动作库中的宏仍引用此方案");
  if (Object.keys(config.profiles).length===1) throw new Error("至少保留一个配置方案");
  const old=profile, next=Object.keys(config.profiles).find(id=>id!==old);
  for (const p of Object.values(config.profiles)) for (const l of p.layers) for (const bindings of Object.values(l.bindings)) {
    for (const action of Object.values(bindings)) {
      if (action.type==="profile" && action.id===old) throw new Error("仍有动作引用此方案，请先移除引用");
      if (action.type==="macro" && action.steps.some(s=>s.type==="profile" && s.id===old)) throw new Error("宏仍引用此方案");
    }
  }
  delete config.profiles[old]; if (config.active_profile===old) {config.active_profile=next;config.active_layer=0;}
  profile=next; changed();renderProfiles();renderBindings();
});
$("activate").onclick=guarded(async () => { config.active_profile=profile; config.active_layer=layer; changed(); await save(); });
async function save() { await api("/api/config",config,"PUT"); dirty=false; $("dirty").textContent="已保存"; notice(""); await refresh(); }
$("save").onclick=guarded(save);
function discard(){if(!dirty || window.confirm("丢弃尚未保存的修改？"))return load();}
$("reload").onclick=$("discard").onclick=guarded(discard);
$("rename-profile").onclick=guarded(()=>{
  const name=$("profile-name").value.trim();if(!name)throw new Error("方案名称不能为空");
  config.profiles[profile].name=name;changed();renderProfiles();
});
$("rename-layer").onclick=guarded(()=>{
  const name=window.prompt("图层名称",config.profiles[profile].layers[layer].name);if(!name?.trim())return;
  config.profiles[profile].layers[layer].name=name.trim();changed();renderProfiles();
});
for (const [id,key] of Object.entries(voiceFields)) $(id).oninput=() => {config.voice[key]=$(id).value;changed();};
$("voice-backend").onchange=()=>{config.voice.backend=$("voice-backend").value;renderBackend();changed();};
for (const [id,key] of [["voice-max","max_seconds"],["voice-timeout","timeout_seconds"]]) $(id).oninput=()=>{config.voice[key]=Number($(id).value);changed();};
$("voice-auto").onchange=()=>{config.voice.auto_insert=$("voice-auto").checked;changed();};
$("voice-command").onchange=guarded(()=>{const value=JSON.parse($("voice-command").value);if(!Array.isArray(value))throw new Error("命令必须是 JSON 数组");config.voice.command=value;changed();});
for (const [id,key] of [["double-ms","double_ms"],["hold-ms","hold_ms"]]) $(id).oninput=()=>{config.gestures[key]=Number($(id).value);changed();};
for (const [id,key] of [["device-serial","serial"],["device-path","usb_path"]]) $(id).oninput=()=>{config.device[key]=$(id).value;changed();};
$("preview").onchange=guarded(async()=>{
  clearInterval(previewTimer);
  const on=$("preview").checked;
  await api("/api/preview",{seconds:on ? 15:0});
  if(on) previewTimer=setInterval(guarded(async()=>{await api("/api/preview",{seconds:15});}),5000);
  await refresh();
});
$("learn").onclick=guarded(()=>{
  if (!$("preview").checked || !state.preview || !rawSignal) throw new Error("请先开启预览，并按下设备上的按键");
  config.device.mapping[rawSignal]=selected;changed();notice(`已映射 ${rawSignal} → ${controls[selected]}，请保存配置。`);
});
$("cancel").onclick=guarded(()=>api("/api/cancel",{}));
$("refresh-device").onclick=guarded(()=>api("/api/device/refresh",{}));
for (const [id,operation] of [["record","start"],["stop-record","stop"],["confirm-voice","confirm"],["cancel-voice","cancel"]]) {
  $(id).onclick=guarded(async()=>{await api("/api/voice/test",{operation});await refresh();});
}
$("copy-result").onclick=guarded(async()=>{await navigator.clipboard.writeText($("voice-result").value);notice("结果已复制");});
$("export").onclick=()=>{
  const url=URL.createObjectURL(new Blob([JSON.stringify(config,null,2)],{type:"application/json"}));
  const link=document.createElement("a");link.href=url;link.download="vibekey-config.json";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
function importConfig(value) {
  if(value?.version!==1 || !value.profiles || !value.profiles[value.active_profile]) throw new Error("配置结构或版本无效；导入支持版本 1");
  const previous = {config,profile,layer};
  try {
  config=clone(value);ensureLibrary(config);profile=config.active_profile;layer=config.active_layer;
  renderProfiles();renderBindings();renderForms();
  } catch (error) {
    ({config,profile,layer}=previous);
    renderProfiles();renderBindings();renderForms();
    throw new Error("配置字段不完整：" + error.message);
  }
  changed();notice("配置已载入编辑区，保存时后台会校验全部字段。");
}
$("import").onchange=guarded(async()=>{
  const file=$("import").files[0];if(!file)return;
  if(file.size>1048576)throw new Error("配置文件不得超过 1 MiB");
  importConfig(JSON.parse(await file.text()));$("import").value="";
});
$("apply-json").onclick=guarded(()=>importConfig(JSON.parse($("config-json").value)));
document.querySelectorAll("[data-control]").forEach(button=>{
  let chain=Promise.resolve(), down=false;
  const send=pressed=>{chain=chain.then(()=>api("/api/simulate",{control:button.dataset.control,pressed})).catch(e=>notice(e.message));};
  button.onclick=()=>selectControl(button.dataset.control);
  button.onpointerdown=e=>{
    selectControl(button.dataset.control);
    if(!$("simulate-input").checked)return;
    e.preventDefault();button.setPointerCapture(e.pointerId);down=true;send(true);
  };
  const up=()=>{if(down){down=false;send(false);}};
  button.onpointerup=up;button.onpointercancel=up;button.onlostpointercapture=up;
});
window.addEventListener("beforeunload",event=>{if(dirty){event.preventDefault();event.returnValue="";}});
setupLanguage();
guarded(async()=>{
  capabilities=await api("/api/capabilities");await load();ensurePageSave();
  const stream=new EventSource("/api/events");
  stream.onmessage=event=>{
    const data=JSON.parse(event.data);
    if(data.type==="raw" && data.pressed) {rawSignal=data.signature;$("raw-signal").textContent=rawSignal;}
    if(data.type==="control") inputFeedback(data);
    if(data.type==="voice")updateVoice(data);
    if(data.type==="state_changed")scheduleRefresh();
    if(data.type==="error" || data.type==="notice")notice(data.message);
    // Keep transcripts out of the event log.
    if(data.type!=="voice") {eventLines.unshift(JSON.stringify(data));eventLines.length=Math.min(eventLines.length,40);$("events").textContent=eventLines.join("\n");}
  };
  stream.onerror=()=>{$("connection").textContent="连接中断，正在重连…";};
  stream.onopen=()=>scheduleRefresh();
}) ();
