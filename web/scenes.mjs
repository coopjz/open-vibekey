import {node,button} from "/editors.mjs";

export function sceneOverview({getConfig,getState,getCapabilities,getCatalog,onSelect,onFollow,onDetails}) {
  const $=id=>document.getElementById(id);
  let busy=false, signature="";
  function entries() {
    const config=getConfig(), catalog=getCatalog(), active=getState()?.active_profile || config.active_profile;
    const ids=new Set([config.auto_follow.default_profile,...Object.keys(catalog),active]);
    return [...ids].map(id=>[id,config.profiles[id] || catalog[id]?.profile]).filter(([,profile])=>profile);
  }
  function render() {
    const config=getConfig(), catalog=getCatalog(), items=entries();
    signature=JSON.stringify(items.map(([id,profile])=>[id,profile.name]));
    $("scene-presets").replaceChildren();
    for(const [id,profile] of items) {
      const card=button("",()=>onSelect(id),"scene-preset");card.dataset.scenePreset=id;
      card.setAttribute("aria-label","启用预设："+profile.name);
      const symbol=id==="codex-cli"?">_":id==="claude-code"?"✳":id===config.auto_follow.default_profile?"⌂":id.endsWith("default")?"◉":id.endsWith("dispatch")?"↗":"▤";
      const copy=node("span","scene-copy");
      copy.append(node("strong","",profile.name),node("small","",catalog[id]?.description || (id===config.auto_follow.default_profile?"默认回退方案":"自定义方案")));
      const check=node("span","scene-check","✓");check.setAttribute("aria-hidden","true");
      card.append(node("span","scene-symbol",symbol),copy,check);$("scene-presets").append(card);
    }
    update();
  }
  function update() {
    const config=getConfig();if(!config)return;
    if(JSON.stringify(entries().map(([id,profile])=>[id,profile.name]))!==signature){render();return;}
    const state=getState(), active=state?.active_profile || config.active_profile;
    for(const card of $("scene-presets").children) {
      const selected=card.dataset.scenePreset===active;
      card.classList.toggle("current",selected);card.setAttribute("aria-pressed",String(selected));card.disabled=busy;
      card.title=config.auto_follow.enabled?"点击启用并切为手动模式":"点击启用此预设";
    }
    const enabled=config.auto_follow.enabled, capabilities=getCapabilities();
    $("home-follow-enabled").checked=enabled;
    $("home-follow-enabled").disabled=busy||(!enabled&&!capabilities?.auto_follow?.available);
    $("home-follow-state").textContent=enabled?"已开启":"已关闭";
    $("home-follow-summary").textContent=enabled?
      (state?.auto_follow?.error || "未匹配时使用："+config.profiles[config.auto_follow.default_profile].name):"手动选择场景预设";
    $("home-follow-state").classList.toggle("enabled",enabled);
  }
  $("home-follow-enabled").onchange=()=>onFollow($("home-follow-enabled").checked);
  $("home-follow-details").onclick=onDetails;
  return {render,update,setBusy(value){busy=value;update();}};
}
