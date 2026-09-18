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
        anchor_pos: tuple[int, int] | None = None,
    ) -> None:
        """anchor_pos: 参考矩形（游戏客户区）内的自定义锚点（客户区坐标，
        悬浮窗左上角位置），设置后优先于 corner（用户标注的背包旁空档位）。"""
        if QApplication.instance() is None:
            raise RuntimeError("OverlayWindow 需要先创建 QApplication")
        self._corner = corner
        self._margin = margin_px
        self._anchor_pos = anchor_pos
        self._reference: tuple[int, int, int, int] | None = None
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

    def _place_corner(self, reference: tuple[int, int, int, int] | None = None) -> None:
        """把窗口放到角落。

        reference: 参考矩形 (x, y, w, h) 屏幕坐标——默认游戏客户区，悬浮窗
        贴其角落内侧（窗口模式下游戏不铺满屏幕，贴屏幕角落会跑到游戏外）；
        无参考时回落屏幕可用区。
        """
        if reference is not None:
            rx, ry, rw, rh = reference
        else:
            screen = self.widget.screen() or QApplication.primaryScreen()
            geo = screen.availableGeometry()
            rx, ry, rw, rh = geo.x(), geo.y(), geo.width(), geo.height()
        size = self.widget.size()
        if self._anchor_pos is not None:
            # 自定义锚点：ax 为左缘、ay 为**底边**目标（下边界与声骸列表
            # 底边平齐的定位语义），夹取在参考矩形内
            ax, ay = self._anchor_pos
            x = min(max(rx + ax, rx), max(rx + rw - size.width(), rx))
            y = min(max(ry + ay - size.height(), ry), max(ry + rh - size.height(), ry))
            self.widget.move(x, y)
            return
        m = self._margin
        left = self._corner in (Corner.TOP_LEFT, Corner.BOTTOM_LEFT)
        top = self._corner in (Corner.TOP_RIGHT, Corner.TOP_LEFT)
        x = rx if left else rx + rw - size.width() - m
        y = ry + m if top else ry + rh - size.height() - m
        self.widget.move(x, y)

    # --- 显隐（不抢焦点）---

    def set_anchor_pos(self, pos: tuple[int, int]) -> None:
        """运行时更新锚点（托盘微调用），可见时立即重定位。"""
        self._anchor_pos = pos
        if self._visible:
            self._reference = getattr(self, "_reference", None)
            if self._reference is not None:
                self._place_corner(self._reference)

    def show_no_activate(self, reference: tuple[int, int, int, int] | None = None) -> None:
        """显示悬浮窗（不抢焦点）；reference 为定位参考矩形（游戏客户区）。"""
        self._reference = reference
        if self._visible:
            return
        self._ensure_native()
        self._place_corner(reference)
        self.widget.show()
        if self._hwnd is not None:
            _USER32.ShowWindow(self._hwnd, _SW_SHOWNOACTIVATE)
        self._visible = True

    def reposition(self, reference: tuple[int, int, int, int]) -> None:
        """参考矩形（游戏客户区）移动时重新定位（仅 move，不重绘内容）。"""
        self._reference = reference
        if not self._visible:
            return
        self._place_corner(reference)

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
