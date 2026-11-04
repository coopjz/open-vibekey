# 本机 fcitx5-vinput 配置与使用

2026-11-04，Ubuntu 20.04.6 / X11。保留系统版本和 PulseAudio，使用
用户级 Flatpak Fcitx5 + vinput v2.4.2 完整版。离线语音已通过用户实测。

## 日常操作

- **VibeKey 上键**：按住说话，松开识别。已设置 Hold 模式，短按不再切换持续录音。
- **Ctrl+空格**：英文键盘 / 中文拼音切换。Fcitx5 ChineseAddons 已安装。
- **右 Shift**：vinput 命令面板；输入 `/asr` 切换识别后端。
- 旋钮保留音量增减和静音。顺时针对应 `wheel:-`，逆时针对应 `wheel:+`。
- 应用菜单新增“VibeKey 语音设置”和“VibeKey 输入法设置”。

```bash
~/.local/bin/vibekey-voice status    # 服务和当前后端
~/.local/bin/vibekey-voice settings  # 官方 vinput GUI
~/.local/bin/vibekey-voice offline   # 选择本地识别并重启识别后台
~/.local/bin/vibekey-voice api       # 有密钥时选择 OpenAI；未填密钥时拒绝切换
~/.local/bin/vibekey-voice restart   # 重启整个输入栈，会暂时中断输入
```

语音由输入法提交到当前应用的输入框；VibeKey 网页中的内置录音、确认、取消
仍是另一套流程，不控制 vinput。右 Alt 按住预设可在“其他”动作库选择。

## 离线与 OpenAI API

默认使用本地 SenseVoice INT8 中文模型：
`model.sherpa-onnx.sense-voice-zh-en-ja-ko-yue-int8`，CPU 推理。
默认保留原始识别结果，不启用 LLM 改写。VAD 已关闭：之前发现整句被判为无人声，
关闭后用户确认整句检测恢复正常；这不代表模型已无错字。

另已安装 `oai-batch`（`provider.openai-compatible.batch`），配置：

| 设置 | 值 |
| --- | --- |
| URL | `https://api.openai.com/v1/audio/transcriptions` |
| 模型 | `gpt-transcribe` |
| 返回格式 | `json` |
| 请求超时 | 60 秒（provider 外层超时 65 秒） |
| API Key | 由用户在本机 GUI 的 provider 环境变量中填写 |

模型和端点依据当日 [OpenAI 官方语音转写文档](https://developers.openai.com/api/docs/guides/speech-to-text)。
上游脚本将 16kHz 单声道 PCM 封装成 WAV 发给端点，并读取 JSON 的 `text`。
本地与 API 配置共存，每次只选一个；没有自动把离线录音上传云端或自动故障切换。
只有选择 API 后才会按用户触发上传录音，真实 API 调用还需要凭据及账号模型权限。

GUI 中进入“控制”，编辑 OpenAI-Compatible (Batch) 的环境变量
`VINPUT_ASR_API_KEY` 并保存。无需把密钥发到聊天。
用户配置 `~/.var/app/org.fcitx.Fcitx5/config/vinput/config.json` 权限为 0600；
它不属于 Git 仓库，诊断只报告密钥是否存在，不输出内容。

## 桌面接入与自动启动

宿主 `fcitx5-frontend-gtk3`、`fcitx5-frontend-qt5` 已安装；检查实际 GTK
模块注册名称为 **fcitx**，不能因为包名就填成 fcitx5。
GTK 与 Qt 原生输入框都已建立 Fcitx5 D-Bus 输入上下文。

`~/.xinputrc` 已配置：

```sh
run_im none
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
```

不启动仓库中的旧版原生 Fcitx5 daemon；真正的服务由 Flatpak 启动。
已打开的应用可能仍保留旧环境，需要重启应用，或下次注销重新登录后生效。
未自动退出用户桌面或关闭浏览器。已建立输入上下文不等于所有应用均已实机验收。

`vibekey-voice.target` 已启用，随 `graphical-session.target` 自动启动：

| 用户服务 | 职责 |
| --- | --- |
| `vibekey-input.service` | 当前源码目录中的 AU05 驱动及网页（8765） |
| `vibekey-voice-pipewire.service` | 独立音频桥接，socket `pipewire-vibekey` |
| `vibekey-voice-policy.service` | 独立 PipeWire 路由 |
| `vibekey-vinput.service` | Flatpak vinput 识别后台 |
| `vibekey-fcitx5.service` | Flatpak Fcitx5 桌面输入法 |

设备访问已由 `scripts/install-voice-host-access.sh` 配置持久化规则。
用户已加入 `vibekey-input` 组，uinput 模块已配置开机加载；组成员身份下次登录生效，
本次会话保留用户 ACL。尚未实际注销/重启系统验收。

## 音频桥接与版本

- PipeWire 1.0.9，上游提交 `467fd4a02e37f93a8d27448eef548e247f020466`。
- media-session 0.4.2，上游提交 `80dae7e24bec02b2befe09a72fbac6e2b38ccb5c`。
- 本地前缀 `~/.local/opt/vibekey-voice/pipewire`，未替换系统库或 PulseAudio。
- pulse-tunnel source 固定为序列号 `202609081030` 的 AU05。
- vinput capture device 为 `vibekey-au05-microphone`。
- Flatpak 获得自定义 socket 访问权限，服务设置 `PIPEWIRE_REMOTE=pipewire-vibekey`。
- 模型归档 SHA-256：`7305f7905bfcf77fa0b39388a313f3da35c68d971661a65475b56fb2162c8e63`。

配置模板和单位文件位于 `packaging/voice/`，`.in` 文件必须渲染后才能使用。
当前源码驱动的服务依赖 `/home/cooper/code/vibe-key` 保持原路径。
USB 重插后的驱动连接已有此前实测；本轮未模拟麦克风拔插、PulseAudio 重启或系统重启。
若音频链路失效，先检查 `vibekey-voice status` 与 `vibekey-vinput device list`，
必要时重新启动整个目标；不保证 PipeWire 1.0.9 的 tunnel 能自动恢复所有断线情况。

## 验证与恢复

已验证：离线中文实机输入、禁用 VAD 后恢复整句检测、原生 GTK/Qt 输入上下文、
五个服务 active、target 自动启动链接、权限组和规则、离线/API 配置共存。
API 必须在填好密钥后另行验证；不会把“配置存在”报告为“云端识别通过”。

本次桌面配置备份在 `~/.local/state/vibekey-voice/backups/20261104-150652/`。
其中保存了原输入源、原 Fcitx5 profile 和原 vinput JSON（可能包含用户密钥，勿上传）。

停止自动启动：

```bash
systemctl --user disable --now vibekey-voice.target
```

这会同时停止 AU05 抓取与虚拟输出。恢复原输入法时，将 `~/.xinputrc` 改名保留，
重新选择原 IBus 输入法并注销/登录。该文件部署前不存在；不要删除用户后续新增的配置。
