"""词条权重评分引擎。

移植自 WutheringWavesUID ``utils/calculate.py``（GPL-3.0）的打分口径：

- 每条词条按角色权重表（main_props / sub_props）加权求和；
- 总分除以该 Cost 的满分（score_max）得百分比；
- 单件得分 = 百分比 × 50（五件合计 250 分制）；
- 等级按 props_grade / total_grade 阈值映射到 c/b/a/s/ss/sss。

与 WWUID 的差异：输入用显式的主/副词条分组（OCR 场景下面板可直接区分），
替代其「prop_list 前 2 项为主词条」的约定。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .characters import CharConfig, get_config
from .models import GRADES, Echo, EchoScore, EntryScore, StatEntry
from .tables import ELEMENT_PREFIXES, SKILL_DAMAGE_SUBS, max_roll_value


def _entry_score(
    entry: StatEntry, weights: Mapping[str, float], skill_weight: Sequence[float]
) -> float:
    if entry.name in ("攻击", "攻击%", "生命", "生命%", "防御", "防御%"):
        return weights.get(entry.name, 0.0) * entry.value
    if entry.name in SKILL_DAMAGE_SUBS:
        sw = skill_weight[SKILL_DAMAGE_SUBS.index(entry.name)]
        return weights.get("技能伤害加成", 0.0) * sw * entry.value
    if entry.name[:2] in ELEMENT_PREFIXES:
        return weights.get("属性伤害加成", 0.0) * entry.value
    return weights.get(entry.name, 0.0) * entry.value


def _cost_index(cost: int) -> int:
    """Cost -> score_max / props_grade 的下标（1->0, 3->1, 4->2）。"""
    return {1: 0, 3: 1}.get(cost, 2)


def _grade_for(percent: float, thresholds: Sequence[float]) -> str:
    idx = 0
    for i, threshold in enumerate(thresholds):
        if percent >= threshold:
            idx = i
    return GRADES[idx]


def _valid_tier(name: str, grade: Mapping[str, list]) -> str | None:
    """词条在角色有效词条表中的档次（s > a > b），非有效词条为 None。

    WWUID 的有效词条表不区分「攻击」与「攻击%」（同名匹配），
    此处保持同口径：带 % 的基础词条回落到不带 % 的名字再查一次。
    """
    if name in grade.get("valid_s", ()):
        return "s"
    if name in grade.get("valid_a", ()):
        return "a"
    if name in grade.get("valid_b", ()):
        return "b"
    if name.endswith("%"):
        return _valid_tier(name[:-1], grade)
    return None


def score_echo(echo: Echo, cfg: CharConfig) -> EchoScore:
    """对单件声骸打分（50 分制）。"""
    skill_weight = cfg.skill_weight or [0, 0, 0, 0]
    main_weights = cfg.main_props.get(str(echo.cost), {})

    scored: list[tuple[StatEntry, float]] = []
    for s in echo.main_stats:
        scored.append((s, _entry_score(s, main_weights, skill_weight)))
    for s in echo.sub_stats:
        scored.append((s, _entry_score(s, cfg.sub_props, skill_weight)))

    total = sum(v for _, v in scored)
    max_score = cfg.score_max[_cost_index(echo.cost)]
    percent = total / max_score if max_score else 0.0

    entries = tuple(
        EntryScore(
            name=s.name,
            value=s.value,
            score=round(v, 2),
            valid_tier=_valid_tier(s.name, cfg.grade),
            is_max_roll=(s in echo.sub_stats and max_roll_value(s.name) == s.value),
        )
        for s, v in scored
    )
    return EchoScore(
        cost=echo.cost,
        score=round(percent * 50, 1),
        grade=_grade_for(percent, cfg.props_grade[_cost_index(echo.cost)]),
        percent=percent,
        entries=entries,
    )


def score_echo_for_character(echo: Echo, character: str) -> tuple[EchoScore, CharConfig]:
    """便捷入口：按角色名取配置打分；无配置的角色回落到 default（通用权重）。"""
    cfg = get_config(character)
    return score_echo(echo, cfg), cfg
