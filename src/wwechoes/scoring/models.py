"""评分领域模型。

词条名采用 WWUID 规范名：百分比词条以 ``%`` 结尾（如 ``攻击%``、``暴击``、
``暴击伤害``、``湮灭伤害加成``），数值为浮点数（不带百分号）。
OCR 层负责把游戏内文案归一化到这些规范名（见 ``ocr/parser.py`` 的别名表）。
"""

from __future__ import annotations

from dataclasses import dataclass

#: 评分等级，从低到高；与 WWUID 的 score_interval 一致
GRADES = ("c", "b", "a", "s", "ss", "sss")

#: 单件声骸满分（5 件合计 250 分）
FIX_MAX_SCORE = 50


@dataclass(frozen=True, slots=True)
class StatEntry:
    """一条词条：规范名 + 数值（浮点，百分比词条不带 % 号）。"""

    name: str
    value: float


@dataclass(frozen=True, slots=True)
class Echo:
    """一件声骸：Cost（4/3/1）+ 主词条（含固定词条）与副词条。"""

    cost: int
    main_stats: tuple[StatEntry, ...]
    sub_stats: tuple[StatEntry, ...]


@dataclass(frozen=True, slots=True)
class EntryScore:
    """单条词条的评分结果。

    valid_tier: 's' | 'a' | 'b' | None —— 该词条是否属于角色有效词条及档次
    is_max_roll: 是否为该词条的最高数值档（满 roll，UI 高亮用）
    """

    name: str
    value: float
    score: float
    valid_tier: str | None
    is_max_roll: bool


@dataclass(frozen=True, slots=True)
class EchoScore:
    """一件声骸的评分结果（50 分制）。"""

    cost: int
    score: float
    grade: str
    percent: float
    entries: tuple[EntryScore, ...]


@dataclass(frozen=True, slots=True)
class CharacterScore:
    """汇总条数据：本角色 5 个槽位，未看过/未识别的槽位为 None。"""

    character: str
    echoes: tuple[EchoScore | None, ...]

    @property
    def total(self) -> float:
        return round(sum(e.score for e in self.echoes if e is not None), 1)

    @property
    def seen_count(self) -> int:
        return sum(1 for e in self.echoes if e is not None)

    def grade(self, total_grade: tuple[float, ...]) -> str:
        """按 WWUID total_grade 阈值给出整套评分等级（未看满 5 件时按已看件计，UI 需标注件数）。"""
        ratio = self.total / (FIX_MAX_SCORE * 5)
        idx = 0
        for i, threshold in enumerate(total_grade):
            if ratio >= threshold:
                idx = i
        return GRADES[idx]
