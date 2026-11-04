# 官方 Studio 的语音输入路径

核对日期：2026-11-04。
目标为用户提供的 `Win_Ulanzi_Studio_V3.4.8.20261027.exe`；
安装器身份与解包映射沿用 `studio-integration.md`。

## 结论及证据类型

官方 AU05 文档明确描述：语音输入通过绑定第三方语音输入软件的快捷键实现，
举例包括 Typeless、豆包输入法和微信输入法。这支持“设备/Studio 负责触发，
第三方工具负责识别”的使用路径；不支持推断官方自带某个特别准确的 ASR 模型。

- AU05 使用指南：
  https://docs.ulanzistudio.com/vibekey/au05/#_2-1-认识-vibe-key-控制方式
- 官方兼容说明：
  https://docs.ulanzistudio.com/vibekey/faq/voice-input-compatibility.html
- AU05-X 文档作为旁证，不能替代 AU05 的硬件证据：
  https://docs.ulanzistudio.com/vibekey/au05-x/
  其中说明联名款默认以 Command+D 调用 WorkBuddy 自身录音，也可更改为其他工具快捷键。

因此，本项目目前通过右 Alt 按住事件调用 fcitx5-vinput 的设计与官方所描述的
快捷键集成路径一致。当前中文错误率应进一步从收音质量和 vinput 所选 ASR
后端评估，不能期待复制 Studio 的按键逻辑就能更换识别引擎。

## 安装包中的可复核事实（普通静态解析）

解压块 370 是 `UlanziDeck.exe`，块 372 是 `Ulanzi_Studio.dll`。
EXE `.rdata` 的文件偏移到虚拟地址换算为 image base `0x140000000`
加 `file_offset + 0x1200`。

| 文件位置 | 观察 |
| --- | --- |
| EXE `0x625d98` | `SettingDialog::onDenoiseLevelChanged(int)` 日志标识 |
| EXE `0x625e58` | `SettingDialog::OnSetDeviceDenoiseLevel(int)` 日志标识 |
| EXE `0x616a10` | `DialDeviceManager::onSetDeviceMicNRLevel(QString const &,int)` 标识 |
| EXE `0x614a48`、`0x614a60` | `getDeviceMicNRLevel`、`setDeviceMicNRLevel` 动态 SDK 名称 |
| EXE `0xff1548` | Qt 元数据类名 `SystemAudioInputService` |
| DLL export | `getDeviceMicNRLevel` / `setDeviceMicNRLevel` |
| EXE import | Windows `keybd_event` / `SendInput` |

这些是符号和字符串的存在证据，不能单凭名字确定具体 HID 命令、降噪参数、
设备型号覆盖或执行时序。官方 AU05 文档另明确提供设备降噪的开启/关闭设置。
硬件降噪与 VAD（静音检测）及 ASR（识别）是不同环节；不把它们混同。

块 300 的 `AI Solutions.ulanziDeckProfile` 实际是带版本前缀的 ZIP。
检查其 manifest 后得到 33 个打开网站动作、2 个上一页、2 个下一页动作；
根 manifest 标注 D200H。这个“AI”名字不能作为 Studio 内置识别模型或 AU05
识别配置的证据。

## 对当前 Linux 版本的处理

- 保留已通过实机测试的右 Alt 按住触发。
- 保留当前关闭 VAD 的配置：之前整句消失在日志中有明确的 VAD 跳过记录，
  关闭后用户确认检测恢复正常。
- 当前模型仍是本地 SenseVoice INT8，未为了本轮调查擅自更换。
- API provider 已安装，但未填入凭据、未运行真实 API 对照。
- 若错误集中于专有名词，可评估支持热词的模型；若是一般中文误识别，应对
  同一批语句比较其他本地模型或用户选择的云 API。改善幅度须用实际结果判断。
- 不在本轮发送未经验证的硬件降噪设置命令。

## 覆盖边界

文档是当前官网内容，版本与用户提供的 3.4.8 安装包未必完全相同。
静态字符串检索没有发现某个模型名，不足以证明所有插件或后续下载资源都无 ASR。
本轮未启动 Windows Studio、未抓取其运行流量，也未验证第三方识别服务的模型。


## REA / Ghidra 降噪入口证据

Ghidra 12.1.4 对 `Ulanzi_Studio.dll` 的导出
`setDeviceMicNRLevel`（`0x1800519e0`）完成函数分析：
Evidence `ev_335c8366d703b38dc7a14c1c59b84a69b9a44115885af74a96c96bc29a56fbc2`，
完整 dossier 见 `studio-micnr-function.json`。
该入口检查 SDK 全局状态，按传入标识查找设备对象，找到后调用
`FUN_180039d90` 并传递其余参数。这个入口不执行语音转写。
这仍未给出下游 HID 报告布局、参数语义或特定型号支持范围；不据此发硬件命令。


EXE 主程序的 REA/Ghidra 分析已完成；类名 `SystemAudioInputService`
（地址 `0x140ff2748`）的引用查询返回 `0x140516e7e`。
Evidence `ev_8d4294aca4ace034e36420b1b6af152dc19773054f0862b57c117b894ea74691`，
见 `studio-speech-service-xrefs.json`。本轮没有继续反编译该类的全部行为；
不得将单个类名引用查询写成已证明“主程序所有路径都不做 ASR”。
