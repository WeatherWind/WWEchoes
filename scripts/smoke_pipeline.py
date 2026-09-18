"""端到端管线回放冒烟（Windows 本机运行，不入 pytest）。

用 docs/assets/raw/ 截图模拟帧源，驱动与 app.Pipeline 相同的
检测 -> 槽位 -> OCR -> 解析 -> 评分链路（跳过 WGC 与 GUI 部分），
验证 DETAIL 触发逻辑与评分产出。目录无素材时跳过。

    python scripts/smoke_pipeline.py
"""

from __future__ import annotations

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wwechoes.app import SLOT_COST, _parse_hotkey  # noqa: E402
from wwechoes.detect import PageState, detect_slot, observe_page  # noqa: E402
from wwechoes.detect.roi import DETAIL_MAIN_STATS, DETAIL_SUB_STATS  # noqa: E402
from wwechoes.ocr.engine import OcrEngine  # noqa: E402
from wwechoes.scoring import Echo  # noqa: E402
from wwechoes.scoring.engine import score_echo_for_character  # noqa: E402

RAW = "docs/assets/raw"


def imread(p: str) -> np.ndarray:
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def main() -> int:
    files = sorted(glob.glob(os.path.join(RAW, "*.png")))
    if not files:
        print("[skip] 无本地素材")
        return 0

    # 模拟主循环：观测 -> DETAIL 时槽位触发（与 app.Pipeline._on_frame 同构）
    ocr = OcrEngine()
    scores: dict[int, object] = {}
    character = "default"
    detail_seen = 0
    for f in files:
        frame = imread(f)
        state = observe_page(frame)
        if state is not PageState.DETAIL:
            continue
        detail_seen += 1
        slot = detect_slot(frame)
        if slot is None:
            continue
        mains = ocr.read_stats(frame, DETAIL_MAIN_STATS)
        subs = ocr.read_stats(frame, DETAIL_SUB_STATS)
        echo = Echo(cost=SLOT_COST[slot], main_stats=tuple(mains), sub_stats=tuple(subs))
        echo_score, _ = score_echo_for_character(echo, character)
        scores[slot] = echo_score
        print(
            f"  {os.path.basename(f)[:46]:46s} slot={slot} 主{len(mains)} 副{len(subs)}"
            f" -> {echo_score.score:g} {echo_score.grade.upper()}"
        )

    if detail_seen == 0:
        print("FAIL: 素材中未检测到任何 DETAIL 态")
        return 1
    print(f"\nDETAIL 触发 {detail_seen} 次，槽位覆盖 {sorted(scores)}")
    if len(scores) < 5:
        print("FAIL: slot1-5 未全部覆盖")
        return 1

    # 热键解析健全性
    mods, vk = _parse_hotkey("Alt+E")
    assert mods == 0x1 and vk == ord("E"), f"hotkey 解析异常 {mods:#x} {vk}"
    print("热键解析 OK (Alt+E -> MOD_ALT, 'E')")

    from wwechoes.scoring.characters import get_config
    from wwechoes.scoring.models import CharacterScore

    cs = CharacterScore(character=character, echoes=tuple(scores.get(k) for k in range(1, 6)))
    grade = cs.grade(get_config(character).total_grade)
    print(f"汇总条: total={cs.total:g}/250 grade={grade.upper()}")
    print("回放冒烟通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
