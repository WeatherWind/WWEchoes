"""Windows Graphics Capture 后端（占位，Windows 会话实现）。

参考实现要点（来自调研 docs/research/2026-09-18）：
- 库选型 ``windows-capture``（Rust 双绑定，支持按 HWND、MinimumUpdateInterval、
  去黄框 DrawBorderSettings）；
- 游戏窗口定位：进程名 ``Client-Win64-Shipping.exe`` + EnumWindows 取可见主窗口，
  校验 16:9（detect.roi.is_16_9）；
- DPI：进程需 PerMonitorV2 感知，物理像素坐标对齐悬浮窗（见 overlay）。
"""

from __future__ import annotations

from . import CaptureBackend, FrameCallback

GAME_PROCESS_NAME = "Client-Win64-Shipping.exe"


class WgcCaptureBackend(CaptureBackend):
    def __init__(self) -> None:
        raise NotImplementedError("待 Windows 会话实现：windows-capture 接入与窗口定位")

    def start(self, on_frame: FrameCallback) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
