# AU05-X 预设、电量与灯效（2026-11-04）

## 来源和差异

官方说明：https://docs.ulanzistudio.com/vibekey/au05-x/ ，2.1 出厂预设、2.2 语音、2.5 灯效。

实际绑定取自用户提供的 Windows Studio 3.4.8.20261027 安装包（SHA256 `72cc5c89f85941522a906dfd2bc77fd32e0416aa261fc96177ea3a6be7e4caa9`）中 AU05 配置包：block-295、297、298。三个包的 SHA256 和原始控制器 JSON 保留在 [studio-workbuddy-presets.json](studio-workbuddy-presets.json)。不依赖运行 Windows Studio。

| 控件 | 默认预设 | 快速派活 | 多任务模式 |
|---|---|---|---|
| 上键 | Ctrl+D | Ctrl+D | Ctrl+D |
| 中键 | Enter | Enter | Enter |
| 下键 | Esc | Esc | Esc |
| 旋钮按下 | Shift+Alt+W | Ctrl+N | Shift+Alt+W |
| 逆时针 | 鼠标向上滚动 | Ctrl+[ | Ctrl+[ |
| 顺时针 | 鼠标向下滚动 | Ctrl+] | Ctrl+] |

网页插图使用 macOS Command，且后两张图的链接名、图中功能和 Windows 包的方案名称存在差异。本实现保留 Windows 包的名称与绑定对应关系，没有机械地把截图中的 Command 映射为 Linux Super。目标应用需要支持相应快捷键，所有绑定均可编辑。

添加模板默认复制当前启用方案/层的整个上键绑定，以保留按住说话、双击等现有行为；取消勾选后使用原始 Ctrl+D。安装在当前用户配置的三个方案已经沿用 RIGHTALT 保持按住，不涉及 vinput provider 修改。选择编辑方案不会自动启用，需明确点击“启用此方案与层”。

## 协议证据

SDK DLL 为 block-372，SHA256 `2e37239e7bd6cc7a9bf0395eae05aa9892b1544a6dace45d9f009b7bc131bd48`。REA/Ghidra 完整 Evidence 保留为同目录 JSON：

- [模式导出函数](studio-light-mode.json)，内部构包函数 [FUN_18001a400](studio-mode-inner.json)：`01 0b 88 04 01 00 <mode>`。
- [全亮亮度导出函数](studio-brightness.json)，内部构包函数 [FUN_18001a650](studio-brightness-inner.json)：`01 0b 88 04 02 00 00 <level>`。
- [读取参数](studio-light-get.json)：`01 0b 88 01`。
- [设置页模式回显](studio-light-ui.json)：模式 0 禁用亮度控件。主程序反汇编 `0x14011899c–0x1401189dd` 注册全亮=1、全灭=0、工作=2；`0x140118a85–0x140118ad6` 设置亮度滑块 0–20，`0x14011cf17–0x14011cfa1` 按模式分发亮度。

仅使用厂商 HID interface 03 写入，interface 02 保持只读。沿用项目 TEA 编码，64 字节报文。请求按队列间隔 120 ms 发送，接口不接受任意报文字节。

回读 `81 0b 88 11 00 00 <mode> <allOnBrightness> ...` 更新设备实际参数。写入确认 `...14` 不作为完整参数回读。只有后续全参数回读与请求模式、亮度同时一致时才显示已确认；5 秒未匹配显示超时，不伪造成功。设备断开时清除参数和操作状态，不自动重放灯效。

当前只控制模式和全亮模式亮度。工作模式中的各状态颜色、呼吸参数，以及 AI 状态同步尚未接入；选择工作模式会保留这些设备已有参数。

## 电量与实机验证

只读请求 `01 01 02 01`；响应 `81 01 02 11` 的 byte 4–5 为小端毫伏、6–7 为小端百分数、10 为充电标志。沿用已有解码器；与 [Olanzi 协议证据](https://github.com/MrCroxx/olanzi/blob/main/docs/02-vibekey-protocol.md) 一致。在线状态请求 `06 03 0a 01`，响应 byte 4 为在线标志。

连接时及每 20 秒查询在线、电量、灯效，设置页可手动刷新。未收到响应显示未知，不由电压估计百分比。待机/断连清除旧电量。实机返回 70%、约 3.85 V、未充电。

[实机灯效记录](au05-light-live-test.json)：原模式 1、亮度 7；依次设置模式 0、2、1，再亮度 8，最终恢复模式 1、亮度 7；五次均由全参数回读确认。未做目视光照强度测量。

不发送 `06 01 23 00 01` Studio 心跳，不改写按键表、配对、睡眠或固件，保持已确认的标准 HID 输入路径。
