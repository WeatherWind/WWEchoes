"""评分引擎单测：金样例数值 + 等级阈值 + 有效词条/满 roll 标注。

金样例独立于引擎实现，按 WWUID 公式手算：
今汐（skill_weight=[0,0,0.65,0.3]，4Cost score_max=83.804）
  主词条: 攻击150 -> 0.025*150=3.75 ; 暴击22 -> 0.5*22=11.0
  副词条: 暴击10.5 -> 2*10.5=21.0 ; 暴伤21 -> 1*21=21.0 ;
          攻击%11.6 -> 1.1*11.6=12.76 ; 共鸣效率6.8 -> 0.25*6.8=1.7
  合计 71.21 -> percent=71.21/83.804 -> *50 四舍五入
"""

from __future__ import annotations

import pytest

from wwechoes.scoring import Echo, StatEntry, score_echo, score_echo_for_character
from wwechoes.scoring.characters import get_config, known_characters
from wwechoes.scoring.models import CharacterScore


@pytest.fixture()
def jinxii_echo() -> Echo:
    return Echo(
        cost=4,
        main_stats=(StatEntry("攻击", 150.0), StatEntry("暴击", 22.0)),
        sub_stats=(
            StatEntry("暴击", 10.5),
            StatEntry("暴击伤害", 21.0),
            StatEntry("攻击%", 11.6),
            StatEntry("共鸣效率", 6.8),
        ),
    )


def test_golden_score_jinxii(jinxii_echo):
    score, cfg = score_echo_for_character(jinxii_echo, "今汐")
    raw = (0.025 * 150 + 0.5 * 22) + (2 * 10.5 + 1 * 21 + 1.1 * 11.6 + 0.25 * 6.8)
    percent = raw / 83.804
    assert score.score == pytest.approx(round(percent * 50, 1))
    assert score.score == 42.5
    assert score.grade == "sss"  # percent≈0.8497 ≥ 0.84


def test_entry_details(jinxii_echo):
    score, _ = score_echo_for_character(jinxii_echo, "今汐")
    by_name = {e.name: e for e in score.entries}
    # 今汐 valid_s: 暴击/暴击伤害/攻击/衍射伤害加成；valid_b: 共鸣效率/共鸣解放伤害加成
    assert by_name["暴击"].valid_tier == "s"
    assert by_name["攻击%"].valid_tier == "s"  # % 基础词条回落到不带 % 的有效词条名
    assert by_name["共鸣效率"].valid_tier == "b"
    assert by_name["暴击"].is_max_roll is True  # 10.5 为暴击最高档
    assert by_name["暴击伤害"].is_max_roll is True  # 21.0 为暴伤最高档
    assert by_name["共鸣效率"].is_max_roll is False
    assert by_name["攻击"].is_max_roll is False  # 主词条不参与满 roll 判定


def test_elemental_damage_main_stat():
    """Cost3 主词条「湮灭伤害加成」走属性伤害加成权重。"""
    echo = Echo(
        cost=3,
        main_stats=(StatEntry("攻击", 100.0), StatEntry("湮灭伤害加成", 30.0)),
        sub_stats=(StatEntry("暴击", 6.3),),
    )
    score, _ = score_echo_for_character(echo, "今汐")
    raw = 0.025 * 100 + 0.275 * 30 + 2 * 6.3
    assert score.score == pytest.approx(round(raw / 79.804 * 50, 1))


def test_skill_damage_sub_stat_uses_skill_weight():
    """技能伤害类副词条权重 = 技能伤害加成权重 × skill_weight。"""
    echo = Echo(
        cost=1,
        main_stats=(StatEntry("生命", 2280.0),),
        sub_stats=(StatEntry("共鸣技能伤害加成", 11.6),),  # 今汐 skill_weight[2]=0.65
    )
    score, _ = score_echo_for_character(echo, "今汐")
    # 生命主词条今汐权重为 0，唯一得分项：1.1 * 0.65 * 11.6
    assert score.entries[-1].score == pytest.approx(1.1 * 0.65 * 11.6, abs=0.01)


def test_unknown_character_falls_back_to_default():
    cfg = get_config("不存在的角色")
    assert cfg.is_default is True
    echo = Echo(
        cost=4,
        main_stats=(StatEntry("攻击", 150.0), StatEntry("暴击伤害", 44.0)),
        sub_stats=(StatEntry("暴击", 10.5),),
    )
    score = score_echo(echo, cfg)
    assert score.score > 0


def test_known_characters_loaded():
    names = known_characters()
    assert "今汐" in names
    assert "__default__" not in names
    assert len(names) >= 40


def test_character_score_summary(jinxii_echo):
    echo_score, cfg = score_echo_for_character(jinxii_echo, "今汐")
    summary = CharacterScore(character="今汐", echoes=(echo_score, None, echo_score, None, None))
    assert summary.seen_count == 2
    assert summary.total == pytest.approx(echo_score.score * 2)
    # 85/250 = 0.34 < 0.48 -> 整套等级最低档 c（未集齐 5 件时 UI 需标注件数）
    assert summary.grade(tuple(cfg.total_grade)) == "c"
