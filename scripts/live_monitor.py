"""真机实时监控：抓帧 -> 状态转换日志 -> DETAIL 时跑完整识别评分链路。

用法：python scripts/live_monitor.py [秒数]
配合用户在游戏内操作：进装配页 -> 点开声骸详情 -> 换槽位 -> 退出。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0

from wwechoes.app import SLOT_COST  # noqa: E402
from wwechoes.capture.win_wgc import (  # noqa: E402
    WgcCaptureBackend,
    ensure_per_monitor_v2,
    find_game_hwnd,
)
from wwechoes.detect import PageState, detect_slot, observe_page  # noqa: E402
from wwechoes.ocr.engine import OcrEngine  # noqa: E402
from wwechoes.scoring import Echo  # noqa: E402
from wwechoes.scoring.engine import score_echo_for_character  # noqa: E402

ensure_per_monitor_v2()
hwnd = find_game_hwnd()
print(f"[monitor] 游戏 hwnd={hwnd}，监控 {DURATION:.0f}s，请开始操作…", flush=True)

backend = WgcCaptureBackend(hwnd=hwnd, min_interval_ms=100)
frames: list = []
lock = threading.Lock()


def on_frame(f):
    with lock:
        frames.append(f)
        if len(frames) > 300:
            del frames[:100]


backend.start(on_frame)

ocr = OcrEngine()
t0 = time.monotonic()
last_state = None
last_slot = None
detail_count = 0
state_hist: Counter = Counter()

from wwechoes.detect.roi import DETAIL_MAIN_STATS, DETAIL_SUB_STATS  # noqa: E402

while time.monotonic() - t0 < DURATION:
    time.sleep(0.15)
    with lock:
        if not frames:
            continue
        frame = frames[-1]
    state = observe_page(frame)
    state_hist[state.name] += 1
    if state is not last_state:
        t = time.monotonic() - t0
        print(f"[{t:6.1f}s] 状态: {last_state and last_state.name} -> {state.name}", flush=True)
        last_state = state
    if state is PageState.DETAIL:
        slot = detect_slot(frame)
        if slot is not None and slot != last_slot:
            last_slot = slot
            detail_count += 1
            mains = ocr.read_stats(frame, DETAIL_MAIN_STATS)
            subs = ocr.read_stats(frame, DETAIL_SUB_STATS)
            echo = Echo(cost=SLOT_COST[slot], main_stats=tuple(mains), sub_stats=tuple(subs))
            es, _ = score_echo_for_character(echo, "default")
            print(
                f"        DETAIL slot={slot} 主{len(mains)} 副{len(subs)}"
                f" -> {es.score:g} {es.grade.upper()}  "
                f"主={[f'{m.name}{m.value:g}' for m in mains]} "
                f"副={[f'{s.name}{s.value:g}' for s in subs]}",
                flush=True,
            )
            import cv2

            path = f"docs/assets/raw/live_detail_{slot}_{detail_count}.png"
            cv2.imencode(".png", frame)[1].tofile(path)
    else:
        last_slot = None

backend.stop()
print(f"\n[monitor] 结束：状态分布 {dict(state_hist)}，DETAIL 触发 {detail_count} 次", flush=True)
