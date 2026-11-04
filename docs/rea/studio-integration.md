# Studio 本地集成（2026-11-04）

## 已接入

- 官方 AU05 设备插画作为键位工作台背景，保留四个原生按钮的焦点、点击和实时状态。
- “打开网站”动作：HTTP(S) 地址，经 `xdg-open` 交给默认浏览器；支持按键、旋转、宏、导入导出及宏 Code。模拟模式仅报告事件。
- Debian 构建复制图片资源。未自动安装或推送。

网站功能的静态依据是安装器块 103 的 System manifest，动作 UUID
`com.ulanzi.ulanzideck.system.website`，未声明 Devices 限制。
Linux 实现是独立实现；未运行 Windows 程序，未证明官方实际执行路径或设备支持语义。

## 图片身份与提取

安装器 SHA-256：`72cc5c89f85941522a906dfd2bc77fd32e0416aa261fc96177ea3a6be7e4caa9`。
块 370 为 `UlanziDeck.exe`，块映射见 `studio-filenames.json`。
Qt 名称表位于 EXE 文件偏移 `0xaba560`，树位于 `0xabb280`，
节点宽度 22 字节，数据表位于 `0x6abd70`。
遍历树恢复 92 个文件。目标为 `profileui/images/vibekey.png`，
EXE 字节偏移 7323751，长度 180751，尺寸 188 × 692。
图片 SHA-256：`2d3c4095da2b004ebb985a3efdee12b5423d582e767d850b353febd6e42ebd3a`。
资源由普通 Python 静态解析恢复，属于 shell 证据，不是 REA 反编译结论。
原图保存在 `web/assets/studio/vibekey.png`；许可边界见 THIRD_PARTY.md。

## REA 验证

REA CLI 6.7.0 / Ghidra 12.1.4 成功分析 `Ulanzi_Studio.dll`：
Evidence `ev_46fff64ff41fe387598ef783c81a35d94fecffcc42dbd99c657e553615b0cf62`，
1934 个过程、1231 个字符串，完整记录见 `studio-dll-overview.json`。
这仅验证 native 分析可用，未据此推出 HID 写入协议。

## 尚未解决

- `~AU05` 设备过滤语义尚未追踪；未把 OBS、灯光等清单当作 AU05 功能。
- 后续已验证灯光模式、全亮亮度及电量读取，详见 [预设与灯效记录](presets-and-lighting.md)。保活、固件更新和键表写入仍未启用。
- 文件名映射已覆盖 743 个负载块，但安装器目录切换未完整重建。
- 已恢复的图片资源不等于已获再分发授权；本轮未推送或发布。

## 本轮验收

Python unittest 60 项、Node 模型测试 10 项通过。Chrome 集成测试通过，
新增检查覆盖图片 HTTP 加载、URL 编辑和保存；桌面及 390px 窄屏无横向溢出。
已人工查看桌面截图。Debian 包构建成功，包含图片和来源说明，依赖声明包含
提供 `xdg-open` 的 `xdg-utils`。未进行系统安装、浏览器实际启动或硬件动作验收。

## 实机结果（2026-11-04）

设备 AU05，序列号 `202609081030`，X11 会话。
安装 AU05 udev 规则并重新插入后，hidraw/evdev 连接正常。
用户确认上键单击成功打开测试网页，顺/逆时针音量及旋钮静音切换正常。
用户表示宏此前已验证，本轮撤掉临时宏，不重复验收。

该设备当前上报 `wheel:-` 对应顺时针、`wheel:+` 对应逆时针；
已在用户配置持久化修正，尚未推广为所有固件的默认映射。
当前方案为：上键打开本机网页，中/下键无动作，旋钮音量增减与静音。
本轮为源码后台实机测试，不代表 Debian 系统安装已经验收。
