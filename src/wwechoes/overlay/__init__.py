"""悬浮窗：透明、置顶、点击穿透、不抢焦点。

窗口样式配方（两参考项目实证，见 docs/research）：
``WS_POPUP | WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT
| WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW`` 配合 ``SW_SHOWNOACTIVATE`` 显示。
本包在非 Windows 平台仅提供内容视图开发预览，
Win32 扩展样式在 win_overlay.py 中仅 win32 下生效。
"""

from __future__ import annotations

import sys

from .view import ScoreCard, SummaryBar

__all__ = ["ScoreCard", "SummaryBar", "OverlayWindow"]

if sys.platform == "win32":
    from .win_overlay import OverlayWindow
else:

    class OverlayWindow:  # 开发占位：mac 上不可用，接口契约见 win_overlay
        def __init__(self) -> None:
            raise RuntimeError(
                "悬浮窗仅支持 Windows；"
                "mac 会话请用 ScoreCard 预览（python -m wwechoes.overlay.view）"
            )
