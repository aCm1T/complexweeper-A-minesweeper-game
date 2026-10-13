# Complexweeper 1.2.0-linux.1 · Linux 社区预览版

基于 [Yueqing-Chen/complexweeper-A-minesweeper-game](https://github.com/Yueqing-Chen/complexweeper-A-minesweeper-game) 的 v1.2.0（提交 e225219ce5d331f717eaead80200ecb64d01746e）制作的社区 Linux 移植版。

提供 GTK 3 原生窗口，保留圆复数与双曲复数模式、原版 Zig 规则、像素图集和音效。支持标准难度、自定义四种雷配比、1–3 倍缩放、成绩保存及结局复盘。

## 下载与运行

解压 `complexweeper-1.2.0-linux.1-x86_64.tar.gz`，在解压目录运行 `./complexweeper`。系统需提供 Python 3、PyGObject、PyCairo 和 GTK 3；音效需要 GStreamer WAV 播放插件。完整依赖及构建说明见包内 `README-Linux.md`。

包内包含 x86_64 Linux 基线指令集二进制、全部源码、构建脚本与 GPL-3.0 授权文件。无需 Wine 或 Zig 运行时。

## 发布审查与验证

- 已修复原先本机编译引入 AVX-512 指令的兼容性问题，改为 `x86_64-linux-gnu` / `baseline` 构建，并检查两个 ELF 产物的指令与私有路径。
- 原有 Windows 自动发布任务已排除 Linux 标签，避免混入 Windows 附件或错误标记为最新正式版。
- 原版 58 项规则断言与新增 10 组 Linux 回归测试通过。
- X11、Wayland 各 31 项真实窗口检查通过。
- 全部六段原版 WAV 经 GStreamer 完整解码到测试输出。
- 保留上游署名、完整源码及原素材授权说明；打包时排除缓存、个人设置和编译中间文件。

已验证的发行版为 Fedora 44。物理扬声器及 Ubuntu / Debian 尚未实测。新增 GitHub Actions 工作流已准备，远端验证状态以 Release 页面和仓库 Actions 记录为准。本发行建议标记为 **Pre-release**。

规则主体 `game.zig` 与上游逐字节一致。Linux 接口补充了极密自定义棋盘首击翻完全部安全格时立即判胜的边界行为。原版 Windows 入口保留，素材权利说明沿用上游。

## 校验

下载相应 `.sha256` 文件，与压缩包放在同一目录，运行：

```bash
sha256sum -c complexweeper-1.2.0-linux.1-x86_64.tar.gz.sha256
```

包内 `SHA256SUMS` 可进一步校验源码及二进制文件。
