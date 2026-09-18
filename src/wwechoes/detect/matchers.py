"""帧 -> 页面状态 / 槽位判定的纯像素判据（无模板图，仅 numpy）。

设计依据（国服 3.6 版本、1920×1080 截图 35 张混淆矩阵 35/35，含 7 张
负样本零误报；实测分布见 scripts/verify_assets.py 与 docs/worklog/）：

- 详情面板（DETAIL）：金胶囊像素数恒定 4609..4612，非面板帧 <=2（含
  反粉条件，排除战斗 HUD 粉色特效假阳）；暗带 mean/std/max 三重判据。
- 装配页（ASSEMBLY）：页签金条 829..835 vs 负样本最大 274；COST 区与
  底部按钮取上下限窗口，排除声骸背包金条与武器页亮按钮。
- 打开详情面板后游戏切换为完整新布局（左列已装备 + 中列背包 + 右侧
  面板），装配页 C2/C3 判据在 DETAIL 态全部归零 —— 因此观测顺序必须
  **先测面板（D）再测装配页（C）**。
- 槽位选中环为淡金描边（探针计数 + 左右双边结构校验 + 单槽约束；
  共鸣链页存在已知同色假阳，但被 DETAIL 前置判据拦截）。

合规：仅做屏幕帧的像素统计，不涉及任何内存读取（ADR-0003）。
"""

from __future__ import annotations

import numpy as np

from .page_detector import PageState
from .roi import (
    ASSEMBLY_BOTTOM_BUTTONS,
    ASSEMBLY_COST_DIGITS,
    ASSEMBLY_TAB_GOLD,
    BASE_H,
    BASE_W,
    DETAIL_DARK_BAND,
    DETAIL_GOLD_CAPSULE,
    SLOT_PROBES,
    Roi,
    scale_roi,
)

# --- 阈值（正/负样本实测分布的中安全区，见模块 docstring）---
ASSEMBLY_TAB_GOLD_MIN = 500  # 正 829..835 / 负最大 274（战斗 HUD 天空）
ASSEMBLY_COST_DIGITS_RANGE = (150, 400)  # 正 235..296 / 负最大 460（超出上限被拒）
ASSEMBLY_BUTTONS_RANGE = (1000, 6000)  # 正 ~5020 / 武器页 6521 超上限被拒
DETAIL_CAPSULE_MIN = 3000  # 正 4609..4612 / 负 <=2
DETAIL_DARK_BAND_MAX_MEAN = 45.0  # 正 34..39 / 负 >=48
DETAIL_DARK_BAND_MAX_STD = 10.0
DETAIL_DARK_BAND_MAX_PIXEL = 130
SLOT_MIN_COUNT = 40  # 正 185..316 / 未选中 0..11

#: 灰度权重（BGR -> ITU-R BT.601 亮度），避免依赖 cv2 保持模块轻量
_GRAY_WEIGHTS = np.array([0.114, 0.587, 0.299], dtype=np.float32)


def _crop(frame: np.ndarray, roi: Roi) -> np.ndarray:
    x, y, w, h = roi.x, roi.y, roi.w, roi.h
    fh, fw = frame.shape[:2]
    if y + h > fh or x + w > fw or x < 0 or y < 0:
        return np.zeros((0, 0, 3), dtype=frame.dtype)
    return frame[y : y + h, x : x + w]


def _scale(frame: np.ndarray, roi: Roi) -> Roi:
    """帧尺寸非基准时等比缩放 ROI（v1 正式支持 1080p，其他 16:9 尽力）。"""
    fh, fw = frame.shape[:2]
    if (fw, fh) == (BASE_W, BASE_H):
        return roi
    return scale_roi(roi, fw, fh)


def _area_scale(frame: np.ndarray) -> float:
    """计数判据的面积归一化因子：非基准分辨率帧的像素计数折算回基准。

    阈值按 1080p 截图标定（绝对像素数）；帧缩放后命中数按面积衰减，
    乘回 (基准面积/帧面积) 使判据在任意等比分辨率下等效。
    """
    fh, fw = frame.shape[:2]
    return (BASE_W * BASE_H) / (fw * fh)


def _count_gold(frame: np.ndarray, roi: Roi, *, anti_pink: bool = False) -> int:
    """金色调像素计数（C 组判据口径：R>200,G>180,120<B<220,R>B）。"""
    region = _crop(frame, _scale(frame, roi))
    if region.size == 0:
        return 0
    b, g, r = (region[:, :, i].astype(np.int16) for i in range(3))
    mask = (r > 200) & (g > 180) & (b > 120) & (b < 220) & (r > b)
    if anti_pink:
        mask &= (r - g) < 40
    return int(mask.sum() * _area_scale(frame))


def _count_gold_capsule(frame: np.ndarray, roi: Roi) -> int:
    """金色胶囊像素计数（D1 口径：R>170,G>130,R-B>50,R-G<40 反粉）。

    胶囊核心色 (208,195,114) 的 B 低于 C 组下限，必须用独立口径。
    """
    region = _crop(frame, _scale(frame, roi))
    if region.size == 0:
        return 0
    b, g, r = (region[:, :, i].astype(np.int16) for i in range(3))
    mask = (r > 170) & (g > 130) & ((r - b) > 50) & ((r - g) < 40)
    return int(mask.sum() * _area_scale(frame))


def _count_white(frame: np.ndarray, roi: Roi) -> int:
    region = _crop(frame, _scale(frame, roi))
    if region.size == 0:
        return 0
    b, g, r = (region[:, :, i] for i in range(3))
    return int(((r > 230) & (g > 230) & (b > 225)).sum() * _area_scale(frame))


def _gray_stats(frame: np.ndarray, roi: Roi) -> tuple[float, float, int]:
    """区域灰度 (mean, std, max)。"""
    region = _crop(frame, _scale(frame, roi))
    if region.size == 0:
        return (255.0, 0.0, 255)  # 空区域按"最亮"处理，判据自然拒绝
    gray = region.astype(np.float32) @ _GRAY_WEIGHTS
    return (float(gray.mean()), float(gray.std()), int(gray.max()))


def _warm_bright_bounds(frame: np.ndarray, roi: Roi) -> tuple[int, int, int]:
    """槽位选中环暖亮像素 (归一化计数, min_x, max_x)。"""
    scaled = _scale(frame, roi)
    region = _crop(frame, scaled)
    if region.size == 0:
        return (0, -1, -1)
    b, g, r = (region[:, :, i].astype(np.int16) for i in range(3))
    mask = (
        (r > 165) & (g > 160) & (b > 110) & (b < 220)
        & ((r - b) >= 25) & ((r - b) <= 85) & ((g - b) >= 12)
    )
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return (0, -1, -1)
    return (
        int(len(xs) * _area_scale(frame)),
        scaled.x + int(xs.min()),
        scaled.x + int(xs.max()),
    )


def is_detail_panel(frame: np.ndarray) -> bool:
    """声骸详情面板是否存在（金胶囊 + 暗带双重判据）。"""
    if _count_gold_capsule(frame, DETAIL_GOLD_CAPSULE) < DETAIL_CAPSULE_MIN:
        return False
    mean, std, mx = _gray_stats(frame, DETAIL_DARK_BAND)
    return (
        mean < DETAIL_DARK_BAND_MAX_MEAN
        and std < DETAIL_DARK_BAND_MAX_STD
        and mx < DETAIL_DARK_BAND_MAX_PIXEL
    )


def is_assembly_page(frame: np.ndarray) -> bool:
    """是否为装配页（未打开详情面板；金条 + COST 窗口 + 按钮窗口三重判据）。"""
    tab = _count_gold(frame, ASSEMBLY_TAB_GOLD)
    if tab < ASSEMBLY_TAB_GOLD_MIN:
        return False
    cost = _count_gold(frame, ASSEMBLY_COST_DIGITS)
    lo, hi = ASSEMBLY_COST_DIGITS_RANGE
    if not (lo <= cost <= hi):
        return False
    buttons = _count_white(frame, ASSEMBLY_BOTTOM_BUTTONS)
    lo, hi = ASSEMBLY_BUTTONS_RANGE
    return lo <= buttons <= hi


def observe_page(frame: np.ndarray) -> PageState:
    """单帧瞬时观测：先测详情面板（布局切换后装配页判据失效），再测装配页。"""
    if is_detail_panel(frame):
        return PageState.DETAIL
    if is_assembly_page(frame):
        return PageState.ASSEMBLY
    return PageState.UNKNOWN


def detect_slot(frame: np.ndarray) -> int | None:
    """当前详情面板对应第几槽位（1..5）；无命中或多命中（不可信）返回 None。

    仅在 DETAIL 态调用有意义（无面板的装配页/负样本上左列不存在选中环；
    共鸣链页金色节点为已知假阳，由 DETAIL 前置判据拦截）。
    """
    fh, fw = frame.shape[:2]
    sx = fw / BASE_W
    hits: list[int] = []
    for slot, probe in SLOT_PROBES.items():
        count, min_x, max_x = _warm_bright_bounds(frame, probe.roi)
        # 结构校验阈值随分辨率缩放（与 ROI 同因子）
        left = round(probe.left_max * sx)
        right = round(probe.right_min * sx)
        if count >= SLOT_MIN_COUNT and min_x <= left and max_x >= right:
            hits.append(slot)
    return hits[0] if len(hits) == 1 else None
