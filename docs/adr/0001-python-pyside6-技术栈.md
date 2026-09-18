# 技术栈：Python 3.11+ / PySide6

开发环境是 macOS，目标平台只有 Windows，产品需要屏幕捕获（WGC）、中文 OCR（PP-OCR 系 ONNX）、OpenCV 模板匹配三层能力。选定 Python + PySide6：三块生态全有成熟库，且核心逻辑（识别、评分、UI）可在 macOS 上开发调试，只有 Win32 窗口样式与捕获等薄层需 Windows 实测；ok-ww / MCEchoSys 为同领域同栈先例。

## Considered Options

- **C# WPF + WGC + ONNX**：体积与系统集成最优，但 WPF 仅 Windows 可运行，mac 开发环境无法验证，迭代受阻。
- **C++ / ImGui（参考项目 WWMAP-TOOLS 路线）**：性能最佳，开发与维护成本最高，首发不值得。

## Consequences

- 分发体积大（PySide6 + ONNX Runtime + 模型，单 exe 预计 60–150 MB），PyInstaller 有杀软误报史，需签名/白名单申诉缓解。
- PyInstaller 无法交叉编译：Windows 打包走 GitHub Actions Windows runner（仓库本就计划公开），Release 产物即测试包。
