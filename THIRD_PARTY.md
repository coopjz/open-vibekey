# 上游参考与第三方依赖

本项目是独立实现的 Linux 用户态程序，不是 Ulanzi 官方软件。
AU05 HID 报告、默认键值、TEA 参数及物理按键事件的研究参考了以下开源项目：

| 项目 | 用途 | 上游许可 |
| --- | --- | --- |
| [OmiroAI/ulanzi-vibekey](https://github.com/OmiroAI/ulanzi-vibekey) | AU05 通信与协议研究 | MIT |
| [MrCroxx/olanzi](https://github.com/MrCroxx/olanzi) | Linux 设备处理与协议交叉参考 | MIT |
| [jimmibram/vibekey-driver](https://github.com/jimmibram/vibekey-driver) | HID、TEA 与按键事件交叉参考 | MIT |

未将这些项目的源码或二进制捆绑到发行包；本项目中的实现受根目录 MIT
许可证约束。未来直接引入第三方代码时，应保留对应版本的原始版权和许可声明。

0.2 工作台的布局与交互参照 `MrCroxx/olanzi`（Copyright © 2026 Croxx，MIT）
提交 `eb78f88f973d4d28f1d6d3369cdfb65881b1e1c6`：
VIA 风格键帽、六控件手势总览、Layer 选择、分类动作库和深灰/暖杏色配色。
界面与运行逻辑为本项目独立实现，具体能力差异记录于 `docs/ui-parity.md`。

以下为系统或用户单独安装的运行依赖，不包含在发行包中：

- Python 3、Linux hidraw/evdev/uinput、systemd、udev。
- GTK3 与 PyGObject：独立文本助手。
- PulseAudio 的 `parec`（`pulseaudio-utils`）：录音，也可连接 PipeWire 的
  PulseAudio 兼容服务。
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp)：可选离线转写，
  C/C++，MIT；模型另行下载，其许可应分别核对。
- 用户选用的转写命令或在线转写服务：由用户安装、配置并遵守其条款。

Ulanzi、VibeKey 和 AU05 名称仅用于说明硬件兼容性。


## 本地提取的 Studio 图片

`web/assets/studio/vibekey.png` 提取自用户提供的
`Win_Ulanzi_Studio_V3.4.8.20261027.exe`，资源路径
`:/profileui/images/vibekey.png`，版权归原权利人所有，不适用本项目 MIT 许可。
尚未发现允许再分发该图片的许可；当前用于用户请求的本地界面集成，
公开发布包含此图片的版本前应取得许可或替换为自行制作的图片。
文件身份、提取偏移及分析边界见 `docs/rea/studio-integration.md`。

fcitx5-vinput（https://github.com/xifan2333/fcitx5-vinput，GPL-3.0）作为用户
独立安装的外部输入法插件接入；本项目仅提供右 Alt 按住快捷键预设，未复制
其源码、模型或二进制。安装要求与本机限制见 `docs/fcitx5-vinput.md`。
