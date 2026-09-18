"""ROI 定义与分辨率缩放。

所有 ROI 以 1920×1080（16:9 基准）的像素坐标定义；其他 16:9 分辨率按
宽高比等比缩放。坐标值实测自国服 3.6 版本 1080p 截图（docs/assets/raw/，
混淆矩阵验证见 scripts/verify_assets.py 与 docs/worklog/）。

注意：采集截图顶部 y=0..30 为屏幕遮挡伪影（近白横条，非游戏 UI），游戏
内容从 y=31 起。WGC 运行时抓取的是窗口客户区，实测若无伪影则需用
``SCREEN_ARTIFACT_HEIGHT`` 校准 y 偏移（见 matchers.frame_offset）。
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_W, BASE_H = 1920, 1080

#: 用户采集截图中游戏内容上方的屏幕伪影高度（像素）；运行时按需用于 y 校准
SCREEN_ARTIFACT_HEIGHT = 31


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


# ---------------------------------------------------------------------------
# 装配页检测 ROI（判据阈值见 matchers.py）
# ---------------------------------------------------------------------------

#: 左侧页签列第 3 位（声骸页签）金色高亮竖条 —— 装配页最强单一特征
ASSEMBLY_TAB_GOLD = Roi(50, 478, 60, 46)

#: 右上 COST 数字区（如 "12/12"）；需上下限窗口排除亮场景
ASSEMBLY_COST_DIGITS = Roi(1340, 150, 150, 65)

#: 底部白色胶囊按钮排（替换/声骸推荐）
ASSEMBLY_BOTTOM_BUTTONS = Roi(250, 1000, 350, 36)

#: 装配页检测 ROI 汇总（保持既有占位名，供通用遍历）
ASSEMBLY_PAGE_ROIS: tuple[Roi, ...] = (
    ASSEMBLY_TAB_GOLD,
    ASSEMBLY_COST_DIGITS,
    ASSEMBLY_BOTTOM_BUTTONS,
)

# ---------------------------------------------------------------------------
# 声骸详情面板检测 ROI
# ---------------------------------------------------------------------------

#: 面板顶部金色胶囊开关 —— 面板存在最强特征（打开面板时 18/18 恒定命中）
DETAIL_GOLD_CAPSULE = Roi(1320, 78, 140, 35)

#: COST 行与主词条 1 之间的暗色均匀带（mean/std/max 三重判据）
DETAIL_DARK_BAND = Roi(1560, 250, 300, 13)

#: 详情面板检测 ROI 汇总
DETAIL_PANEL_ROIS: tuple[Roi, ...] = (DETAIL_GOLD_CAPSULE, DETAIL_DARK_BAND)

# ---------------------------------------------------------------------------
# 详情面板 OCR 区域（词条识别输入；文字灰度 >=205，背景 <=75，
#: 二值化阈值 150-160 可干净分离，见 docs/worklog 素材分析）
# ---------------------------------------------------------------------------

#: 声骸名（金字 ≈246,239,190），含等级与类型图标行
DETAIL_ECHO_NAME = Roi(1508, 183, 345, 25)

#: 强化等级数字（如 "+25"），名称行右端
DETAIL_LEVEL = Roi(1770, 183, 46, 25)

#: COST 行（"COST" 标签 + 数字 + 槽位图标）
DETAIL_COST_ROW = Roi(1512, 219, 334, 25)

#: 主词条区：2 行（y≈270 / y≈306），Cost4 为 2 条主词条；3.6 版本 c1/c3 同为 2 行
DETAIL_MAIN_STATS = Roi(1508, 265, 350, 70)

#: 副词条区：最多 5 行，y=344 起步进 35px；+0 未强化时整块空白（固定网格逐行探测）
DETAIL_SUB_STATS = Roi(1508, 340, 350, 170)

#: 副词条单行（i=0..4）：Roi(1518, 344 + 35*i, 320, 22)
def sub_stat_row(i: int) -> Roi:
    """副词条第 i 行（0 基）。"""
    if not 0 <= i <= 4:
        raise ValueError(f"副词条行号 0..4，got {i}")
    return Roi(1518, 344 + 35 * i, 320, 22)


# ---------------------------------------------------------------------------
# 已装备槽位选中探针（仅 DETAIL 态有意义；面板打开后布局切换为
#: 左列已装备列表 + 中列背包网格 + 右侧详情面板）
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SlotProbe:
    """槽位选中态探针：暖亮像素计数 + 左右亮环边界结构校验。"""

    roi: Roi
    left_max: int  #: 亮环左竖边允许的最大 x（命中像素最左需 <= 此值）
    right_min: int  #: 亮环右竖边允许的最小 x（命中像素最右需 >= 此值）

    @staticmethod
    def for_slot(slot: int) -> SlotProbe:
        probes = {
            1: SlotProbe(Roi(50, 265, 122, 30), 62, 138),
            2: SlotProbe(Roi(40, 436, 118, 22), 62, 138),
            3: SlotProbe(Roi(40, 544, 118, 22), 62, 138),
            4: SlotProbe(Roi(40, 653, 118, 22), 62, 138),
            5: SlotProbe(Roi(40, 760, 118, 22), 62, 138),
        }
        if slot not in probes:
            raise ValueError(f"槽位号 1..5，got {slot}")
        return probes[slot]


#: 槽位编号 -> 探针（1=Cost4 主声骸 … 5=Cost1；选中环淡金 ≈(239,228,163)）
SLOT_PROBES: dict[int, SlotProbe] = {k: SlotProbe.for_slot(k) for k in range(1, 6)}
