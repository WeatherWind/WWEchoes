"""角色配置数据不变量：拦截 vendor 数据缺字段/键名异常。"""

from __future__ import annotations

from wwechoes.scoring.characters import _load_all, known_characters
from wwechoes.scoring.tables import ELEMENT_PREFIXES, PHANTOM_MAIN_VALUES, PHANTOM_SUB_VALUES

MAIN_KEYS = set(PHANTOM_MAIN_VALUES) | {"属性伤害加成"} | {f"{e}伤害加成" for e in ELEMENT_PREFIXES}
SUB_KEYS = set(PHANTOM_SUB_VALUES) | {f"{e}伤害加成" for e in ELEMENT_PREFIXES}


def test_all_configs_have_required_fields():
    for name, cfg in _load_all().items():
        assert set(cfg.main_props) == {"1", "3", "4"}, f"{name} main_props 键异常"
        assert len(cfg.score_max) == 3, f"{name} score_max 长度异常"
        assert len(cfg.props_grade) == 3 and all(len(g) == 6 for g in cfg.props_grade), (
            f"{name} props_grade 结构异常"
        )
        assert len(cfg.skill_weight) == 4, f"{name} skill_weight 长度异常"


def test_all_weight_keys_are_known_stats():
    for name, cfg in _load_all().items():
        for weights in cfg.main_props.values():
            unknown = set(weights) - MAIN_KEYS
            assert not unknown, f"{name} 主词条权重未知键: {unknown}"
        unknown = set(cfg.sub_props) - SUB_KEYS
        assert not unknown, f"{name} 副词条权重未知键: {unknown}"


def test_vendored_data_is_recent_enough():
    """快照含 2025 下半年角色（防止误回退到旧 vendor 快照）。"""
    names = set(known_characters())
    for expected in ("今汐", "守岸人", "卡提希娅", "菲比", "洛可可"):
        assert expected in names, f"配置快照缺少 {expected}"


def test_valid_grade_entries_are_canonical_names():
    for name, cfg in _load_all().items():
        for tier in ("valid_s", "valid_a", "valid_b"):
            for stat in cfg.grade.get(tier, ()):
                base = stat.rstrip("%")
                assert base in SUB_KEYS or stat in MAIN_KEYS, f"{name} {tier} 异常词条名: {stat}"
