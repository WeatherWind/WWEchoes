"""ROI 定义与分辨率缩放。

所有 ROI 以 1920×1080（16:9 基准）的像素坐标定义；其他 16:9 分辨率按
宽高比等比缩放。具体坐标值等 Windows 会话用 1080p 截图标注后填入
``ASSEMBLY_PAGE_ROIS`` / ``DETAIL_PANEL_ROIS``（当前为占位空表）。
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_W, BASE_H = 1920, 1080


@dataclass(frozen=True, slots=True)
class Roi:
    """矩形兴趣区（基准分辨率下的像素坐标）。"""

    x: int
    y: int
    w: int
    h: int


def scale_roi(roi: Roi, width: int, height: int) -> Roi:
    """把基准 ROI 等比缩放到目标 16:9 分辨率。"""
    sx, sy = width / BASE_W, height / BASE_H
    return Roi(round(roi.x * sx), round(roi.y * sy), round(roi.w * sx), round(roi.h * sy))


def is_16_9(width: int, height: int, tolerance: float = 0.02) -> bool:
    ratio = width / height
    return abs(ratio - 16 / 9) / (16 / 9) <= tolerance


#: 装配页检测 ROI（占位：坐标待 Windows 会话以 1080p 截图标注）
ASSEMBLY_PAGE_ROIS: tuple[Roi, ...] = ()

#: 声骸详情面板词条区 ROI（占位：主词条区 + 副词条区 + 面板出现特征区）
DETAIL_PANEL_ROIS: tuple[Roi, ...] = ()
