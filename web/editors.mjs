import {actionNames,clone,newAction,validShortcut,shortcutFromEvent,macroToCode,macroFromCode,validateActionDraft} from "/model.mjs";

export function node(tag,className,text) {
  const item=document.createElement(tag);
  if(className)item.className=className;
  if(text!==undefined)item.textContent=text;
  return item;
}
export function button(text,callback,className="") {
  const item=node("button",className,text);item.type="button";item.onclick=callback;return item;
}
export function option(select,value,text) {
  const item=node("option","",text);item.value=value;select.append(item);
}
function field(parent,title,element) {
  const label=node("label");label.append(node("span","",title),element);parent.append(label);return element;
}
function input(value,callback,type="text") {
  const item=node("input");item.type=type;item.value=value ?? "";
  item.onchange=()=>callback(type==="number"?Number(item.value):item.value);
  return item;
}
function select(value,options,callback) {
  const item=node("select");
  for(const [v,label] of options)option(item,v,label);
  item.value=value;item.onchange=()=>callback(item.value);return item;
}
const recorders=new Set();
export function stopRecorders() { for(const stop of [...recorders])stop(); }
export function recordShortcut(control,onResult,onError) {
  stopRecorders();
  control.classList.add("recording");const original=control.textContent;control.textContent="录制中… Esc 取消";
  let timeout;
  function finish() {
    clearTimeout(timeout);window.removeEventListener("keydown",capture,true);
    control.classList.remove("recording");control.textContent=original;recorders.delete(finish);
  }
  function capture(event) {
    event.preventDefault();event.stopImmediatePropagation();
    if(event.code==="Escape"){finish();return;}
    if(event.repeat)return;
    const value=shortcutFromEvent(event);
    if(value){finish();onResult(value);}
    else if(!/^(Control|Shift|Alt|Meta)/.test(event.code))onError("此按键暂不支持，请使用键库中的按键");
  }
  window.addEventListener("keydown",capture,true);recorders.add(finish);
  timeout=setTimeout(finish,20000);
}

// A structured action editor shared by bindings, library items and macro steps.
export function actionFields(parent,action,onChange,context={}) {
  const stack=node("div","field-stack");parent.append(stack);
  const error=message=>context.notice?.(message);
  const commit=patch=>{const next={...clone(action),...patch};delete next.label;delete next.library_id;onChange(next);};
  if(action.type==="shortcut") {
    const row=node("div","field-row");
    const keys=input(action.keys,value=>{
      value=value.toUpperCase().trim();
      if(!validShortcut(value)){error("无效的快捷键，请使用 CTRL+SHIFT+A 等格式");keys.value=action.keys;return;}
      commit({keys:value});
    });
    keys.setAttribute("aria-label","快捷键");row.append(keys);
    const record=button("录制",()=>recordShortcut(record,value=>commit({keys:value}),error));
    record.setAttribute("aria-label","录制快捷键");row.append(record);stack.append(row);
  } else if(["text","shell"].includes(action.type)) {
    const value=node("textarea");value.rows=3;value.value=action.value || "";
    value.onchange=()=>commit({value:value.value});
    field(stack,action.type==="text"?"要输入的文本":"Shell 命令",value);
  } else if(action.type==="application") {
    field(stack,"可执行文件",input(action.argv?.[0] || "",value=>commit({argv:[value,...(action.argv || []).slice(1)]})));
    const args=node("textarea");args.rows=2;args.placeholder="每行一个参数，不经过 Shell";args.value=(action.argv || []).slice(1).join("\n");
    args.onchange=()=>commit({argv:[action.argv?.[0] || "",...args.value.split("\n").filter(Boolean)]});
    field(stack,"参数（每行一个）",args);
    field(stack,"X11 窗口类（可选）",input(action.wm_class || "",wm_class=>commit({wm_class})));
    stack.append(node("p","muted","启动命令退出后继续宏步骤；需要复用时请加入 APP 库。"));
  } else if(action.type==="volume") {
    field(stack,"音量操作",select(action.operation,[["up","增大音量"],["down","减小音量"],["mute","切换静音"]],operation=>commit({operation})));
  } else if(["layer","momentary_layer"].includes(action.type)) {
    field(stack,"目标层",select(String(action.index),[0,1,2,3].map(i=>[String(i),"Layer "+i]),index=>commit({index:Number(index)})));
  } else if(action.type==="profile") {
    field(stack,"目标方案",select(action.id,Object.entries(context.config.profiles).map(([id,p])=>[id,p.name]),id=>commit({id})));
  } else if(action.type==="voice") {
    const operations=[["ptt","按住说话"],["confirm","确认文本"],["cancel","取消转写"]].filter(([op])=>op!=="ptt" || !context.rotation);
    field(stack,"语音操作",select(action.operation,operations,operation=>commit({operation})));
  } else if(action.type==="macro") {
    stack.append(node("p","muted",`${action.steps.length} 个步骤 · 依次执行`));
    const preview=node("ol","macro-preview");
    for(const step of action.steps.slice(0,5))preview.append(node("li","","delay_ms" in step?`等待 ${step.delay_ms} ms`:step.keys || step.label || actionNames[step.type]));
    stack.append(preview,button("编辑宏步骤",()=>context.editMacro?.(action)));
  } else if(action.type==="inherit") {
    stack.append(node("p","muted","继承较低层的同一手势；显式无动作会阻止继承。"));
  } else stack.append(node("p","muted","此手势不执行动作。"));
  return stack;
}

export function macroEditor(parent,initial,onChange,context) {
  let steps=clone(initial), codeMode=false, recording=false, recordDelays=true,lastTime=null,codeText="";
  const root=node("div");parent.append(root);
  const announce=()=>onChange(clone(steps));
  const append=step=>{
    if(steps.length>=100){context.notice("宏最多 100 步");return;}
    steps.push(step);announce();render();
  };
  let recordingHandler,finishRecording;
  function render() {
    root.replaceChildren();
    const tabs=node("div","macro-code-tabs");
    tabs.append(button("可视化",()=>{
      if(codeMode) {
        try{steps=macroFromCode(codeText);announce();}
        catch(error){context.notice(error.message);return;}
      }
      codeMode=false;render();
    },!codeMode?"current":""),button("Code",()=>{codeText=macroToCode(steps);codeMode=true;render();},codeMode?"current":""));
    if(recording)for(const tab of tabs.children)tab.disabled=true;
    root.append(tabs);
    if(codeMode) {
      const code=node("textarea","code-editor");code.value=codeText;
      code.oninput=()=>{codeText=code.value;};
      root.append(code,node("p","muted","支持 tap_code16(LCTL(KC_C));、wait_ms(500);。其他动作使用 VIBEKEY_ACTION(JSON);。"));
      root.append(button("校验并应用代码",()=>{
        try{steps=macroFromCode(codeText);announce();context.notice("宏代码已通过解析并应用");}
        catch(error){context.notice(error.message);}
      }));
      return;
    }
    const toolbar=node("div","macro-toolbar");
    const record=button(recording?"停止录制":"录制宏",()=>{
      if(recording){finishRecording?.();return;}
      stopRecorders();recording=true;lastTime=null;render();
      finishRecording=()=>{
        recording=false;recorders.delete(finishRecording);
        window.removeEventListener("keydown",recordingHandler,true);render();
      };
      recordingHandler=event=>{
        event.preventDefault();event.stopImmediatePropagation();
        if(event.code==="Escape"){finishRecording();return;}
        if(event.repeat)return;
        const keys=shortcutFromEvent(event);if(!keys)return;
        const now=performance.now(),delay=lastTime===null?0:Math.min(30000,Math.round(now-lastTime));
        if(steps.length+(recordDelays&&delay>30?2:1)>100){finishRecording();context.notice("宏已达到 100 步");return;}
        if(recordDelays&&delay>30)steps.push({delay_ms:delay});
        steps.push({type:"shortcut",keys});lastTime=now;announce();render();
      };
      window.addEventListener("keydown",recordingHandler,true);recorders.add(finishRecording);
    },recording?"record-button recording":"");
    toolbar.append(record);
    const timing=node("label","check"),checkbox=node("input");checkbox.type="checkbox";checkbox.checked=recordDelays;checkbox.onchange=()=>recordDelays=checkbox.checked;
    timing.append(checkbox,node("span","","记录间隔"));toolbar.append(timing,node("span","muted",steps.length+" / 100 步"));root.append(toolbar);
    if(recording)root.append(node("div","record-focus","依次按下组合键，点击停止或按 Esc 结束。录制期间仅记录当前页面的键盘输入。"));
    const list=node("div","macro-steps");root.append(list);
    if(!steps.length)list.append(node("p","empty-note","暂无步骤。添加按键、APP 或等待，也可以直接录制。"));
    steps.forEach((step,index)=>{
      const row=node("div","macro-step");row.append(node("span","step-number",String(index+1)));
      const editor=node("div");row.append(editor);
      if("delay_ms" in step) {
        const delay=input(step.delay_ms,value=>{
          if(!Number.isInteger(value)||value<0||value>30000){context.notice("等待时间为 0–30000 ms");return;}
          steps[index]={delay_ms:value};announce();
        },"number");delay.min="0";delay.max="30000";field(editor,"等待（毫秒）",delay);
      } else {
        const options=["shortcut","application","text","volume","shell","layer","profile"].map(type=>[type,actionNames[type]]);
        const kind=select(step.type,options,type=>{steps[index]=newAction(type);announce();render();});field(editor,"步骤类型",kind);
        actionFields(editor,step,value=>{steps[index]=value;announce();render();},{...context,editMacro:undefined});
        if(step.type==="application" && context.library?.applications?.length) {
          const apps=select("",[["","从 APP 库填入"],...context.library.applications.map(item=>[item.id,item.name])],id=>{
            const item=context.library.applications.find(item=>item.id===id);
            if(item){steps[index]={...clone(item.action),label:item.name,library_id:item.id};announce();render();}
          });editor.prepend(apps);
        }
      }
      const actions=node("div","step-controls");
      const move=direction=>{
        const target=index+direction;if(target<0||target>=steps.length)return;
        [steps[index],steps[target]]=[steps[target],steps[index]];announce();render();
      };
      const up=button("↑",()=>move(-1));up.disabled=index===0;up.setAttribute("aria-label","上移步骤 "+(index+1));
      const down=button("↓",()=>move(1));down.disabled=index===steps.length-1;down.setAttribute("aria-label","下移步骤 "+(index+1));
      const remove=button("×",()=>{steps.splice(index,1);announce();render();},"danger");remove.setAttribute("aria-label","删除步骤 "+(index+1));
      actions.append(up,down,remove);row.append(actions);list.append(row);
    });
    const add=node("div","inline-actions");
    add.append(button("＋ 组合键",()=>append({type:"shortcut",keys:"CTRL+C"})),button("＋ APP",()=>append({type:"application",argv:[""]})),button("＋ 等待",()=>append({delay_ms:500})));
    root.append(add);
    if(recording)for(const item of [...list.querySelectorAll("button,input,select,textarea"),...add.children])item.disabled=true;
  }
  render();
  return {getSteps:()=>{if(codeMode)steps=macroFromCode(codeText);validateActionDraft({type:"macro",steps});return clone(steps);}};
}
