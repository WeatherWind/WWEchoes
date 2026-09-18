"""Windows 悬浮窗（占位，Windows 会话实现）。

实现要点（来自 WWMAP-TOOLS / IMao 调研结论）：
- Qt 侧：``WindowStaysOnTopHint | FramelessWindowHint | Tool`` +
  ``WA_TranslucentBackground``（真 alpha，不用色键）；
- Win32 侧（ctypes SetWindowLongW GWL_EXSTYLE 追加）：
  ``WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW``，
  显示用 ``SW_SHOWNOACTIVATE``，所有 SetWindowPos 带 ``SWP_NOACTIVATE``；
- 位置：默认屏幕右上角（设置可配置角落与缩放），不跟随游戏窗口逐帧移动
  （决策：固定角落）；进程需 PerMonitorV2 DPI 感知；
- 性能：内容不变不重绘（参考 WWMAP-TOOLS 的 Present 跳过策略），
  离开装配页整窗 hide；
- 焦点校验：仅当游戏窗口前台（GetForegroundWindow == 游戏 HWND）时显示。
"""

from __future__ import annotations


class OverlayWindow:
    def __init__(self) -> None:
        raise NotImplementedError("待 Windows 会话实现")
