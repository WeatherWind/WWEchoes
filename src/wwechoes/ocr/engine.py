"""OCR 引擎：RapidOCR（onnxruntime CPU）适配层。

延迟导入与模型加载（首次约 1s，模型随包内置 PP-OCRv6），供 app 管线
在 DETAIL 态按需调用。行聚类把识别碎片（名称/数值分列输出）拼回文本行。

实测（3.6 版 1080p 截图，18/18 详情面板）：主/副词条区识别准确，
仅词条名前小图标会误识为噪声首字符（parser 后缀回退已容错）。
"""

from __future__ import annotations

import numpy as np

from wwechoes.detect.roi import Roi
from wwechoes.ocr.parser import parse_stat_line
from wwechoes.scoring.models import StatEntry

#: 同一行判定的 y 中心差阈值（像素，基准 1080p）
_ROW_GROUP_TOLERANCE = 15.0


def _cluster_lines(items: list[dict]) -> list[str]:
    """按 y 中心把识别碎片聚类成行，行内按 x 排序拼接。"""
    items = sorted(items, key=lambda i: i["y"])
    rows: list[list[dict]] = []
    for it in items:
        row_y = sum(p["y"] for p in rows[-1]) / len(rows[-1]) if rows else 0.0
        if rows and abs(it["y"] - row_y) < _ROW_GROUP_TOLERANCE:
            rows[-1].append(it)
        else:
            rows.append([it])
    return [" ".join(p["t"] for p in sorted(row, key=lambda p: p["x"])) for row in rows]


class OcrEngine:
    """线程不安全（onnxruntime session 可并发但结果列表独立）；
    v1 在主线程串行调用。"""

    def __init__(self) -> None:
        self._eng = None

    def _ensure(self):
        if self._eng is None:
            from rapidocr import RapidOCR  # 延迟导入：重依赖

            self._eng = RapidOCR()
        return self._eng

    def read_lines(self, frame_bgr: np.ndarray, roi: Roi) -> list[str]:
        """识别帧上 ROI 区域，返回拼接后的文本行（自上而下）。"""
        eng = self._ensure()
        region = frame_bgr[roi.y : roi.y + roi.h, roi.x : roi.x + roi.w]
        if region.size == 0:
            return []
        result = eng(region)
        if not result.txts:
            return []
        items = []
        for box, txt in zip(result.boxes, result.txts, strict=False):
            if not txt:
                continue
            ys = [float(p[1]) for p in box]
            xs = [float(p[0]) for p in box]
            items.append({"y": sum(ys) / len(ys), "x": sum(xs) / len(xs), "t": txt})
        return _cluster_lines(items)

    def read_stats(self, frame_bgr: np.ndarray, roi: Roi) -> list[StatEntry]:
        """识别并解析 ROI 区域的词条行（过滤无法归一的行）。"""
        parsed = (parse_stat_line(line) for line in self.read_lines(frame_bgr, roi))
        return [e for e in parsed if e is not None]
