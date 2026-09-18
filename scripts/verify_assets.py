"""素材回归验证：用 detect.matchers 判据对 docs/assets/raw/ 全量截图跑混淆矩阵。

用法（Windows 会话，需已安装 numpy/opencv 与本地截图素材）：
    python scripts/verify_assets.py [素材目录]

素材仅本地留存（.gitignore 排除 raw/），CI 无素材时直接跳过（退出码 0）。
新采集素材（版本更新后）应复跑本脚本，判据退化时先调 matchers 阈值再合入。
"""

from __future__ import annotations

import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wwechoes.detect import PageState, detect_slot, observe_page  # noqa: E402

DEFAULT_DIR = "docs/assets/raw"


def imread(p: str) -> np.ndarray:
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def classify(name: str) -> str:
    if name.startswith("neg-"):
        return "NEG"
    if name.startswith("assembly-detail"):
        return "DETAIL"
    if name.startswith("assembly-"):
        return "ASM"
    return "SKIP"


def main() -> int:
    assets = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR
    files = sorted(glob.glob(os.path.join(assets, "*.png")))
    if not files:
        print(f"[skip] {assets} 下无截图素材（仅 Windows 本机留存），跳过回归。")
        return 0

    # 坐标系约定：ROI 常量按截图原始坐标系标注（顶部 0..30 伪影条视为基准
    # 帧一部分，所有 ROI 的 y>=78 不受影响）；素材整图直接作为基准 1080p 帧
    # 喂给判据。运行时 WGC 客户区帧由 matchers 内部 scale_roi 自适应缩放。
    correct = wrong = 0
    slot_total = slot_ok = 0
    failures: list[str] = []
    for f in files:
        name = os.path.basename(f)
        cls = classify(name)
        if cls == "SKIP":
            continue
        img = imread(f)
        if img is None:
            failures.append(f"{name}: 读取失败")
            wrong += 1
            continue
        frame = img
        obs = observe_page(frame)
        expect = {
            "ASM": PageState.ASSEMBLY,
            "DETAIL": PageState.DETAIL,
            "NEG": PageState.UNKNOWN,
        }[cls]
        ok = obs is expect
        correct += ok
        wrong += not ok
        if not ok:
            failures.append(f"{name}: expect={cls} obs={obs.name}")
        if cls == "DETAIL" and "slot" in name:
            name_slot = name.split("slot")[1][0]
            slot_total += 1
            slot_ok += detect_slot(frame) == int(name_slot)

    print(f"页面检测: {correct}/{correct + wrong} 正确")
    if slot_total:
        print(f"槽位判定(slot 系列): {slot_ok}/{slot_total} 正确")
    for msg in failures:
        print("  失败:", msg)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
