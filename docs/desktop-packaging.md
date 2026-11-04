# 桌面封装与兼容范围评估

本轮仅调整网页控制台的排版和样式，继续使用 Python 后台与本地网页。没有引入 Electron 或增加现有安装包的运行依赖。独立的 `web/workbench.css` 随安装包发布，界面无需更换框架即可采用设备中心布局。

## Electron 对安装的影响

Electron 把 Chromium 和 Node.js 打入应用二进制，用户不需要另外安装 Node.js。相比目前依靠用户浏览器显示的轻量安装包，增加 Electron 壳会增加下载体积、安装占用和运行时进程。实际体积应在完成封装后测量，本项目目前没有 Electron 构建，不能给出实测包大小。

Linux 仍需要平台系统库。electron-builder 的稳定版 v26 文档列出的常见 DEB 依赖包括 GTK3、NSS、libnotify、X11 扩展、辅助功能库、UUID、Secret Service 及 xdg-utils。很多桌面系统已安装其中一部分，实际缺少哪些取决于用户系统及功能选择。打包时还要处理发行版之间的库名称和版本差异。

无论使用哪种界面，本项目的 Python 运行时、udev/hidraw 与 uinput 权限、输入法和语音组件仍然需要处理；它们不会因引入 Electron 而消失。

## 跨系统版本

Electron 支持 Windows、macOS 和 Linux 的相应架构，但每个平台和架构需要对应构建。官方平台支持随 Electron/Chromium 和发行版支持周期变化，不是任意新旧系统均可运行。

针对本项目，可以把 Ubuntu 20.04、22.04、24.04 的 x86_64 桌面列为待验证矩阵。当前仅在本机 Ubuntu 20.04.6 的现有 Python/浏览器架构下实测，尚未验证这些系统的 Electron 构建，也没有将它们标记为已支持。Ubuntu 20.04 上使用哪个 Electron 版本，需要以该版本官方支持范围、动态库基线和真实运行测试决定。

DEB 适合 Debian/Ubuntu 系；AppImage 可以减少安装步骤，但不会消除系统库、内核和桌面环境约束。Flatpak 也需要对硬件访问、后台服务与输入法集成专门设计。

当前输入后端依赖 Linux hidraw、evdev、uinput 和 X11 窗口属性。迁移到 Windows/macOS 时，Electron 可复用界面，设备输入、权限、窗口识别和文本交付需实现相应平台后端。Wayland 的自动跟随也需要独立的桌面集成。

建议保留轻量网页版作为兼容基础；确实需要独立窗口、托盘或桌面发布体验时，再增加可选 Electron 壳，并用共享后台保持行为一致。

参考：

- [Electron 官方介绍](https://www.electronjs.org/docs/latest/)
- [Electron 平台支持](https://github.com/electron/electron/blob/main/README.md#platform-support)
- [electron-builder v26 Linux 打包与依赖](https://www.electron.build/v26/docs/linux/)
- [Work Louder Input](https://worklouder.cc/input)
