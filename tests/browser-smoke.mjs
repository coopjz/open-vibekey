// Optional integration test: Node 22+ and a locally installed Chrome.
// Runs against an isolated simulated daemon; never grabs or injects real input.
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm, mkdir, writeFile} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join, resolve} from "node:path";
import {setTimeout as delay} from "node:timers/promises";

const directory = await mkdtemp(join(tmpdir(), "vibekey-ui-test-"));
const children = [];
let socket;
const errors = [];
async function until(fn, description, attempts=150) {
  for (let i=0; i<attempts; i++) {
    try { const result=await fn(); if(result) return result; } catch {}
    await delay(100);
  }
  throw new Error("Timed out: "+description);
}
function child(command, args) {
  const process=spawn(command,args,{cwd:resolve("."),stdio:["ignore","pipe","pipe"]});
  children.push(process);
  let stderr="";
  process.stderr.on("data",data=>{stderr=(stderr+data).slice(-8000);});
  process.on("error",error=>errors.push(error.message));
  process.stderrText=()=>stderr;
  return process;
}
try {
  const daemon=child(process.env.PYTHON || "/usr/bin/python3",
    ["-m","vibekey","--simulate","--port","0","--config",join(directory,"config.json")]);
  let output="";
  daemon.stdout.on("data",data=>{output+=data;});
  const port=await until(()=>output.match(/127\.0\.0\.1:(\d+)/)?.[1],"simulated daemon startup");
  const origin="http://127.0.0.1:"+port;
  const browser=child(process.env.CHROME || "/usr/bin/google-chrome",
    ["--headless=new","--disable-gpu","--disable-dev-shm-usage","--no-first-run",
      "--no-default-browser-check","--remote-debugging-port=0",
      "--user-data-dir="+join(directory,"chrome"),"about:blank"]);
  const debugPort=await until(async()=>(await readFile(join(directory,"chrome","DevToolsActivePort"),"utf8")).split("\n")[0],
    "Chrome debugging endpoint");
  const pages=await (await fetch("http://127.0.0.1:"+debugPort+"/json")).json();
  socket=new WebSocket(pages.find(page=>page.type==="page").webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let nextId=0;
  const pending=new Map(), exceptions=[];
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    if(message.method==="Runtime.exceptionThrown") exceptions.push(message.params.exceptionDetails);
    if(message.id) {
      const pair=pending.get(message.id);
      pending.delete(message.id);
      if(message.error) pair.reject(new Error(JSON.stringify(message.error)));
      else pair.resolve(message.result);
    }
  };
  function cdp(method,params={}) {
    return new Promise((resolve,reject)=>{
      const id=++nextId;
      pending.set(id,{resolve,reject});
      socket.send(JSON.stringify({id,method,params}));
    });
  }
  async function evaluate(expression) {
    const result=await cdp("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});
    if(result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride",{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
  await cdp("Page.navigate",{url:origin});
  await until(()=>evaluate('document.getElementById("connection")?.textContent.includes("模拟模式")'),
    "UI initialization");
  assert.match(await evaluate('document.getElementById("dirty").textContent'),/配置已加载/);
  // Paired rotation settings must persist without touching the voice/button bindings.
  const beforeRotation=await (await fetch(origin+"/api/config")).json();
  for(const [mode,cw,ccw] of [["terminator-panes","CTRL+SHIFT+N","CTRL+SHIFT+P"],["terminal-tabs","CTRL+PAGEDOWN","CTRL+PAGEUP"]]) {
    await evaluate(`(()=>{
      const select=document.getElementById("rotation-mode");
      select.value=${JSON.stringify(mode)};select.dispatchEvent(new Event("change"));
      document.getElementById("save").click();
    })()`);
    await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"rotation save").catch(async error=>{
      console.error(await evaluate('JSON.stringify({notice:document.getElementById("notice").textContent,dirty:document.getElementById("dirty").textContent,mode:document.getElementById("rotation-mode").value})'));
      throw error;
    });
    const persisted=await (await fetch(origin+"/api/config")).json();
    const bindings=persisted.profiles.default.layers[0].bindings;
    assert.equal(bindings.cw.single.keys,cw);assert.equal(bindings.ccw.single.keys,ccw);
    assert.deepEqual(bindings.top,beforeRotation.profiles.default.layers[0].bindings.top);
    await cdp("Page.reload");
    await until(()=>evaluate('document.getElementById("dirty")?.textContent==="配置已加载" && document.getElementById("connection")?.textContent.includes("模拟模式") && document.getElementById("rotation-mode")?.value==='+JSON.stringify(mode)),"rotation reload");
  }
  // Exercise the real binding editor, persistence, and simulated event stream.
  await evaluate(`(()=>{
    const select=document.querySelector("#bindings select");
    select.value="shortcut";select.dispatchEvent(new Event("change"));
    const edit=document.querySelector('#bindings input[aria-label="快捷键"]');
    edit.value="CTRL+SHIFT+T";
    edit.dispatchEvent(new Event("change"));
    document.getElementById("save").click();
  })()`);
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"configuration save");
  const config=await (await fetch(origin+"/api/config")).json();
  assert.equal(config.profiles.default.layers[0].bindings.top.single.keys,"CTRL+SHIFT+T");
  const {token}=await (await fetch(origin+"/api/state")).json();
  for (const pressed of [true,false]) {
    const response=await fetch(origin+"/api/simulate",{method:"POST",headers:{
      "Content-Type":"application/json","X-VibeKey-Token":token
    },body:JSON.stringify({control:"top",pressed})});
    assert.equal(response.status,200);
  }
  await until(()=>evaluate('document.getElementById("events").textContent.includes("simulated_action")'),
    "SSE action feedback");
  // Editing selection must not mask a change in physical rotation direction.
  await evaluate('document.querySelector(\'[data-control="cw"]\').click()');
  for (const [control,count] of [["cw",10],["ccw",5]]) {
    for (let index=0;index<count;index++) {
      const response=await fetch(origin+"/api/simulate",{method:"POST",headers:{
        "Content-Type":"application/json","X-VibeKey-Token":token
      },body:JSON.stringify({control,pressed:true})});
      assert.equal(response.status,200);
    }
  }
  await until(()=>evaluate('document.getElementById("ccw-count").textContent==="5"'),
    "rotation direction feedback");
  assert.equal(await evaluate('document.getElementById("cw-count").textContent'),"10");
  assert.match(await evaluate('document.getElementById("last-input").textContent'),/逆时针/);
  assert.equal(await evaluate('document.querySelector(\'[data-control="cw"]\').classList.contains("selected")'),true);
  await evaluate('document.getElementById("reset-input").click()');
  assert.equal(await evaluate('document.getElementById("cw-count").textContent'),"0");
  assert.equal(await evaluate('document.getElementById("ccw-count").textContent'),"0");
  // Select a gesture from the overview, assign a key, and set repeat output.
  await evaluate(`(()=>{
    document.querySelector('[data-gesture-control="knob"][data-gesture="double"]').click();
    document.querySelector('[data-category="字符"]').click();
    document.querySelector('[data-key="A"]').click();
    const repeat=document.querySelector('[aria-label="重复次数"]');
    repeat.value="3";repeat.dispatchEvent(new Event("change"));
  })()`);
  assert.equal(await evaluate('document.getElementById("gesture-title").textContent'),"双击");
  await evaluate('document.getElementById("save").click()');
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"repeated shortcut save");
  let saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.profiles.default.layers[0].bindings.knob.double.repeat,3);
  // Native keyboard recording is scoped to the active recorder.
  await evaluate(`document.querySelector('#bindings button[aria-label="录制快捷键"]').click()`);
  await cdp("Input.dispatchKeyEvent",{type:"keyDown",key:"k",code:"KeyK",modifiers:2});
  await cdp("Input.dispatchKeyEvent",{type:"keyUp",key:"k",code:"KeyK",modifiers:2});
  assert.equal(await evaluate('document.querySelector(\'#bindings input[aria-label="快捷键"]\').value'),"CTRL+K");
  // Create an application library entry through the actual dialog, then assign.
  await evaluate(`(()=>{
    document.querySelector('[data-category="APP"]').click();
    [...document.querySelectorAll("#palette-content button")].find(b=>b.textContent.includes("添加 APP")).click();
  })()`);
  await until(()=>evaluate('document.querySelector("#library-editor .field-stack input")!==null'),"application editor");
  await evaluate(`(()=>{
    document.getElementById("library-name").value="Test terminal";
    const executable=document.querySelector("#library-editor .field-stack input");
    executable.value="/usr/bin/true";executable.dispatchEvent(new Event("change"));
    document.getElementById("library-form").requestSubmit();
  })()`);
  await until(()=>evaluate('!document.getElementById("library-dialog").open'),"application library save");
  await evaluate('document.querySelector(".library-assign").click()');
  // Create a macro, reorder its steps, round-trip Code and assign it.
  await evaluate(`(()=>{
    document.querySelector('[data-category="宏"]').click();
    [...document.querySelectorAll("#palette-content button")].find(b=>b.textContent.includes("新建宏")).click();
    document.getElementById("library-name").value="Test macro";
    [...document.querySelectorAll("#library-editor .inline-actions button")].find(b=>b.textContent.includes("组合键")).click();
    [...document.querySelectorAll("#library-editor .inline-actions button")].find(b=>b.textContent.includes("等待")).click();
    document.querySelector('[aria-label="上移步骤 2"]').click();
    [...document.querySelectorAll(".macro-code-tabs button")].find(b=>b.textContent==="Code").click();
  })()`);
  assert.match(await evaluate('document.querySelector(".code-editor").value'),/^wait_ms\(500\);/);
  await evaluate(`(()=>{
    [...document.querySelectorAll(".macro-code-tabs button")].find(b=>b.textContent==="可视化").click();
    document.getElementById("library-form").requestSubmit();
  })()`);
  await until(()=>evaluate('!document.getElementById("library-dialog").open'),"macro library save");
  await evaluate('document.querySelector(".library-assign").click()');
  await evaluate('document.getElementById("save").click()');
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"library persistence");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.library.applications[0].name,"Test terminal");
  assert.equal(saved.library.macros[0].action.steps[0].delay_ms,500);
  assert.equal(saved.profiles.default.layers[0].bindings.knob.double.type,"macro");
  // Save a layer inheritance action without activating it.
  await evaluate(`(()=>{
    document.querySelector('#layer-tabs [aria-label="Layer 1"]').click();
    document.querySelector('[data-gesture-control="top"][data-gesture="single"]').click();
    document.querySelector('[data-category="其他"]').click();
    document.querySelector('[data-key="▽"]').click();
    document.getElementById("save").click();
  })()`);
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"inheritance save");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.active_layer,0);
  assert.equal(saved.profiles.default.layers[1].bindings.top.single.type,"inherit");
  assert.equal(await evaluate('document.getElementById("activation-warning").hidden'),false);
  assert.equal(await evaluate('document.getElementById("activate").classList.contains("primary")'),true);
  assert.match(await evaluate('document.getElementById("activation-warning").textContent'),/设备仍使用/);
  // Switching UI language must preserve the editor and its unsaved draft.
  await evaluate(`(()=>{
    document.querySelector('[data-key="文本"]').click();
    const value=document.querySelector("#bindings textarea");
    value.value="draft survives language switch";value.dispatchEvent(new Event("change"));
    document.querySelector('[data-page="settings"]').click();
    const language=document.getElementById("language");
    language.value="en";language.dispatchEvent(new Event("change"));
  })()`);
  await until(()=>evaluate('document.documentElement.lang==="en" && document.querySelector(\'[data-page="workspace"]\').textContent.includes("Keymap")'),"English interface");
  await evaluate('document.querySelector(\'[data-page="workspace"]\').click()');
  assert.equal(await evaluate('document.querySelector("#bindings textarea").value'),"draft survives language switch");
  await evaluate(`(()=>{
    document.querySelector('[data-page="settings"]').click();
    const language=document.getElementById("language");
    language.value="zh";language.dispatchEvent(new Event("change"));
    document.querySelector('[data-page="workspace"]').click();
  })()`);
  await until(()=>evaluate('document.documentElement.lang==="zh-CN" && document.querySelector(\'[data-page="workspace"]\').textContent.includes("键位")'),"Chinese interface");
  assert.equal(await evaluate('document.querySelector("#bindings textarea").value'),"draft survives language switch");
  // Verify the new URL editor, persistence, and packaged device illustration.
  const image=await fetch(origin+"/assets/studio/vibekey.png");
  assert.equal(image.status,200);
  assert.equal((await image.arrayBuffer()).byteLength,180751);
  await evaluate(`(()=>{
    document.querySelector('[data-key="打开网站"]').click();
    const url=document.querySelector('#bindings input[type="url"]');
    url.value="https://example.com/a?q=one%20two#part";
    url.dispatchEvent(new Event("change"));
    document.getElementById("save").click();
  })()`);
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"website save");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.deepEqual(saved.profiles.default.layers[1].bindings.top.single,
    {type:"website",url:"https://example.com/a?q=one%20two#part"});
  // Collect rendered previews and verify layout on desktop and mobile.
  await mkdir(resolve("dist/previews"),{recursive:true});
  for (const [name,width,height] of [["desktop",1280,1000],["mobile",390,844]]) {
    await cdp("Emulation.setDeviceMetricsOverride",{width,height,deviceScaleFactor:1,mobile:false});
    await delay(150);
    assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,name+" horizontal overflow");
    const shot=await cdp("Page.captureScreenshot",{format:"png",captureBeyondViewport:true});
    await writeFile(resolve("dist/previews/workspace-"+name+".png"),Buffer.from(shot.data,"base64"));
    for (const page of ["voice","settings"]) {
      await evaluate(`document.querySelector('[data-page="${page}"]').click()`);
      assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,name+" "+page+" horizontal overflow");
      const settingsShot=await cdp("Page.captureScreenshot",{format:"png",captureBeyondViewport:true});
      await writeFile(resolve("dist/previews/"+page+"-"+name+".png"),Buffer.from(settingsShot.data,"base64"));
    }
    await evaluate('document.querySelector(\'[data-page="workspace"]\').click()');
  }
  // vinput uses a held Right Alt preset on physical buttons only.
  await evaluate(`document.querySelector('[data-key="fcitx5-vinput"]').click()`);
  assert.equal(await evaluate('document.querySelector("#bindings input").value'),"RIGHTALT");
  await evaluate('document.getElementById("save").click()');
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"vinput preset save");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.deepEqual(saved.profiles.default.layers[1].bindings.top.single,
    {type:"shortcut",keys:"RIGHTALT",mode:"hold",label:"fcitx5-vinput"});
  // Official templates create editable drafts without activating or replacing existing work.
  await evaluate(`document.querySelector('[data-page="settings"]').click()`);
  assert.equal(await evaluate('document.querySelectorAll(".preset-card").length'),5);
  assert.equal(await evaluate('document.getElementById("apply-light").disabled'),true);
  assert.equal(await evaluate('document.getElementById("session")'),null);
  await evaluate(`document.querySelector(".preset-card button").click()`);
  assert.equal(await evaluate('document.getElementById("profile").value'),"workbuddy-default");
  assert.equal(await evaluate('document.getElementById("activation-warning").hidden'),false);
  await evaluate('document.getElementById("save").click()');
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"preset save");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.active_profile,"default");
  assert.deepEqual(saved.profiles["workbuddy-default"].layers[0].bindings.cw.single,{type:"scroll",direction:"down"});
  assert.deepEqual(saved.profiles.default.layers[1].bindings.top.single,{type:"shortcut",keys:"RIGHTALT",mode:"hold",label:"fcitx5-vinput"});
  await evaluate(`(()=>{const select=document.getElementById("profile");select.value="default";select.dispatchEvent(new Event("change"));})()`);
  // CLI setup creates both profiles and stable-role rules without changing the fallback.
  await evaluate(`(()=>{
    document.querySelector('[data-page="settings"]').click();
    document.getElementById("follow-cli").click();
  })()`);
  assert.equal(await evaluate('document.getElementById("follow-enabled").checked'),true);
  assert.equal(await evaluate('document.querySelectorAll(".follow-rule").length'),2);
  await evaluate('document.getElementById("save").click()');
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"automatic profiles save");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.auto_follow.enabled,true);
  assert.equal(saved.auto_follow.default_profile,"default");
  assert.deepEqual(saved.auto_follow.rules.map(rule=>rule.role),["vibekey-codex","vibekey-claude"]);
  assert.equal(saved.profiles["codex-cli"].layers[0].bindings.knob.single.keys,"CTRL+R");
  assert.equal(saved.profiles["claude-code"].layers[0].bindings.knob.single.keys,"CTRL+O");
  await evaluate('document.getElementById("follow-cli").click()');
  assert.equal(await evaluate('document.querySelectorAll(".follow-rule").length'),2);
  for(const [name,width,height] of [["desktop",1280,1000],["mobile",390,844]]) {
    await cdp("Emulation.setDeviceMetricsOverride",{width,height,deviceScaleFactor:1,mobile:false});
    await evaluate('window.scrollTo(0,0)');await delay(150);
    assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,"follow rules "+name+" overflow");
    const screenshot=await cdp("Page.captureScreenshot",{format:"png",captureBeyondViewport:true});
    await writeFile(resolve("dist/previews/settings-follow-"+name+".png"),Buffer.from(screenshot.data,"base64"));
  }
  // Per-rule profile edits and priority controls survive persistence.
  await evaluate(`(()=>{
    const profile=document.querySelector('.follow-rule [data-rule-field="profile"]');
    profile.value="claude-code";profile.dispatchEvent(new Event("change"));
    document.getElementById("save").click();
  })()`);
  await until(()=>evaluate('document.getElementById("dirty").textContent==="已保存"'),"follow rule edit save");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.auto_follow.rules[0].profile,"claude-code");
  await evaluate('document.getElementById("activate").click()');
  await until(async()=>!(await (await fetch(origin+"/api/config")).json()).auto_follow.enabled,"manual activation disables automatic switching");
  // Malformed imports must leave the current editor usable.
  await evaluate(`(()=>{
    document.getElementById("config-json").value=JSON.stringify({
      version:1,active_profile:"bad",profiles:{bad:{name:"Broken",layers:[]}}
    });
    document.getElementById("apply-json").click();
  })()`);
  await until(()=>evaluate('document.getElementById("notice").textContent.includes("配置字段不完整")'),
    "malformed import feedback");
  assert.equal(await evaluate('document.getElementById("profile").value'),"default");
  // The first page exposes direct preset activation and an immediate follow switch.
  await evaluate(`document.querySelector('[data-page="workspace"]').click()`);
  assert.equal(await evaluate('document.querySelectorAll("#scene-presets [data-scene-preset]").length'),6);
  assert.equal(await evaluate(`document.querySelector('[data-scene-preset="default"]').getAttribute("aria-pressed")`),"true");
  await evaluate('document.getElementById("home-follow-enabled").click()');
  await until(async()=>(await (await fetch(origin+"/api/config")).json()).auto_follow.enabled,"home follow switch persistence");
  await until(()=>evaluate('!document.querySelector(".scene-preset").disabled'),"home follow change completed");
  assert.equal(await evaluate('document.getElementById("home-follow-state").textContent'),"已开启");
  assert.equal(await evaluate('document.getElementById("follow-enabled").checked'),true);
  await evaluate('document.getElementById("home-follow-details").click()');
  assert.equal(await evaluate('document.getElementById("settings").hidden'),false);
  assert.equal(await evaluate('document.activeElement.id'),"follow-settings");
  await evaluate(`document.querySelector('[data-page="workspace"]').click()`);
  await evaluate(`document.querySelector('[data-scene-preset="codex-cli"]').click()`);
  await until(async()=>{
    const config=await (await fetch(origin+"/api/config")).json();
    return config.active_profile==="codex-cli"&&!config.auto_follow.enabled;
  },"home preset activation disables following");
  await until(()=>evaluate(`document.querySelector('[data-scene-preset="codex-cli"]').getAttribute("aria-pressed")==="true"`),"home active preset highlight");
  assert.equal(await evaluate('document.getElementById("profile").value'),"codex-cli");
  assert.equal(await evaluate('document.getElementById("home-follow-enabled").checked'),false);
  assert.equal(await evaluate('document.getElementById("follow-enabled").checked'),false);
  saved=await (await fetch(origin+"/api/config")).json();
  assert.deepEqual(saved.profiles.default.layers[1].bindings.top.single,{type:"shortcut",keys:"RIGHTALT",mode:"hold",label:"fcitx5-vinput"});
  await until(()=>evaluate('!document.querySelector(".scene-preset").disabled'),"home preset change completed");
  // An uninstalled scene is created with the current voice binding and immediately activated.
  await evaluate(`document.querySelector('[data-scene-preset="workbuddy-dispatch"]').click()`);
  await until(async()=>(await (await fetch(origin+"/api/config")).json()).active_profile==="workbuddy-dispatch","home creates and activates a missing preset");
  await until(()=>evaluate('document.getElementById("profile").value==="workbuddy-dispatch" && !document.querySelector(".scene-preset").disabled'),"home switch completion");
  saved=await (await fetch(origin+"/api/config")).json();
  assert.equal(saved.profiles["workbuddy-dispatch"].layers[0].bindings.top.single.keys,saved.profiles["codex-cli"].layers[0].bindings.top.single.keys);
  await evaluate(`document.querySelector('[data-scene-preset="default"]').click()`);
  await until(()=>evaluate(`document.querySelector('[data-scene-preset="default"]').getAttribute("aria-pressed")==="true"`),"home default selection");
  // A rejected save restores the previous selection and leaves the quick controls usable.
  await until(()=>evaluate('!document.querySelector(".scene-preset").disabled'),"home default save completion");
  await evaluate(`(()=>{
    const original=window.fetch;
    window.fetch=(url,options)=>{
      if(url==="/api/config"&&options?.method==="PUT"){
        window.fetch=original;
        return Promise.resolve(new Response(JSON.stringify({error:"测试保存失败"}),{status:400}));
      }
      return original(url,options);
    };
    document.querySelector('[data-scene-preset="claude-code"]').click();
  })()`);
  await until(()=>evaluate('document.getElementById("notice").textContent==="测试保存失败"'),"home save failure feedback");
  assert.equal(await evaluate('document.getElementById("profile").value'),"default");
  assert.equal(await evaluate(`document.querySelector('[data-scene-preset="default"]').getAttribute("aria-pressed")`),"true");
  assert.equal(await evaluate('document.querySelector(".scene-preset").disabled'),false);
  assert.equal((await (await fetch(origin+"/api/config")).json()).active_profile,"default");
  await evaluate('document.getElementById("notice").hidden=true');
  for(const [name,width,height] of [["desktop",1280,1000],["mobile",390,844]]) {
    await cdp("Emulation.setDeviceMetricsOverride",{width,height,deviceScaleFactor:1,mobile:false});
    await evaluate('window.scrollTo(0,0)');await delay(150);
    assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,"scene selection "+name+" overflow");
    const screenshot=await cdp("Page.captureScreenshot",{format:"png",captureBeyondViewport:true});
    await writeFile(resolve("dist/previews/workspace-scenes-"+name+".png"),Buffer.from(screenshot.data,"base64"));
  }
  // Callouts and physical hit areas must share their vertical centres at every breakpoint.
  for(const width of [1450,1280,1000,760,600,430,390,340]) {
    await cdp("Emulation.setDeviceMetricsOverride",{width,height:1000,deviceScaleFactor:1,mobile:false});
    await delay(60);
    const layout=await evaluate(`(()=>{
      const rect=selector=>document.querySelector(selector).getBoundingClientRect();
      const centre=r=>r.y+r.height/2;
      const errors=["top","middle","bottom"].map(control=>Math.abs(centre(rect('[data-matrix="'+control+'"]'))-centre(rect('.physical.key-'+control))));
      errors.push(Math.abs(centre(rect('[data-matrix="knob"]'))-centre(rect('.physical.dial'))));
      const matrices=["top","middle","bottom"].map(control=>rect('[data-matrix="'+control+'"]'));
      return {errors,overlap:matrices.some((r,i)=>i>0&&r.top<matrices[i-1].bottom),overflow:document.documentElement.scrollWidth>innerWidth};
    })()`);
    assert.equal(layout.overflow,false,"workbench overflow at "+width);
    assert.equal(layout.overlap,false,"overlapping key callouts at "+width);
    assert.ok(layout.errors.every(error=>error<1.5),"key alignment at "+width+": "+JSON.stringify(layout.errors));
  }
  assert.deepEqual(exceptions,[]);
  assert.deepEqual(errors,[]);
  console.log("Browser smoke passed: device/callout alignment at eight viewport widths, structured editor, key recorder, gesture overview, repeat, APP/macro library, macro Code/reordering, layers, persistence, SSE, rotation reversal, import recovery, responsive layout");
  if(browser.exitCode!==null) throw new Error(browser.stderrText());
} catch(error) {
  for(const process of children) console.error(process.stderrText());
  throw error;
} finally {
  socket?.close();
  for(const process of children.reverse()) {
    if(process.exitCode===null) {
      process.kill("SIGTERM");
      await Promise.race([new Promise(resolve=>process.once("exit",resolve)),delay(4000)]);
      if(process.exitCode===null) process.kill("SIGKILL");
    }
  }
  await rm(directory,{recursive:true,force:true,maxRetries:10,retryDelay:100});
}
