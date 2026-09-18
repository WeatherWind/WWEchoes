"""Windows Graphics Capture 后端（windows-capture 库，Rust 双绑定）。

实现要点（来自调研 docs/research/2026-09-18 与 M0 骨架注记）：
- 窗口定位：进程名 ``Client-Win64-Shipping.exe`` + EnumWindows 取可见
  主窗口（客户区最大者），校验 16:9 由调用方按帧尺寸做（roi.is_16_9）；
- ``draw_border=False`` 去除捕获黄框；``minimum_update_interval`` 限帧率
  （页面检测 30fps 足够，降低 CPU/功耗）；
- 帧回调里的 ``frame_buffer`` 是原生内存的零拷贝视图，回调返回后失效，
  必须 ``.copy()`` 深拷贝后再交给管线；
- DPI：进程需 PerMonitorV2 感知（``ensure_per_monitor_v2``，须在创建
  任何窗口前调用），保证物理像素坐标与悬浮窗对齐。

合规（ADR-0003）：仅按 HWND 只读捕获画面，不读内存、不注入、不模拟输入。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import threading
from collections.abc import Callable

import numpy as np

from . import CaptureBackend, FrameCallback

GAME_PROCESS_NAME = "Client-Win64-Shipping.exe"

_USER32 = ctypes.WinDLL("user32", use_last_error=True) if sys.platform == "win32" else None
_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None

# --- Win32 常量（按需小集合）---
_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_WS_VISIBLE = 0x10000000
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_DWMWA_CLOAKED = 14


def ensure_per_monitor_v2() -> bool:
    """设置进程 PerMonitorV2 DPI 感知（须在任何窗口创建前调用）。

    返回是否设置成功；失败时进程为系统默认感知，坐标可能被虚拟化，
    由调用方决定是否告警。Windows 10 1703+ 支持 -4 上下文。
    """
    if _USER32 is None:
        return False
    return bool(_USER32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))


def _query_process_name(pid: int) -> str:
    """PID -> 进程映像名（QueryFullProcessImageNameW，只读查询）。"""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = _KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buf))
        ok = _KERNEL32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        return buf.value.rsplit("\\", 1)[-1] if ok else ""
    finally:
        _KERNEL32.CloseHandle(handle)


def _is_cloaked(hwnd: int) -> bool:
    """UWP 挂起窗口等'隐形'窗口（DWM cloaked），应排除。"""
    value = wt.DWORD(0)
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wt.HWND(hwnd), _DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
        )
    except OSError:
        return False  # 无 DWM 环境按未隐藏处理
    return bool(value.value)


def find_game_hwnd(process_name: str = GAME_PROCESS_NAME) -> int:
    """枚举顶层可见窗口，返回目标进程中客户区最大者的 HWND。

    找不到时抛 LookupError（游戏未运行）。
    """
    if _USER32 is None:
        raise RuntimeError("窗口枚举仅支持 Windows")

    matches: list[tuple[int, int]] = []  # (客户区面积, hwnd)

    def enum_proc(hwnd: int, _lparam: int) -> bool:
        if not _USER32.IsWindowVisible(hwnd):
            return True
        style = _USER32.GetWindowLongW(hwnd, _GWL_STYLE)
        exstyle = _USER32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        if not style & _WS_VISIBLE or exstyle & _WS_EX_TOOLWINDOW:
            return True
        if _is_cloaked(hwnd):
            return True
        pid = wt.DWORD(0)
        _USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _query_process_name(pid.value).lower() != process_name.lower():
            return True
        rect = wt.RECT()
        _USER32.GetClientRect(hwnd, ctypes.byref(rect))
        area = max(rect.right - rect.left, 0) * max(rect.bottom - rect.top, 0)
        if area > 0:
            matches.append((area, hwnd))
        return True

    _USER32.EnumWindows(ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(enum_proc), 0)
    if not matches:
        raise LookupError(
            f"未找到进程 {process_name} 的可见窗口：游戏未运行，或以独占全屏运行"
            "（独占全屏下 WGC 无法捕获，请以无边框窗口运行游戏）"
        )
    matches.sort(reverse=True)
    return matches[0][1]


def client_rect(hwnd: int) -> tuple[int, int]:
    """窗口客户区尺寸 (width, height)，物理像素。"""
    rect = wt.RECT()
    _USER32.GetClientRect(hwnd, ctypes.byref(rect))
    return rect.right - rect.left, rect.bottom - rect.top


class WgcCaptureBackend(CaptureBackend):
    """按 HWND 推送游戏客户区帧（BGR uint8）的自由线程 WGC 后端。"""

    def __init__(self, hwnd: int | None = None, min_interval_ms: int = 33) -> None:
        try:
            from windows_capture import WindowsCapture
        except ImportError as exc:  # pragma: no cover - 依赖缺失属环境问题
            raise RuntimeError("缺少 windows-capture 依赖（pip install windows-capture）") from exc
        self._hwnd = hwnd if hwnd is not None else find_game_hwnd()
        self._interval = min_interval_ms
        self._control = None
        self._lock = threading.Lock()
        self._capture = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            minimum_update_interval=min_interval_ms,
            window_hwnd=self._hwnd,
        )
        self._on_frame_user: FrameCallback | None = None
        self._on_closed_user: Callable[[], None] | None = None

        @self._capture.event
        def on_frame_arrived(frame, capture_control):  # noqa: ANN001 - 库回调签名
            if self._on_frame_user is None:
                return
            bgr = frame.convert_to_bgr().frame_buffer
            self._on_frame_user(np.array(bgr, copy=True))  # 零拷贝视图回调后失效

        @self._capture.event
        def on_closed():
            cb = self._on_closed_user
            if cb is not None:
                cb()

    @property
    def hwnd(self) -> int:
        return self._hwnd

    def start(self, on_frame: FrameCallback, on_closed: Callable[[], None] | None = None) -> None:
        """启动捕获线程（on_closed 在捕获源关闭/游戏退出时回调）。"""
        self._on_frame_user = on_frame
        self._on_closed_user = on_closed
        with self._lock:
            if self._control is not None:
                raise RuntimeError("capture 已启动")
            self._control = self._capture.start_free_threaded()

    def stop(self) -> None:
        with self._lock:
            if self._control is not None:
                self._control.stop()
                self._control = None
