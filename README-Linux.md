# 复扫雷 · Linux 原生版

基于 Complexweeper 1.2.0 的社区 Linux 移植版。保留原版 Zig 规则引擎、两种模式、像素图集与六段音效，新增 GTK 3 原生桌面界面。无需 Wine，也无需网络服务或浏览器。

上游仓库：[Yueqing-Chen/complexweeper-A-minesweeper-game](https://github.com/Yueqing-Chen/complexweeper-A-minesweeper-game)。本移植基于上游 1.2.0 源码包，对应提交 [`e225219ce5d3`](https://github.com/Yueqing-Chen/complexweeper-A-minesweeper-game/commit/e225219ce5d331f717eaead80200ecb64d01746e)。

## 开始玩

发布包包含 **x86_64 Linux** 的编译结果。二进制采用通用 x86_64 基线指令集，不要求 AVX / AVX-512。已在 Fedora 44 的 X11 与 Wayland 会话验证；其他发行版需具备下述运行依赖。

在本目录打开终端，运行：

```bash
./complexweeper
```

也可以执行同目录的 `启动复扫雷.sh`。如果文件管理器把脚本当作文本打开，使用上面的终端方式。解压压缩包后若执行权限丢失，运行 `chmod +x complexweeper 启动复扫雷.sh`。

## 操作与功能

- 左键按下预览，松开翻格；拖出棋盘再松开会取消。
- 右键循环：空 → +1 → −1 → +i / +j → −i / −j → 空。
- 中键，或左右键同时按住已翻开的数字格：预览邻格，松开尝试展开。
- 笑脸按钮或 F2：新游戏。F1：帮助。Ctrl+Q：退出。
- “圆复数”和“双曲复数”菜单各提供初、中、高三个难度及自定义棋盘。
- 自定义宽 9–40、高 9–30，可以指定四种雷的数量，也可以均分当前雷数。
- “显示”菜单支持 1、2、3 倍像素缩放；超出屏幕的棋盘可以滚动。
- 两种模式分别记录三个标准难度的最佳用时。“游戏 → 声音”控制音效。
- 胜负后保留原版复盘贴图：踩中的雷、未标的雷、正确与错误的旗帜。

首击位置及其八邻域安全。**空白与数字 0 不同**：空白才表示周围完全没有雷。展开判据通过仍可能踩雷，旗帜的位置也必须正确。胜利要求翻开所有非雷格。

成绩、缩放和声音偏好默认保存在 `${XDG_CONFIG_HOME:-~/.config}/complexweeper/preferences.json`。可以指定其他目录：

```bash
./complexweeper --config-dir ./我的设置
```

## 在另一台 Linux 电脑上运行

需要系统 Python 3、PyGObject、PyCairo 和 GTK 3。音效需要 GStreamer 及 WAV 播放插件；音频不可用时仍可玩游戏。

Fedora 的运行依赖：

```bash
sudo dnf install python3-gobject python3-cairo gtk3 gstreamer1-plugins-base gstreamer1-plugins-good
```

Ubuntu / Debian 的运行依赖：

```bash
sudo apt install python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 gir1.2-gstreamer-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good
```

安装依赖后直接运行本包，不需要安装 Zig。预编译引擎面向 x86_64；其他架构需要重新构建。Ubuntu / Debian 命令作为依赖说明，未在本次本地审查中实测。

## 重构说明

`正式版/src/game.zig` 与原版逐字节一致。Windows 的原有入口和构建脚本仍保留。

新增的 `正式版/src/linux_api.zig` 将规则封装为检查参数范围的 C ABI，编译成 `linux/libcomplexweeper.so`。Python 只负责界面、输入手势、音频和本地设置；布雷、复数计算、展开判据、翻格和胜负判定仍在原版 Zig 引擎中执行。

规则自检原先为了读取版本号而导入整个 Windows 界面，现在改为读取独立的 `version.zig`，因此可以在 Linux 运行同一套规则自检。

Linux 接口补上了一个边界行为：极密自定义棋盘若首击已翻完全部安全格，会立即判胜。没有更改复数或双曲复数的计算和展开规则。

新增源文件：

- `linux/app.py`：GTK 窗口、菜单、对话框、计时与成绩。
- `linux/controller.py`：鼠标手势与取消操作。
- `linux/render.py`：原版图集、数码管与复盘渲染。
- `linux/engine.py`：Zig 接口的类型化绑定。
- `linux/preferences.py`、`linux/sound.py`：本地设置与 GStreamer 声音。
- `linux/test_port.py`、`linux/smoke_test.py`：Linux 接口及真实窗口测试。

## 从源码构建

需要 **Zig 0.14.1**、Node.js，以及上面的 Python / GTK 运行依赖。编译器不包含在游戏包中。

```bash
ZIG=/path/to/zig ./build-linux.sh
```

脚本会生成原版图集索引、Linux 规则库、自检程序和音频文件，然后自动运行测试。Zig 使用 `ReleaseSafe` 构建，保留运行时安全检查，CPU 设置为 `baseline`。默认目标为 `x86_64-linux-gnu`；在 ARM64 Linux 本机重建时可指定 `COMPLEXWEEPER_TARGET=aarch64-linux-gnu`。

构建工具可从 [Zig 官方下载页](https://ziglang.org/download/) 获取。GTK 界面采用 [官方 DrawingArea 绘制和事件接口](https://docs.gtk.org/gtk3/class.DrawingArea.html)。

## 验证

```bash
./complexweeper --selftest
./complexweeper --smoke-test ./界面测试 --config-dir ./测试设置 --mute
```

第一条不需要桌面会话：运行原版 **58 项规则断言**及新增 **10 组 Linux 回归测试**。第二条需要桌面会话，会在真实 GTK 窗口内测试菜单、鼠标、对话框、胜负、纪录和音频解码，完成后自动关闭。测试使用指定的设置目录。

交付包的 `验证/` 保存已通过的真实窗口报告与界面截图。GStreamer 测试完整解码全部六段 WAV 到测试输出，不检测物理扬声器。

## 授权与素材

原作者：青月晓（Yueqing-Chen）。原版说明保留在 `README.md`，GPL-3.0 全文保留在 `LICENSE`。此次新增及修改的代码也按 GPL-3.0 提供；压缩包包含完整源码。

扫雷原始图像来自 Microsoft，新增图像和图标来自青月晓。原版已说明 Microsoft 图像权利不属于代码的 GPL-3.0 授权范围。本程序与 Microsoft 无隶属关系；素材说明沿用原项目，没有另行扩大素材授权。
