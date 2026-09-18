# WWEchoes — 鸣潮声骸实时评分悬浮工具

进入《鸣潮》「角色 - 声骸」装配页时，WWEchoes 在游戏上方以透明置顶悬浮窗实时显示当前声骸的词条权重评分（250 分制 SSS~C），并提供本角色 5 槽位汇总条。

## 合规声明

WWEchoes 是**只读截图**工具：不读取游戏内存、不注入进程、不修改游戏文件、**不模拟任何键鼠输入**；仅通过窗口枚举与画面截图 + OCR 实现识别（详见 `docs/adr/0003-只读截图合规边界.md`）。使用第三方工具的封号风险由用户自担。

## 使用要求

- Windows 10 1809+ / 国服简中客户端
- Windows 10 1809+ / 国服简中客户端
- 游戏显示模式用**窗口**或全屏均可（若全屏下工具无反应，请切换为「窗口」模式）、16:9 分辨率（v1 以 1920×1080 为基准）
- 下载 Release 中的 exe（PyInstaller onefile 打包，首次启动需解压，稍慢）

## 开发

```bash
pip install -e .[dev]
pytest          # 评分引擎 / ROI / 解析器单测（macOS 与 Windows 均可跑）
ruff check src tests
```

双机跨对话协作模式见 `AGENTS.md`「协作模式」一节：macOS 会话负责纯逻辑与 UI 骨架，Windows 会话负责截屏/悬浮窗/ROI 实测。开始任何工作前请先阅读 `AGENTS.md` 与 `CONTEXT.md`。

## 许可证与致谢

- 本项目采用 [GPL-3.0](./LICENSE)。
- 声骸评分公式与词条数值表移植自 [WutheringWavesUID](https://github.com/CM-Edelweiss/WutheringWavesUID)（GPL-3.0），角色配置数据的来源与快照记录见 `src/wwechoes/scoring/data/SOURCE.md`。
- 悬浮窗窗口样式参考了 [WWMAP-TOOLS](https://github.com/kahvia-d/WWMAP-TOOLS) 与 [IMao-Wuthering-Waves](https://github.com/Yepin2022/IMao-Wuthering-Waves)（均为 GPL-3.0）的技术思路。
