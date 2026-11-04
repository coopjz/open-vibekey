// UI language is a browser preference; configuration drafts remain untouched.
const english = {
  "键位":"Keymap","语音":"Voice","设置":"Settings","连接中":"Connecting",
  "电量未知":"Battery unknown","AU05 已连接":"AU05 connected","等待设备":"Waiting for device",
  "● 模拟模式":"● Simulation","● AU05 已连接":"● AU05 connected","○ 等待设备":"○ Waiting for device",
  "预览 / 学习模式":"Preview / learn","旋钮按下":"Knob press","上键":"Top key",
  "中键":"Middle key","下键":"Bottom key","单击":"Single","双击":"Double","长按":"Long",
  "顺时针":"Clockwise","逆时针":"Counterclockwise","清零计数":"Reset counts",
  "框选表示正在编辑，闪烁表示实际输入":"Outlined = editing · Flashing = live input",
  "屏幕模拟":"Simulate input","正在编辑":"Editing","转动":"Rotation",
  "动作设置":"Action settings","动作类型":"Action type","未设置":"Unset",
  "无动作":"No action","继承底层":"Inherit","快捷键":"Shortcut",
  "打开网站":"Open website","网站地址（HTTP / HTTPS）":"Website URL (HTTP / HTTPS)",
  "使用 fcitx5-vinput：在键位页选择实体按键的单击槽，再从“其他”选择 fcitx5-vinput，保存后按住说话、松开识别。需先安装并启动 Fcitx5、vinput 和识别模型。结果由输入法提交到当前输入框。":"For fcitx5-vinput, select a physical button’s single slot, choose fcitx5-vinput in Other, and save. Hold to speak and release to recognize. Set up Fcitx5, vinput and an ASR model first. The input method commits text to the focused field.",
  "默认触发键为右 Alt；若已修改 vinput 热键，请同步修改快捷键。下方录音、确认和取消按钮用于内置语音，不控制 vinput。":"The default trigger is Right Alt; match any customized vinput hotkey. The recording, confirm and cancel buttons below control built-in voice only.",
  "本地 / API":"Local / API",
  "输入文本":"Type text","启动应用":"Launch application","音量":"Volume",
  "顺序宏":"Macro","切换层":"Switch layer","切换方案":"Switch profile",
  "按住切层":"Momentary layer","语音":"Voice","语音键":"Voice key",
  "短按一次 / 连按":"Tap / repeat","保持按住":"Hold","次":"times",
  "常用":"Basic","字符":"Characters","功能键":"Function","数字键盘":"Numpad",
  "组合键":"Shortcuts","宏":"Macros","媒体":"Media","其他":"Other",
  "学习设备信号":"Learn device input","映射到当前控件":"Map to selected control",
  "开启预览，操作实物，再将信号映射到当前控件。":"Enable preview, press a physical control, then map its signal.",
  "等待设备信号":"Waiting for input","配置已加载":"Configuration loaded",
  "有未保存的修改":"Unsaved changes","已保存":"Saved",
  "保存到本机":"Save to this computer","保存到本机后生效，关闭网页可继续使用":"Save to activate. The driver keeps running when this page closes.",
  "丢弃修改":"Discard changes","启用此方案与层":"Activate profile & layer",
  "正在编辑的方案":"Profile being edited",
  "搜索按键或动作":"Search keys or actions","录制":"Record","录制快捷键":"Record shortcut",
  "分配组合键":"Assign shortcut","组合键内容":"Shortcut",
  "按下组合键录制，或选择修饰键后输入主键。浏览器可能截获部分系统快捷键，可手动填写。":"Record a shortcut or choose modifiers and enter a key. Some system shortcuts are captured by the browser; enter those manually.",
  "录制中… Esc 取消":"Recording… Esc to cancel","没有匹配的按键":"No matching keys",
  "可执行文件":"Executable","参数（每行一个）":"Arguments (one per line)",
  "X11 窗口类（可选）":"X11 window class (optional)",
  "每行一个参数，不经过 Shell":"One argument per line; no shell",
  "启动命令退出后继续宏步骤；需要复用时请加入 APP 库。":"Macro steps continue after the launcher exits. Add to the APP library to reuse.",
  "要输入的文本":"Text to insert","Shell 命令":"Shell command","音量操作":"Volume operation",
  "增大音量":"Volume up","减小音量":"Volume down","切换静音":"Toggle mute",
  "目标层":"Target layer","目标方案":"Target profile","语音操作":"Voice operation",
  "按住说话":"Push to talk","确认文本":"Confirm text","取消转写":"Cancel transcription",
  "编辑宏步骤":"Edit macro steps","此手势不执行动作。":"No action is assigned to this gesture.",
  "继承较低层的同一手势；显式无动作会阻止继承。":"Inherit the same gesture from lower layers. An explicit no-action blocks inheritance.",
  "＋ 新建宏":"+ New macro","＋ 添加 APP":"+ Add APP","编辑":"Edit","删除":"Delete",
  "暂无宏 · 录制或编排一组操作，再分配给任意控件":"No macros yet. Record or compose a sequence, then assign it to a control.",
  "暂无 APP · 从已安装应用中选择，或填写启动命令":"No apps yet. Choose an installed application or enter a launch command.",
  "从当前动作创建":"Create from current action",
  "点击动作卡片分配；编辑库动作会同步更新其所有绑定，保存到本机后生效。":"Click a card to assign it. Editing a library action updates its bindings after saving.",
  "动作名称":"Action name","编辑宏":"Edit macro","新建宏":"New macro","编辑 APP":"Edit APP",
  "添加 APP":"Add APP","保存到动作库":"Save to library","取消":"Cancel","关闭":"Close",
  "已安装的 Ubuntu 应用":"Installed Ubuntu applications","搜索已安装应用":"Search installed apps",
  "没有匹配的应用，可手动填写命令":"No matching apps. Enter a command manually.",
  "应用目录暂不可用，可手动填写命令":"Application list unavailable. Enter a command manually.",
  "可视化":"Visual","校验并应用代码":"Validate & apply code",
  "录制宏":"Record macro","停止录制":"Stop recording","记录间隔":"Record timing",
  "暂无步骤。添加按键、APP 或等待，也可以直接录制。":"No steps. Add shortcuts, apps or delays, or record a sequence.",
  "依次按下组合键，点击停止或按 Esc 结束。录制期间仅记录当前页面的键盘输入。":"Press shortcuts in sequence. Click Stop or press Esc to finish. Only this page's keyboard input is recorded.",
  "等待（毫秒）":"Delay (ms)","步骤类型":"Step type","从 APP 库填入":"Choose from APP library",
  "＋ 组合键":"+ Shortcut","＋ APP":"+ APP","＋ 等待":"+ Delay",
  "语音输入":"Voice input","按住语音键录音，松开转写；中键确认，下键取消。":"Assign push-to-talk, confirm and cancel actions to your preferred controls.",
  "为控件分配按住说话、确认和取消动作；下方配置录音与转写。":"Assign push-to-talk, confirm and cancel actions, then configure recording and transcription below.",
  "转写后端":"Transcription backend","外部可执行程序":"External program","离线 whisper.cpp":"Offline whisper.cpp",
  "兼容 OpenAI 的 API":"Compatible transcription API","麦克风 PulseAudio source":"Microphone PulseAudio source",
  "留空使用系统默认麦克风":"Leave blank for the default microphone","语言":"Language",
  "最长录音（秒，≤120）":"Maximum recording (seconds, ≤120)","转写超时（秒）":"Transcription timeout (seconds)",
  "转写完成后自动交付文本":"Deliver text automatically","命令参数 JSON 数组":"Command arguments (JSON array)",
  "音频路径通过 {audio} 传入；程序将 UTF-8 文本写入标准输出。无需 shell。":"Pass the audio path with {audio}. The program writes UTF-8 text to stdout without a shell.",
  "whisper.cpp 可执行文件":"whisper.cpp executable","模型绝对路径":"Absolute model path",
  "CPU 为默认运行方式。需单独安装 whisper.cpp 与多语言模型。":"CPU is the default. Install whisper.cpp and a multilingual model separately.",
  "完整转写端点":"Transcription endpoint","模型名称":"Model","API key 所在环境变量名":"API key environment variable",
  "密钥仅从后台进程环境读取。":"Credentials are read only from the daemon environment.",
  "● 开始测试录音":"● Test recording","■ 松开 / 转写":"■ Stop / transcribe","复制结果":"Copy result",
  "转写结果将显示在这里":"Transcription will appear here","空闲":"Idle","正在录音":"Recording",
  "正在转写":"Transcribing","等待确认":"Ready","已交付":"Delivered","出错":"Error",
  "配置与诊断":"Configuration & diagnostics","重新连接设备":"Reconnect device",
  "工作区与配置方案":"Workspace & profiles","界面语言":"Interface language","方案名称":"Profile name",
  "重命名方案":"Rename profile","复制为新方案":"Duplicate profile","删除当前方案":"Delete profile",
  "重命名当前层":"Rename layer","停止全部动作":"Stop all actions","设备状态":"Device status",
  "连接状态":"Connection","设备序列号":"Device serial","会话":"Session","灯效与保活":"Lighting & keepalive",
  "当前驱动尚未验证灯光、亮度和保活写入，因此不提供可执行的硬件写入控件。电量仅在设备上报时显示。":"Lighting, brightness and keepalive writes are not yet verified. Hardware write controls remain unavailable. Battery is shown only when reported.",
  "双击窗口（毫秒）":"Double-press window (ms)","长按阈值（毫秒）":"Long-press threshold (ms)",
  "AU05 序列号（可选）":"AU05 serial (optional)","USB 路径（可选，例如 3-9.4）":"USB path (optional, e.g. 3-9.4)",
  "导出配置":"Export configuration","导入配置":"Import configuration","丢弃编辑并重新加载":"Discard & reload",
  "完整配置 JSON（宏、应用参数及高级配置）":"Advanced configuration JSON",
  "将 JSON 应用到编辑区":"Apply JSON to draft","能力与设备诊断":"Capabilities & diagnostics","最近事件":"Recent events",
  "修改保存在当前草稿，保存后生效":"Changes stay in the draft until saved.",
  "本地运行 · 开源":"Local · Open source",
};
const originals = new WeakMap();
let language="zh";
try{language=localStorage.getItem("vibekey-language")==="en"?"en":"zh";}catch{}
const patterns=[
  [/^当前仅在编辑「(.+)」Layer (\d)；设备仍使用「(.+)」Layer (\d)。点击“启用此方案与层”才会切换。$/,(_,draft,layer,active,activeLayer)=>`Editing “${draft}” Layer ${layer}; the device still uses “${active}” Layer ${activeLayer}. Click “Activate profile & layer” to switch.`],
  [/^最近输入：等待设备操作$/,"Last input: waiting"],
  [/^最近输入：(.+)$/,(_,name)=>"Last input: "+(english[name] || name)],
  [/^正在使用：(.+) · Layer (\d)( · 预览中)?$/,(_,name,index,preview)=>`Active: ${name} · Layer ${index}${preview?" · Preview":""}`],
  [/^(.+) 动作库 · (\d+) \/ 16$/,(_,name,count)=>`${name==="宏"?"Macro":name} library · ${count} / 16`],
  [/^(\d+) 个步骤( · 依次执行)?$/,(_,count,suffix)=>`${count} steps${suffix?" · Sequential":""}`],
  [/^(\d+) \/ 100 步$/,(_,count)=>`${count} / 100 steps`],
  [/^等待 (\d+) ms$/,(_,ms)=>`Wait ${ms} ms`],
];
function translated(source){
  if(english[source])return english[source];
  for(const [pattern,replacement] of patterns)if(pattern.test(source))return source.replace(pattern,replacement);
  return source;
}
export function translateUI(){
  document.documentElement.lang=language==="en"?"en":"zh-CN";
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){
    const text=walker.currentNode;
    if(text.parentElement?.closest("script,style,textarea,pre,code,#profile,.library-assign,.combo-preview,.keycap,#mapping-label,[data-summary],.gesture-cell strong"))continue;
    const previous=originals.get(text),value=text.textContent;
    const original=previous&&(value===previous.original||value===previous.translated)?previous.original:value;
    const result=language==="en"?translated(original.trim()):original.trim();
    const next=value.replace(value.trim(),result);
    originals.set(text,{original,translated:language==="en"?next:translated(original)});
    if(value!==next)text.textContent=next;
  }
  for(const element of document.querySelectorAll("[placeholder],[aria-label]")){
    for(const attr of ["placeholder","aria-label"]){
      const value=element.getAttribute(attr);if(!value)continue;
      const key="i18n"+attr.replaceAll("-",""),source=element.dataset[key] || value;
      element.dataset[key]=source;
      const next=language==="en"?translated(source):source;
      if(value!==next)element.setAttribute(attr,next);
    }
  }
}
export function setupLanguage(){
  const picker=document.getElementById("language");picker.value=language;
  picker.onchange=()=>{
    language=picker.value;
    try{localStorage.setItem("vibekey-language",language);}catch{}
    translateUI();
  };
  let queued=false;
  new MutationObserver(()=>{
    if(queued)return;queued=true;
    queueMicrotask(()=>{queued=false;translateUI();});
  }).observe(document.body,{childList:true,subtree:true,characterData:true});
  translateUI();
}
