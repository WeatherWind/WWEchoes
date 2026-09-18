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
from wwechoes.detect.roi import BASE_H  # noqa: E402

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

    # 坐标系约定：ROI 常量为游戏客户区坐标系（真机 WGC 帧裁剪后内容从
    # y=0 起）；素材截图顶部 SCREEN_ARTIFACT_HEIGHT 行是游戏窗口系统
    # 标题栏，喂判据前裁掉，模拟客户区帧。
    from wwechoes.detect.roi import SCREEN_ARTIFACT_HEIGHT  # noqa: E402

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
        # 裁掉标题栏后素材缺底部 31px（截图高度 1080 截断），补黑边回
        # 1920×1080 基准，避免 matchers 触发等比缩放造成伪错位
        # （真机 WGC 客户区帧就是标准 1080 高，无需缩放）。
        cropped = img[SCREEN_ARTIFACT_HEIGHT:, :]
        pad = cropped.shape[0] - BASE_H
        if pad < 0:
            frame = cv2.copyMakeBorder(cropped, 0, -pad, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        else:
            frame = cropped
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
