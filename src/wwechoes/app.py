"""应用入口编排（骨架）。

管线：capture(帧) -> detect(页面状态) -> [DETAIL 态] ocr(详情面板词条)
-> scoring(评分) -> overlay(悬浮窗)。

本模块当前只完成可移植部分的装配契约；capture / overlay 的 Windows
实现与热键、托盘由 Windows 会话补齐（各占位模块内注明要点）。
合规红线（ADR-0003）：任何环节不得引入内存读取/注入/输入模拟。
"""

from __future__ import annotations

import sys


def main() -> int:
    if sys.platform != "win32":
        print(
            "WWEchoes 运行时仅支持 Windows。\n"
            "开发提示：mac 会话请跑 pytest / ScoreCard 预览（python -m wwechoes.overlay.view）",
            file=sys.stderr,
        )
        return 1
    # TODO(Windows 会话): 装配 capture -> detect -> ocr -> scoring -> overlay 管线，
    # 托盘 + RegisterHotKey 热键，主窗口（设置/手动选角色）。
    raise NotImplementedError("Windows 运行时待 Windows 会话实现")
