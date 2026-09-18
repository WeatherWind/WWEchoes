"""matchers 纯像素判据单测（合成 BGR 帧，不依赖素材与平台）。

合成色取自 1080p 截图实测分布（见 detect/matchers.py docstring），
帧坐标系与 roi.py 常量一致（1920×1080 基准）。
"""

from __future__ import annotations

import numpy as np

from wwechoes.detect import PageState, detect_slot, observe_page
from wwechoes.detect.roi import (
    ASSEMBLY_BOTTOM_BUTTONS,
    ASSEMBLY_COST_DIGITS,
    ASSEMBLY_TAB_GOLD,
    DETAIL_DARK_BAND,
    DETAIL_GOLD_CAPSULE,
    SLOT_PROBES,
)

# 合成色（RGB -> 测试内按 BGR 写入帧）
GOLD_TAB = (150, 200, 230)  # 页签金条：过 C 组口径
CAPSULE = (114, 195, 208)  # 金胶囊核心色：过 D1 口径（B 低于 C 组下限）
WHITE_BTN = (240, 240, 240)
DARK = (40, 40, 40)
RING = (140, 190, 200)  # 选中环暖金：过暖亮口径


def blank() -> np.ndarray:
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


def paint(frame: np.ndarray, roi, color) -> None:
    frame[roi.y : roi.y + roi.h, roi.x : roi.x + roi.w] = color


def make_assembly() -> np.ndarray:
    f = blank()
    paint(f, ASSEMBLY_TAB_GOLD, GOLD_TAB)  # 2760 px >= 500
    # COST 区只画 2 行金（模拟数字笔画稀疏，300 in [150,400]）
    f[ASSEMBLY_COST_DIGITS.y : ASSEMBLY_COST_DIGITS.y + 2,
      ASSEMBLY_COST_DIGITS.x : ASSEMBLY_COST_DIGITS.x + 150] = GOLD_TAB
    # 底部按钮只画 10 行白（3500 in [1000,6000]）
    f[ASSEMBLY_BOTTOM_BUTTONS.y : ASSEMBLY_BOTTOM_BUTTONS.y + 10,
      ASSEMBLY_BOTTOM_BUTTONS.x : ASSEMBLY_BOTTOM_BUTTONS.x + 350] = WHITE_BTN
    return f


def make_detail() -> np.ndarray:
    f = blank()
    paint(f, DETAIL_GOLD_CAPSULE, CAPSULE)  # 4900 px >= 3000
    paint(f, DETAIL_DARK_BAND, DARK)  # mean 40 / std 0 / max 40
    return f


def paint_ring(frame: np.ndarray, slot: int) -> None:
    """在探针带左右各画一条竖亮边（模拟选中环双边）。"""
    probe = SLOT_PROBES[slot]
    x, y, w, h = probe.roi.x, probe.roi.y, probe.roi.w, probe.roi.h
    frame[y : y + h, x + 1 : x + 6] = RING
    frame[y : y + h, x + w - 6 : x + w - 1] = RING


def test_black_frame_is_unknown():
    assert observe_page(blank()) is PageState.UNKNOWN


def test_synthetic_assembly_page():
    assert observe_page(make_assembly()) is PageState.ASSEMBLY


def test_synthetic_detail_panel():
    assert observe_page(make_detail()) is PageState.DETAIL


def test_detail_takes_priority_over_assembly():
    """面板打开是布局切换，D 判据须先于 C 判据（两判据同时命中时报 DETAIL）。"""
    f = make_assembly()
    paint(f, DETAIL_GOLD_CAPSULE, CAPSULE)
    paint(f, DETAIL_DARK_BAND, DARK)
    assert observe_page(f) is PageState.DETAIL


def test_cost_overflow_rejected():
    """COST 区亮像素超上限（如声骸背包金条 1964px）须拒绝。"""
    f = make_assembly()
    paint(f, ASSEMBLY_COST_DIGITS, GOLD_TAB)  # 全区 9750 px > 400
    assert observe_page(f) is PageState.UNKNOWN


def test_buttons_overflow_rejected():
    """底部白像素超上限（如武器页 6521px）须拒绝。"""
    f = make_assembly()
    paint(f, ASSEMBLY_BOTTOM_BUTTONS, WHITE_BTN)  # 12600 px > 6000
    assert observe_page(f) is PageState.UNKNOWN


def test_pink_block_not_counted_as_capsule():
    """战斗 HUD 粉色特效 (228,151,167) 不计入金胶囊（R-G 反粉条件）。"""
    f = make_detail()
    paint(f, DETAIL_GOLD_CAPSULE, (167, 151, 228))  # BGR 粉
    assert observe_page(f) is PageState.UNKNOWN


def test_slot_single_hit():
    for k in range(1, 6):
        f = make_detail()
        paint_ring(f, k)
        assert detect_slot(f) == k


def test_slot_multi_hit_returns_none():
    f = make_detail()
    paint_ring(f, 2)
    paint_ring(f, 4)
    assert detect_slot(f) is None


def test_slot_requires_both_edges():
    """只有单侧亮边（立绘同色散点）不构成选中环。"""
    f = make_detail()
    probe = SLOT_PROBES[3]
    x, y, h = probe.roi.x, probe.roi.y, probe.roi.h
    f[y : y + h, x + 1 : x + 6] = RING  # 仅左边
    assert detect_slot(f) is None


def test_half_resolution_frame_still_matches():
    """面积归一化：半分辨率下采样帧判据等效。"""
    f = make_detail()[::2, ::2].copy()
    assert observe_page(f) is PageState.DETAIL
    f2 = make_assembly()[::2, ::2].copy()
    assert observe_page(f2) is PageState.ASSEMBLY
    f3 = make_detail()
    paint_ring(f3, 5)
    assert detect_slot(f3[::2, ::2].copy()) == 5


def test_oversized_frame_roi_out_of_range_is_safe():
    """小帧上 ROI 越界不抛异常，判据自然拒绝。"""
    tiny = np.zeros((100, 100, 3), dtype=np.uint8)
    assert observe_page(tiny) is PageState.UNKNOWN
    assert detect_slot(tiny) is None
