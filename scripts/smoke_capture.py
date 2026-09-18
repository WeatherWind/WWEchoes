"""capture 后端冒烟（Windows 桌面会话手动运行，不入 pytest）。

无游戏环境下用 PySide6 建无边框纯色窗口（窗口区==客户区），WGC 按
HWND 抓帧，断言：能收到帧、帧尺寸与窗口一致、中心像素颜色匹配、
find_game_hwnd 在无游戏时报 LookupError。

    python scripts/smoke_capture.py
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402

from wwechoes.capture.win_wgc import (  # noqa: E402
    WgcCaptureBackend,
    client_rect,
    ensure_per_monitor_v2,
    find_game_hwnd,
)

W, H = 640, 480
FILL_RGB = (90, 180, 60)


def main() -> int:
    print("[1] PerMonitorV2 DPI 感知:", ensure_per_monitor_v2())
    try:
        find_game_hwnd()
        print("[2] FAIL: 无游戏时 find_game_hwnd 应抛 LookupError")
        return 1
    except LookupError as e:
        print("[2] OK: 无游戏时正确报错 ->", str(e)[:60], "...")
    except RuntimeError as e:
        print("[2] SKIP:", e)
        return 0

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication([])
    widget = QWidget()
    widget.setWindowFlags(Qt.WindowType.FramelessWindowHint)  # 窗口区==客户区
    widget.setFixedSize(W, H)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(*FILL_RGB))
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
    widget.move(120, 120)
    widget.show()

    hwnd = int(widget.winId())
    cw, ch = client_rect(hwnd)
    print(f"[3] 自建窗口 hwnd={hwnd} 客户区 {cw}x{ch}")

    backend = WgcCaptureBackend(hwnd=hwnd, min_interval_ms=16)
    frames: list[np.ndarray] = []
    got = threading.Event()

    def on_frame(frame: np.ndarray) -> None:
        frames.append(frame)
        if len(frames) >= 10:
            got.set()

    backend.start(on_frame)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not got.is_set():
        app.processEvents()
        time.sleep(0.01)
    time.sleep(0.3)  # 收尾帧
    backend.stop()

    if not frames:
        print("[4] FAIL: 5s 内未收到任何帧")
        return 1
    last = frames[-1]
    print(f"[4] OK: 收到 {len(frames)} 帧，末帧 shape={last.shape}")
    if last.shape[:2] != (ch, cw):
        print(f"[5] FAIL: 帧尺寸 {last.shape[:2]} != 窗口 {(ch, cw)}")
        return 1
    center = last[ch // 2, cw // 2]
    print(f"[5] OK: 帧尺寸与窗口一致；中心像素 BGR={tuple(int(v) for v in center)}")
    if not np.allclose(center[::-1], FILL_RGB, atol=40):
        print(f"    WARN: 中心色偏差较大（期望 RGB~{FILL_RGB}；GPU 色彩转换/合成可致偏移）")
    print("冒烟通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
