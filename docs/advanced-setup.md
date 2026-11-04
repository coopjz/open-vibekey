# 安装补充与高级设置

日常安装和使用请看 [OpenVibe Key 使用说明](../README.md)。本文保留源码运行、语音安装命令和维护说明，按需查阅。

## 从源码运行

先安装宿主依赖并配置设备访问权限：

```sh
sudo apt install python3 python3-gi gir1.2-gtk-3.0 libgtk-3-bin \
  pulseaudio-utils wmctrl x11-utils xdg-utils
sudo sh scripts/install-voice-host-access.sh
```

注销、登录并重新插入接收器后，在图形终端运行：

```sh
sh scripts/run-dev.sh
```

源码模式和安装包模式只运行一份设备后台，避免重复抓取或占用 8765 端口。本机的旧版语音兼容部署使用 `vibekey-input.service`，与安装包的 `vibekey.service` 是两个不同入口，具体见 [兼容部署记录](fcitx5-vinput.md)。

## 没有设备时体验

```sh
sh scripts/run-dev.sh --simulate --config /tmp/vibekey-demo.json --port 8766
```

打开 <http://127.0.0.1:8766>，勾选「屏幕模拟」后操作界面控件。模拟模式不抓取设备、不注入按键、不执行自定义命令。内置「测试录音」仍是显式的真实麦克风操作。

## fcitx5-vinput 详细安装与配置

分工如下：

```text
VibeKey 实体按键 → 保持按住右 Alt → fcitx5-vinput 录音与识别
                                      ↓
                                Fcitx5 提交到当前输入框
```

Fcitx5 负责桌面输入；vinput 负责麦克风、识别 provider、模型和可选文字整理。**微信输入法指 vinput 中的 WeType 识别 provider**，Fcitx5 仍负责把文字交付给应用。

### 1. 安装 Fcitx5 与 vinput

按照系统版本选择 [vinput 官方安装方式](https://xifan2333.github.io/fcitx5-vinput/install/)。需要离线模型时选择 **Full** 版本；只使用云端识别可以选择 **Lite**。

**Ubuntu 24.04 原生安装示例：**

```sh
sudo apt install fcitx5 fcitx5-config-qt fcitx5-frontend-gtk3 fcitx5-frontend-qt5 im-config
sudo add-apt-repository ppa:xifan233/ppa
sudo apt update
sudo apt install fcitx5-vinput
```

需要拼音时可另安装 `fcitx5-chinese-addons`，并在 Fcitx5 输入法列表中添加拼音。

在系统输入法设置中选择 Fcitx5；使用 `im-config` 的桌面也可执行：

```sh
im-config -n fcitx5
```

注销并重新登录。随后启动识别后台并重新加载 Fcitx5：

```sh
systemctl --user enable --now vinput-daemon.service
fcitx5 -r
vinput-gui
```

先在普通文本框中直接测试右 Alt，确认 vinput 能够录音并上屏，再绑定硬件。

**Ubuntu 20.04：** 不要将上面的 24.04 PPA 当作通用安装源。该系统上的 Fcitx5 和音频组件需要单独处理兼容性。本机采用 Flatpak Fcitx5 + vinput，以及保留 PulseAudio 的独立 PipeWire 桥接；完整路径、服务模板和限制见 [Ubuntu 20.04 兼容部署记录](fcitx5-vinput.md)。

Flatpak 也是上游提供的安装方式，但本项目的 `.deb` **不会自动安装或配置整个 Flatpak 语音栈**。原生和 Flatpak Fcitx5 应选择一条运行路径，避免同时启动两个输入法后台。

### 2. 在 vinput 中配置触发键和麦克风

在 Fcitx5 的插件设置中配置 Vinput：

| 项目 | 推荐值 |
| --- | --- |
| 触发键 | 右 Alt，vinput 名称 `Alt_R` |
| 触发模式 | **Hold / 按住**，松开结束 |
| 麦克风 | 在 Vinput GUI 的「控制」页选择 AU05 或所需录音设备 |
| 初始文字处理 | 先使用「原始」场景确认识别效果，再按需开启整理或改写 |

```sh
vinput device list
```

Fcitx5/vinput 的触发键如果改为其他键，VibeKey 端也要同步修改。

### 3. 选择识别方式

在 Vinput GUI 中安装并选择资源。也可用右 Shift 打开命令面板，通过 `/asr` 切换。模型和 provider 可以共存，每次使用所选后端。

| 方式 | 配置入口 | 使用条件 |
| --- | --- | --- |
| 微信输入法 WeType | 「资源 → ASR 提供商」安装 WeType，再到「控制」选择 | 联网识别，本机用户已实测效果良好 |
| 本地离线模型 | Full 版「资源 → 模型」下载并启用支持中文的模型，例如 SenseVoice | 模型下载完成后可离线识别 |
| 兼容语音 API | 安装 OpenAI-Compatible (Batch) 等 provider，在「控制」中配置环境变量 | 需要对应服务的端点、模型与凭据 |

**微信输入法 provider 示例：**

```sh
vinput provider list -a
vinput provider add provider.wetype.streaming
vinput provider use provider.wetype.streaming
vinput scene use __raw__
```

WeType provider 使用微信输入法的非官方客户端协议；按当前 provider 文档无需用户 API key 或微信登录，录音会发送到微信输入法云端识别。其运行依赖包括 `libopus` 和 OpenSSL `libcrypto`，服务可用性取决于服务端。参见 [WeType provider 说明](https://github.com/xifan2333/vinput-registry/blob/main/resources/providers/wetype/streaming/README.md)。

**离线识别：** 在「资源 → 模型」下载并启用一个中文模型，在「控制」页确认当前 provider 为本地 sherpa-onnx。首次下载需要网络，模型文件不随 VibeKey 安装包提供。要求全离线使用时，同时选择原始场景并关闭云端 LLM 整理。

**API 识别：** 在 vinput 的 provider 环境变量中配置：

| 环境变量 | 内容 |
| --- | --- |
| `VINPUT_ASR_URL` | 服务提供的完整语音转写 URL，例如 `https://api.openai.com/v1/audio/transcriptions` |
| `VINPUT_ASR_MODEL` | 该服务支持且账号可用的语音转写模型 |
| `VINPUT_ASR_API_KEY` | 服务密钥，在本机 GUI 填写 |
| `VINPUT_ASR_LANGUAGE` | 按 provider 和服务要求填写，例如 `zh` |

以上字段对应 [OpenAI-Compatible Batch provider](https://github.com/xifan2333/vinput-registry/blob/main/resources/providers/openai-compatible/batch/README.md)。使用其他 provider 时，以其环境变量说明为准。API 模式会上传录音；vinput 的凭据配置与 VibeKey 内置 API 后端独立，不要将密钥写入 VibeKey 导出的键位 JSON。

### 4. 将 VibeKey 上键设为按住说话

在 VibeKey 控制台：

1. 点击上键的「单击」槽。
2. 在「其他」分类选择 **fcitx5-vinput**。
3. 确认动作是 `RIGHTALT`，输出模式为「保持按住」。
4. 保存到本机，确认当前方案已启用，并关闭预览模式。
5. 点击目标应用的输入框，按住上键说话，松开后等待文字出现。

对应动作配置：

```json
{"type":"shortcut","keys":"RIGHTALT","mode":"hold","label":"fcitx5-vinput"}
```

新增场景预设时，勾选「沿用当前方案的语音键」可以保留已调好的触发方式。

### 5. 原生与兼容部署的命令区别

上述 `vinput` / `vinput-gui` 命令适用于原生安装。已按本机 Ubuntu 20.04 记录部署独立音频桥的环境，使用以下入口：

```sh
vibekey-vinput device list
vibekey-vinput provider list
vibekey-vinput-gui
vibekey-voice status
```

这些封装依赖 `org.fcitx.Fcitx5`、Vinput Flatpak 扩展、`pipewire-vibekey` 音频桥及对应用户服务已经部署。安装 VibeKey 包本身不会创建这些语音服务。`vibekey-voice offline` / `api` 是本机兼容栈的切换助手，依赖已安装的模型和 provider；请按需使用，避免覆盖自己正在使用的 WeType 选择。

## 内置语音转写（可选）

除推荐的 vinput 路线外，语音页还提供独立的录音/转写流程：外部可执行程序、离线 whisper.cpp、兼容音频转写 API。可分配按住录音、确认文本和取消动作，默认需要自行配置后端。

该流程由 VibeKey 后台调用 `parec` 录音，最长 120 秒。X11 下通过 GTK 助手持有剪贴板并发送 Ctrl+V；Wayland 下复制结果供手动粘贴。语音页的录音、确认、取消按钮控制这套内置流程，**不控制 fcitx5-vinput**。

内置 API 密钥通过后台环境变量读取，默认变量名为 `VIBEKEY_API_KEY`。安装包服务可从 `~/.config/vibekey/service.env` 加载环境变量；修改后重启对应 VibeKey 服务。选择 vinput 路线时，在 vinput 中配置 provider、模型和凭据即可。

## 配置与运行说明

- 默认配置：`~/.config/vibekey/config.json`；设置 `XDG_CONFIG_HOME` 时改用该目录，`--config` 可指定其他文件。
- 原子保存，上一版备份为 `.bak`；用户配置权限为 `600`。配置损坏时保留原文件并暂停物理动作。
- 最多 32 个方案，每个方案四层；APP、宏库各最多 16 项，宏最多 100 步，单次等待最多 30 秒。
- 标准 HID 模式通过学习信号完成映射；设备节点号会变化，程序按 USB 父设备发现，不依赖固定 `/dev/hidrawN`。
- 多台 AU05 同时接入时，在设置中指定序列号或 USB 路径。拔出设备会取消动作、释放虚拟按键并重新发现。
- 后台仅监听 `127.0.0.1`，写接口使用每次启动生成的令牌。Shell 和应用动作以当前桌面用户身份运行。

当前仅验证本机 X11 桌面；CI 中的多版本 Python 测试不等于对应发行版的桌面与硬件验收。

## 开发与验证

```sh
python3 -m unittest discover -s tests -v
node --test tests/model.test.mjs
node tests/browser-smoke.mjs
sh scripts/build-deb.sh
```

Python 单元测试和前端配置模型测试不要求真实设备；浏览器检查需要 Node 22+ 和本机 Chrome，使用独立模拟后台与临时配置。可用 `CHROME`、`PYTHON` 指定程序路径。Node 仅是开发测试工具，不是驱动运行依赖。

已有验证包括六控件输入、旋钮方向、音量/静音、用户确认的宏与 vinput 语音输入、电量/灯效回读，以及真实终端窗口的自动跟随与默认回退。API 配置存在不代表真实服务调用已通过；其他发行版、Wayland、CPU 架构和固件仍需分别测试。
