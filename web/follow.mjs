import {node,button,option} from "/editors.mjs";

export function followEditor({getConfig,getProfile,changed,api,guarded,installCli}) {
  const $=id=>document.getElementById(id);
  let openWindows=[];
  const settings=()=>getConfig().auto_follow;
  function profiles(select,value) {
    for(const [id,profile] of Object.entries(getConfig().profiles))option(select,id,profile.name);
    select.value=value;
  }
  function render() {
    const follow=settings();
    $("follow-enabled").checked=follow.enabled;
    $("follow-default").replaceChildren();profiles($("follow-default"),follow.default_profile);
    $("follow-default-layer").value=String(follow.default_layer);
    $("follow-rules").replaceChildren();
    follow.rules.forEach((rule,index)=>{
      const card=node("article","follow-rule"),head=node("div","card-heading"),fields=node("div","form-grid");
      head.append(node("strong","",String(index+1).padStart(2,"0")));
      const actions=node("div","follow-row-actions");
      for(const [label,offset] of [["↑",-1],["↓",1]]) {
        const move=button(label,()=>{[follow.rules[index],follow.rules[index+offset]]=[follow.rules[index+offset],follow.rules[index]];changed();render();},"subtle");
        move.disabled=index+offset<0||index+offset>=follow.rules.length;
        move.setAttribute("aria-label",offset<0?"上移规则":"下移规则");actions.append(move);
      }
      actions.append(button("删除",()=>{follow.rules.splice(index,1);changed();render();},"subtle danger"));head.append(actions);card.append(head);
      const field=(label,control)=>{const wrapper=node("label");wrapper.append(node("span","",label),control);fields.append(wrapper);};
      for(const [key,label] of [["name","应用名称"],["wm_class","窗口类别"],["title","标题包含"],["role","窗口标识（可选）"]]) {
        const input=node("input");input.value=rule[key];input.maxLength=512;input.dataset.ruleField=key;
        input.oninput=()=>{rule[key]=input.value;changed();};field(label,input);
      }
      const profile=node("select");profiles(profile,rule.profile);profile.dataset.ruleField="profile";
      profile.onchange=()=>{rule.profile=profile.value;changed();};field("使用方案",profile);
      const layer=node("select");for(let i=0;i<4;i++)option(layer,String(i),"Layer "+i);
      layer.value=String(rule.layer);layer.onchange=()=>{rule.layer=Number(layer.value);changed();};field("使用层",layer);
      card.append(fields);$("follow-rules").append(card);
    });
    $("follow-empty").hidden=follow.rules.length>0;
  }
  function addRule(window={}) {
    const follow=settings();if(follow.rules.length>=64)throw new Error("最多 64 条应用绑定");
    follow.rules.push({id:"app-"+Date.now().toString(36)+"-"+follow.rules.length,
      name:window.title || "应用",wm_class:window.wm_class || "",title:"",role:window.role || "",
      profile:getProfile(),layer:0});changed();render();
  }
  $("follow-enabled").onchange=()=>{settings().enabled=$("follow-enabled").checked;changed();};
  $("follow-default").onchange=()=>{settings().default_profile=$("follow-default").value;changed();};
  $("follow-default-layer").onchange=()=>{settings().default_layer=Number($("follow-default-layer").value);changed();};
  $("follow-add").onclick=guarded(()=>addRule());
  $("follow-refresh").onclick=guarded(async()=>{
    openWindows=(await api("/api/windows")).windows;
    $("follow-window").replaceChildren();option($("follow-window"),"","选择已打开的应用窗口");
    openWindows.forEach((window,index)=>option($("follow-window"),String(index),`${window.title || window.wm_class} · ${window.wm_class}`));
  });
  $("follow-bind").onclick=guarded(()=>{
    const value=$("follow-window").value;
    if(value===""||!openWindows[Number(value)])throw new Error("先刷新并选择一个应用窗口");
    addRule(openWindows[Number(value)]);
  });
  $("follow-cli").onclick=guarded(()=>{installCli();render();});
  for(const tool of ["codex","claude"])$("launch-"+tool).onclick=guarded(()=>api("/api/cli/launch",{tool}));
  function status(state,capabilities) {
    const follow=state.auto_follow;
    $("follow-status").textContent=follow?.enabled?(follow.error || (follow.rule?"已匹配应用方案":"使用默认方案")):"已关闭";
    $("follow-current").textContent=follow?.window?.title || "前台应用切换时自动更新";
    $("follow-enabled").disabled=!capabilities.auto_follow?.available&&!settings().enabled;
    $("follow-availability").textContent=capabilities.auto_follow?.reason || "";
  }
  return {render,status};
}
