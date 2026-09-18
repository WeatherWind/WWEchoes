# 技术栈：Python 3.11+ / PySide6

产品需要屏幕捕获（WGC）、中文 OCR（PP-OCR 系 ONNX）、OpenCV 模板匹配三层能力。选定 Python + PySide6：三块生态全有成熟库，ok-ww / MCEchoSys 为同领域同栈先例；核心逻辑（识别、评分、UI）在任何平台可开发测试。

> 2026-09-18 补充：协作模式为**双机跨对话**——macOS 会话负责纯逻辑/评分引擎/文档，Windows 会话负责截屏、悬浮窗、ROI 实测与打包验证（"macOS 无法开发"不再是本决策的主要依据，但决策不变：Python 仍是三层生态与社区先例的最优解）。

## Considered Options

- **C# WPF + WGC + ONNX**：体积与系统集成最优，但 WPF 仅 Windows 可运行，mac 开发环境无法验证，迭代受阻。
- **C++ / ImGui（参考项目 WWMAP-TOOLS 路线）**：性能最佳，开发与维护成本最高，首发不值得。

## Consequences

- 分发体积大（PySide6 + ONNX Runtime + 模型，单 exe 预计 60–150 MB），PyInstaller 有杀软误报史，需签名/白名单申诉缓解。
- PyInstaller 无法交叉编译：Windows 打包走 GitHub Actions Windows runner（仓库本就计划公开），Release 产物即测试包。
