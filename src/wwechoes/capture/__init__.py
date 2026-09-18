"""画面捕获后端接口。

实现约束（Windows 会话）：优先 Windows Graphics Capture（按 HWND 捕获、
可遮挡、可控帧间隔），失败回退 DXGI Desktop Duplication；不得使用会写
注册表或注入游戏的方式。所有后端只读截图，遵守 ADR-0003 合规边界。
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np

Frame = np.ndarray
FrameCallback = Callable[[Frame], None]


class CaptureBackend(ABC):
    """按帧回调推送游戏客户区画面（BGR）。"""

    @abstractmethod
    def start(self, on_frame: FrameCallback) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


def create_backend() -> CaptureBackend:
    """工厂：Windows 下返回 WGC 后端；其余平台抛错（捕获仅限 Windows 实测）。"""
    if sys.platform == "win32":
        from .win_wgc import WgcCaptureBackend

        return WgcCaptureBackend()
    raise RuntimeError("画面捕获仅支持 Windows（本环境用于纯逻辑开发与单测）")
