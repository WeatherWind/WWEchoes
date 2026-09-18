"""Windows 悬浮窗：透明、置顶、点击穿透、不抢焦点（实现版）。

配方（两个参考项目实证，见 docs/research/2026-09-18）：
- Qt 侧：``WindowStaysOnTopHint | FramelessWindowHint | Tool`` +
  ``WA_TranslucentBackground``（真 alpha）+ ``WA_ShowWithoutActivating``；
- Win32 侧（创建原生句柄后 ``SetWindowLongW`` 追加 GWL_EXSTYLE）：
  ``WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW``，
  显示用 ``SW_SHOWNOACTIVATE``；
- 位置：屏幕右上角固定（v1 决策：不跟随游戏窗口移动）；
- 性能：内容不变不重绘（Qt 静态内容自然不重绘），离开装配页整窗 hide；
- 焦点校验由 app 层做（GetForegroundWindow == 游戏 HWND 才调 show）。

合规（ADR-0003）：纯展示窗口，全点击穿透，不含任何输入模拟。
"""

from __future__ import annotations

import ctypes
import sys
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TOOLWINDOW = 0x00000080
_SW_SHOWNOACTIVATE = 4

_USER32 = ctypes.WinDLL("user32", use_last_error=True) if sys.platform == "win32" else None

#: 需要追加的扩展样式全集（悬浮窗合规配方）
_OVERLAY_EXSTYLE = _WS_EX_LAYERED | _WS_EX_TRANSPARENT | _WS_EX_NOACTIVATE | _WS_EX_TOOLWINDOW


class Corner(Enum):
    """悬浮窗固定角落（v1：默认右上）。"""

    TOP_RIGHT = "top_right"
    TOP_LEFT = "top_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"


def _apply_win32_overlay_styles(hwnd: int) -> bool:
    """给 HWND 追加悬浮窗扩展样式位；返回是否全部就位。"""
    exstyle = _USER32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    _USER32.SetWindowLongW(hwnd, _GWL_EXSTYLE, exstyle | _OVERLAY_EXSTYLE)
    # SetWindowPos 带 SWP_FRAMECHANGED 使样式立即生效
    # 标志：NOMOVE|NOSIZE|NOZORDER|NOACTIVATE|FRAMECHANGED
    swp_flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0400
    _USER32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, swp_flags)
    return (_USER32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _OVERLAY_EXSTYLE) == _OVERLAY_EXSTYLE


class OverlayWindow:
    """承载 ScoreCard 的无边框透明置顶穿透窗口（每屏角落固定）。

    使用前提：QApplication 已创建且处于主线程；工作线程通过信号间接
    驱动 show/hide（Qt 跨线程 GUI 调用禁止）。
    """

    def __init__(
        self,
        content: QWidget | None = None,
        corner: Corner = Corner.TOP_RIGHT,
        margin_px: int = 16,
    ) -> None:
        if QApplication.instance() is None:
            raise RuntimeError("OverlayWindow 需要先创建 QApplication")
        self._corner = corner
        self._margin = margin_px
        self._visible = False

        self.widget = content if content is not None else QWidget()
        self.widget.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._win32_ok = False
        self._hwnd: int | None = None

    # --- 样式与位置 ---

    def _ensure_native(self) -> None:
        """创建原生句柄并应用 Win32 扩展样式（幂等）。"""
        if self._hwnd is not None:
            return
        self._hwnd = int(self.widget.winId())
        self._win32_ok = _apply_win32_overlay_styles(self._hwnd)

    def _place_corner(self) -> None:
        screen = self.widget.screen() or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        size = self.widget.size()
        m = self._margin
        x = {
            Corner.TOP_RIGHT: geo.right() - size.width() - m,
            Corner.TOP_LEFT: geo.left() + m,
            Corner.BOTTOM_RIGHT: geo.right() - size.width() - m,
            Corner.BOTTOM_LEFT: geo.left() + m,
        }[self._corner]
        y = {
            Corner.TOP_RIGHT: geo.top() + m,
            Corner.TOP_LEFT: geo.top() + m,
            Corner.BOTTOM_RIGHT: geo.bottom() - size.height() - m,
            Corner.BOTTOM_LEFT: geo.bottom() - size.height() - m,
        }[self._corner]
        self.widget.move(x, y)

    # --- 显隐（不抢焦点）---

    def show_no_activate(self) -> None:
        if self._visible:
            return
        self._ensure_native()
        self._place_corner()
        self.widget.show()
        if self._hwnd is not None:
            _USER32.ShowWindow(self._hwnd, _SW_SHOWNOACTIVATE)
        self._visible = True

    def hide(self) -> None:
        if not self._visible:
            return
        self.widget.hide()
        self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def hwnd(self) -> int | None:
        return self._hwnd

    @property
    def win32_styles_ok(self) -> bool:
        """Win32 悬浮样式位是否全部就位（冒烟/自检用）。"""
        if self._hwnd is None:
            return False
        exstyle = _USER32.GetWindowLongW(self._hwnd, _GWL_EXSTYLE)
        return (exstyle & _OVERLAY_EXSTYLE) == _OVERLAY_EXSTYLE
