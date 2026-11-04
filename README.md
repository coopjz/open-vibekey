# VibeKey Linux

Ulanzi AU05 VibeKey 的开源 Linux 用户态驱动与中文可视化配置界面。
目标是 Ubuntu 22.04，并保留 Python 3.8 兼容性，以支持 Ubuntu 20.04。
当前版本为 0.2.0，已完成 AU05 六个控件输入的实机验证；
新增动作输出、桌面集成与语音功能的实机验证范围见文末。

支持六个控件、按键单击/双击/长按、每个方案四层、按住临时切层、快捷键、
应用启动、文本、Shell 命令、顺序宏，以及按住说话、转写后确认或取消。
网页与后台分离，关闭网页后后台仍可处理按键。

## 可视化工作台

以 Olanzi 的 VIA 风格配置流程为参照：深灰与暖杏色配色、银色设备图、
六个控件的手势总览、Layer 0–3、分类键帽与独立动作设置。
具体对照范围和平台差异见 [UI 功能对照](docs/ui-parity.md)。

- 点设备控件或手势卡片，选择要编辑的单击、双击、长按或旋转动作。
- 从常用、字符、功能键、数字键盘、媒体、组合键等分类中分配按键，也可搜索。
- 在组合键面板或动作设置中录制快捷键；支持 1–20 次连按。
  按键单击槽支持保持按住，松开设备按键即释放。
- APP 库可从 Ubuntu 已安装应用中选择，也能手动填写可执行文件和参数。
  X11 安装 `wmctrl` 且配置了窗口类时，可优先聚焦已有窗口。
- 宏库支持键盘录制、可选录制间隔、步骤增删与排序、APP/按键/等待组合，
  以及可视化与受支持的 QMK 风格 Code 切换。每个宏最多 100 步。
- APP 和宏各可保存 16 个具名动作；点击卡片分配，编辑库动作会更新其绑定副本。
- 显式 `▽` 继承较低层的同一手势，`×` 表示不执行；新增配置的 Layer 1–3
  默认继承。已有配置保持原语义，不自动改写动作。
- 设置中可重命名、复制、删除方案和重命名图层；中英文切换保存于浏览器，
  不修改配置草稿。

所有动作和库编辑都是草稿，点击“保存到本机”后生效。“启用此方案与层”
同时保存草稿并启用所选方案与层；仅切换编辑层不会改变运行层。
实时输入反馈与编辑选中状态独立，旋钮方向分别计数。
编辑的方案或层与实际运行项不同时，工作台会显示提示并突出“启用此方案与层”按钮。
只在下拉框选择方案不会立即切换设备动作。

## 每层的语言与职责

| 层 | 语言 | 实现 |
| --- | --- | --- |
| USB/HID 与 evdev | Python 3.8+ | 标准库 `os`、`fcntl`、`select`，按 USB 父设备发现节点，读取 hidraw 并独占 AU05 的 evdev |
| 协议编解码 | Python 3.8+ | 标准 HID 报告、TEA、厂商物理按键与被动状态报告 |
| 手势、方案、宏与配置 | Python 3.8+ | 时间状态机、动作工作队列、JSON 配置、原子保存与备份 |
| 虚拟输入 | Python 3.8+ | 直接调用 Linux uinput，发送快捷键、媒体键和鼠标按钮 |
| 本地 HTTP 与 SSE | Python 3.8+ | 标准库 HTTP 服务，只监听 `127.0.0.1` |
| 可视化配置 | JavaScript、HTML、CSS | 原生 ES Modules，无 npm 构建步骤 |
| 桌面剪贴板/文本窗口 | Python + GTK3 | 独立 PyGObject 进程，持有 Unicode 剪贴板 |
| 录音编排 | Python 3.8+ | 调用系统 `parec`，生成单声道 16 kHz PCM WAV |
| 可选离线识别 | C/C++ | 外部 `whisper.cpp` / `whisper-cli`，单独安装 |
| 可选在线识别 | Python 3.8+ | 标准库 HTTPS multipart，兼容音频转写接口 |
| 安装与发布 | POSIX Shell、Debian 元数据 | `.deb`、udev、systemd 用户服务、桌面入口 |
| 测试 | Python、JavaScript | `unittest` 与 Node 内置测试框架 |

无需编写内核模块。系统的 HID、evdev、uinput 驱动继续由 Linux 提供；
本项目在用户空间进行映射和动作执行。

## 无需安装的模拟体验

在项目目录运行：

```sh
sh scripts/run-dev.sh --simulate
```

打开 <http://127.0.0.1:8765>。勾选模拟输入后，按住/释放界面上的按键，
测试手势、层与方案。模拟模式不抓取物理设备、不注入按键、不运行自定义命令。
“测试录音”是显式操作，仍会访问麦克风并调用你配置的转写后端。
模拟模式确认文本只产生模拟事件。

只读诊断：

```sh
sh scripts/run-dev.sh --diagnose
```

开发运行默认也使用真实的 XDG 配置位置。希望与正式配置隔离时：

```sh
sh scripts/run-dev.sh --simulate --config /tmp/vibekey-demo.json --port 8766
```

## Ubuntu 安装

构建不需要 pip、Node 或网络下载：

```sh
sh scripts/build-deb.sh
sudo apt install ./dist/vibekey_0.2.0_all.deb
sudo usermod -aG vibekey-input "$USER"
```

**完整注销桌面并重新登录，再拔插 AU05**，使新的组成员身份和设备 ACL 生效。
在应用菜单打开 VibeKey；网页地址为 <http://127.0.0.1:8765>。
下次图形登录时会自动启动后台，不自动弹出浏览器。
本次会话也可以运行：

```sh
vibekey-session
systemctl --user status vibekey.service
journalctl --user -u vibekey.service
```

安装包是 `Architecture: all`，因为只包含 Python 与网页源码；
这不表示已经验证所有 CPU 架构。初期实机目标为 amd64。
GTK3、PyGObject、`parec` 等由 Ubuntu 的包管理器安装。

服务以当前桌面用户身份运行。`vibekey-session` 将 DISPLAY、WAYLAND_DISPLAY、
XAUTHORITY 与会话类型导入用户 systemd 环境，再启动服务。
请从图形终端运行；SSH 会话通常缺少剪贴板所需的环境。
服务采用桌面自启动入口，无需执行 `systemctl enable`。

udev 的 AU05 规则只匹配 VID `fff1` / PID `00dd`；
`vibekey-input` 组用于 `/dev/uinput`，具有创建虚拟输入设备的权限。
不要把普通用户加入通用 `input` 组，也不要将输入节点改成全员可写。
如果现有系统另有更宽松的 uinput 规则，本项目不会自动修改它。

卸载：

```sh
systemctl --user stop vibekey.service
sudo apt remove vibekey
```

用户配置和 `vibekey-input` 组保留。默认情况下项目不会删除你的配置。
如需禁用登录启动，可在 `~/.config/autostart/vibekey-autostart.desktop`
创建同名桌面条目并设置 `Hidden=true`。

## 首次连接与映射

1. 先关闭其他 VibeKey 驱动及官方软件，运行只读诊断，确认发现 AU05。
2. 启动真实模式：安装后打开应用，或在源码目录运行 `sh scripts/run-dev.sh`。
3. 在界面开启“预览/学习”，逐个按键，观察原始信号；选择对应控件并学习映射。
4. 保存配置，退出预览，再测试一个低影响动作，例如音量。

页面的“正在编辑的控件”由鼠标选择，保持选中以便编辑；
“最近输入”和本页正反向计数显示实际收到的设备事件。
验证旋钮方向时先清零计数，再分别转动两个方向，观察独立计数与最近输入。

默认映射对应已研究的原厂键值。固件或曾修改过的设备可能不同，需重新学习。
标准模式将组合键按最初的“修饰键 + 普通键”识别为一次按下/松开，
例如 `keyboard:08:0b`；松开修饰键时不会额外触发 `keyboard:00:0b`。
单独的修饰键报告作为组合键的过渡状态处理，不支持映射为独立控件。
预览期间服务仍抓取 AU05 原厂输入，但不执行自定义动作。
预览使用 15 秒租约，页面每 5 秒续期，页面关闭后会自动到期恢复动作。
同一控件若有多余旧映射，可在完整 JSON 编辑区的 `device.mapping` 删除。

2026-11-02 的一次 AU05 实物采集确认了下列映射。设备曾配置的键值可能不同，
因此这是一台设备的实测结果；请以自己设备的学习结果为准：

| 物理控件 | 实测原始信号 |
| --- | --- |
| 上键 | `keyboard:08:0b`（Super + H） |
| 中键 | `keyboard:00:28`（Enter） |
| 下键 | `keyboard:00:29`（Escape） |
| 旋钮按下 | `keyboard:00:2a`（Backspace） |
| 顺时针 | `wheel:+` |
| 逆时针 | `wheel:-` |

这台设备的旋钮按下与默认映射中的逆时针键值相同，必须将
`keyboard:00:2a` 改为 `knob`，并用 `wheel:-` 识别逆时针。
采集报告已保存为 `tests/fixtures/au05-standard-session.json`，
回归测试覆盖全部六个控件及组合键释放顺序。

设备节点号可能变化，发现过程不依赖 `/dev/hidraw12` 等固定路径。
插入多台 AU05 时，必须在设置中指定序列号或 USB 路径，避免选错设备。
成功抓取所选设备全部 evdev 节点后才启用动作；任何节点失败均回滚抓取。
其他 USB 父设备下的键盘、鼠标不参与抓取。
拔出设备会取消动作、释放已注入按键，并每三秒尝试重新发现。

默认 `device.input_mode` 为 `standard`，从接口 02 解码并学习映射。
`vendor` 是为已经输出厂商物理事件的设备准备的高级选项，可在 JSON 中设置；
其事件从接口 03 直接映射物理控件，不经过原始键值学习。
程序不会自动发送 Studio 心跳来切换模式，也不同时消费两路按键事件。

## 方案、手势与动作

界面先选择方案和层进行编辑。“保存”只保存编辑；
“启用当前方案/层”同时改变后台正在使用的方案和层。
动作触发的层/方案切换先在内存生效，在下一次保存配置时持久化。
层索引在 JSON 和界面中均为 `0..3`。
配置支持最多 32 个方案，层和方案名称可在设置页修改。

旋转只支持单次脉冲。按住说话和按住切层必须是单击槽中的独占动作。
仅配置单击时立即执行；配置双击后会等待双击窗口，配置长按后会判断释放时间。
“取消所有动作”清理待处理手势、宏、临时层、语音和虚拟按键。

动作参数通过表单、键帽和宏编辑器修改；完整 JSON 保留为高级入口。
保存时后台统一校验，版本 1 配置继续兼容。
例：

```json
{"type":"shortcut","keys":"CTRL+SHIFT+T"}
```

```json
{"type":"application","argv":["/usr/bin/gnome-terminal"]}
```

```json
{"type":"macro","steps":[
  {"type":"shortcut","keys":"CTRL+C"},
  {"delay_ms":150},
  {"type":"shortcut","keys":"ALT+TAB"},
  {"delay_ms":150},
  {"type":"shortcut","keys":"CTRL+V"}
]}
```

其他动作：

```json
{"type":"text","value":"你好，Ubuntu"}
{"type":"shell","value":"notify-send 'VibeKey' 'Hello'"}
{"type":"volume","operation":"mute"}
{"type":"layer","index":1}
{"type":"momentary_layer","index":2}
{"type":"profile","id":"default"}
{"type":"voice","operation":"ptt"}
{"type":"voice","operation":"confirm"}
{"type":"voice","operation":"cancel"}
{"type":"none"}
```

上面各行是独立动作对象。快捷键使用 Linux 物理键名，包括 A–Z、0–9、
F1–F12、CTRL/SHIFT/ALT/SUPER、方向键、媒体键与 BTN_LEFT/BTN_RIGHT/BTN_MIDDLE。
输入字符受目标应用键盘布局影响；Unicode 文本应使用文本动作。
暂未提供鼠标移动或滚轮动作。
应用与 Shell 在串行动作队列中等待退出，最长 300 秒；
长时间运行的桌面程序建议使用能立即返回的启动器，例如
`["/usr/bin/gio","launch","/usr/share/applications/org.gnome.Terminal.desktop"]`。
宏不允许嵌套，最多 100 步，每次延迟最多 30 秒。

## 语音转写

默认顶键按住录音、释放转写，中键确认结果，下键取消；
首次使用需要先配置转写后端。默认后端为空命令，不会自动下载模型或发送音频。
在界面保存设置后，再使用“测试录音”验证。麦克风源可为空使用系统默认源，
或通过下面的命令查询并填入准确的 source 名称：

```sh
pactl list short sources
```

录音为单声道 16 kHz、16 bit PCM，最长 120 秒。
设备自身 USB 麦克风是否可用，取决于音频系统识别结果；
拔插之后若源名失效，需要重新选择。

三种后端：

- **外部命令**：填写 argv JSON 数组，`{audio}` 替换为 WAV 路径，
  `{language}` 替换为语言；标准输出必须只含 UTF-8 转写文本。
  未写 `{audio}` 时自动将音频路径追加到 argv。
- **whisper.cpp**：单独安装提供 `-f/-m/-l/-otxt/-of/-nt/-np` 参数的
  `whisper-cli`，填写可执行文件与模型绝对路径。模型和 GPU 加速由该外部项目管理；
  此项目未捆绑模型，也未验证本机 RTX 5070 的 CUDA 构建。
- **API**：填写兼容音频转写 API 的 HTTPS 地址、模型和密钥环境变量名称。
  HTTP 仅允许 loopback。音频会上传至配置的服务端。

用于验证录音编排的假转写命令（不做语音识别）：

```json
["/usr/bin/python3","-c","import sys,wave; w=wave.open(sys.argv[1]); print('录音链路已连接')","{audio}"]
```

API 密钥不写入配置 JSON。服务可以从
`~/.config/vibekey/service.env` 读取：

```ini
VIBEKEY_API_KEY=your-secret
```

将该文件权限设置为 `600`，再执行 `systemctl --user restart vibekey.service`。
源码运行时可以从父进程环境继承密钥。配置导出不包含环境文件；
不要将密钥放入命令参数、URL 或导入的 JSON。

转写完成默认等待确认；可在语音设置启用自动交付。
X11 下由 GTK 助手持有剪贴板并发送 Ctrl+V，目标应用需保持正确焦点；
从网页点“确认”时目标通常就是浏览器，建议使用硬件确认键。
Wayland 下复制结果并显示窗口，需要用户回到目标应用手动粘贴。
快捷键仍通过 uinput 发送，实际效果受桌面、锁屏与目标应用限制。
录音、转写中间文件在完成、取消或失败后清理，取消会终止转写子进程。
进程被强制 `SIGKILL` 时无法执行清理，可自行检查 `/tmp/vibekey-audio-*`。
转写结果只保留在内存、网页及剪贴板中，不写入项目日志。

## 配置、接口与恢复

- 配置：`${XDG_CONFIG_HOME:-~/.config}/vibekey/config.json`。
- 上一版本备份：相同路径后加 `.bak`；保存使用原子替换，文件权限 `600`。
- 配置损坏：保留原文件、报告错误并暂停物理动作；显式保存才会替换。
- 文本助手：`${XDG_RUNTIME_DIR}/vibekey/text.sock`；无 runtime 目录时使用私有临时目录。
- 端口冲突：关闭其他实例，或源码运行添加 `--port`。桌面入口固定使用 8765。

后台只监听 IPv4 loopback，校验 Host/Origin，并要求写请求携带每次启动生成的
`X-VibeKey-Token`。网页通过 `/api/state` 获取 token，通过 SSE 接收状态事件。
本机同一用户的进程属于信任范围。导入配置可定义以当前用户权限执行的命令，
因此请检查来源；服务不提供远程访问功能。

主要接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/state`、`/api/config`、`/api/capabilities` | 状态、配置与能力 |
| GET | `/api/applications` | 本机 freedesktop 应用列表与启动参数，不启动应用 |
| GET | `/api/events` | SSE 事件流 |
| PUT | `/api/config` | 校验并保存整个配置 |
| POST | `/api/preview` | `{"seconds":15}`，范围 0–30 |
| POST | `/api/device/refresh`、`/api/cancel` | 重新发现、取消动作 |
| POST | `/api/voice/test` | `{"operation":"start"}`，另有 stop/confirm/cancel |
| POST | `/api/simulate` | 仅模拟模式，`{"control":"top","pressed":true}` |

## 验证范围

| 环境/能力 | 当前情况 |
| --- | --- |
| 本机 Ubuntu 20.04.6、Python 3.8.10、GNOME X11 | 已运行自动化测试和只读设备发现 |
| 本机 AU05，序列号 202609081030 | 已识别节点并成功独占抓取；有序实物采集确认全部六个控件的输入报告和映射 |
| 本机 Chrome、模拟后台 | 已验证表单编辑、快捷键录制、APP/宏库、宏排序与 Code、层、语言切换保留草稿、SSE、方向计数、错误导入恢复和三页窄屏布局 |
| Debian 安装包 | 已构建并解包，验证启动及 HTML、JavaScript、API 访问；尚未进行系统安装验收 |
| Ubuntu 22.04 容器、Python 3.10.4 | 0.2.0 的 57 项 Python 测试全部通过；尚未验收 22.04 桌面与实物输入 |
| Ubuntu 24.04 | 已加入 CI 容器测试配置，尚未实际运行 |
| Wayland 图形会话 | 已实现剪贴板加手动粘贴路径，尚未实测 |
| 音量与静音 | 本机实物测试通过；测试时需启用音量方案及对应层 |
| 其他 uinput 动作与 GTK 粘贴 | 有实现及部分模拟测试，尚未完成交互式实机验收 |
| 真实录音与 whisper/API 识别 | 流程已有子进程测试；未完成真实音频/模型/远程服务验收 |
| 灯效与全亮亮度 | 设置页支持全亮 / 全灭 / 工作模式，以及 0–20 档全亮亮度；写入后回读确认 |
| 固件键表写入 | 尚未启用 |
| 电量与在线状态 | 每 20 秒主动查询，支持手动刷新；待机或断连时清空旧电量 |

仅在设置页明确点击“应用灯效”时写入灯效参数；查询电量不发送 Studio 心跳。不会改写固件键表。

设置页内置 AU05-X 的「默认预设」「快速派活」「多任务模式」，根据官方 Windows 安装包恢复快捷键。添加时可沿用当前语音键；切换到设备前需点击“启用此方案与层”。快捷键需要目标应用支持，可继续编辑。证据与实机验证见 [预设与灯效记录](docs/rea/presets-and-lighting.md)。

设置 → **软件自动跟随** 可按前台应用自动选择方案，并为未绑定应用指定默认方案。新增 **Codex CLI / Claude Code** 场景预设；点击“添加 CLI 自动跟随”，保存后从专用入口启动即可稳定识别。支持普通应用的窗口类别、标题和标识规则。详见 [自动跟随使用说明](docs/auto-follow.md)。
协议编码器供测试与后续研究使用。不要把协议测试通过视为全部固件兼容性认证。

运行测试：

```sh
python3 -m unittest discover -s tests -v
node --test tests/model.test.mjs
node --input-type=module --check < web/app.js
sh scripts/build-deb.sh
```

Python 测试不依赖桌面、root 或实物；Node 只用于开发测试，非运行依赖。
CI 在 Ubuntu 20.04/22.04/24.04 容器运行核心测试，不能替代桌面与硬件测试。

可选的真实浏览器检查需要 Node 22 和本机 Chrome，会启动独立的模拟后台与临时浏览器：

```sh
node tests/browser-smoke.mjs
```

可通过 `CHROME` 指定 Chrome 可执行文件，通过 `PYTHON` 指定 Python。

MIT 许可。上游研究来源与外部依赖见 [THIRD_PARTY.md](THIRD_PARTY.md)。


### Studio 本地集成

键位工作台使用从用户提供的 Studio 安装包提取的 AU05 图片。
在“其他”动作库或“动作类型”中选择“打开网站”，填写完整 HTTP(S) 地址，
保存后由默认浏览器打开；同样可用于宏步骤和旋转动作。模拟模式不打开浏览器。
图片来源与许可、逆向分析证据及未验证能力见 [Studio 集成记录](docs/rea/studio-integration.md)。

### fcitx5-vinput 语音输入

可在实体按键的“单击”槽选择“其他 → fcitx5-vinput”，保存后通过右 Alt
按住事件调用外部输入法的按住说话。需先安装并配置 Fcitx5/vinput；
该功能与内置语音后端独立。Ubuntu 20.04 的兼容性限制和部署步骤见
[接入说明](docs/fcitx5-vinput.md)。

fcitx5-vinput 可同时配置本地中文离线模型与 OpenAI 兼容 API，并在 vinput 中切换。
本机已通过独立测试窗口的离线中文实测；普通桌面应用仍使用原输入法，
尚未全局切换。API 提供商已安装，真实调用需用户配置凭据。
