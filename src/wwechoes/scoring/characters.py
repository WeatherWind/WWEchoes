"""角色评分配置加载。

配置来自 WWUID 的 ``utils/map/character/<角色名>/calc.json``（GPL-3.0），
由 ``scripts/vendor_wwuid.py`` 合并生成 ``data/characters.json``。
未收录角色（新角色待补）回落到 ``__default__`` 通用权重，UI 需提示「通用评分」。
build 变体（condition*.json）v1 暂不支持，留作后续迭代。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "characters.json"
DEFAULT_KEY = "__default__"


@dataclass(frozen=True, slots=True)
class CharConfig:
    name: str
    skill_weight: list[float]
    main_props: dict[str, dict[str, float]]
    sub_props: dict[str, float]
    score_max: list[float]
    props_grade: list[list[float]]
    total_grade: list[float]
    grade: dict = field(default_factory=dict)
    is_default: bool = False


def _parse(name: str, raw: Mapping, is_default: bool = False) -> CharConfig:
    return CharConfig(
        name=name,
        skill_weight=raw.get("skill_weight") or [0, 0, 0, 0],
        main_props=raw.get("main_props", {}),
        sub_props=raw.get("sub_props", {}),
        score_max=raw.get("score_max") or [1.0, 1.0, 1.0],
        props_grade=raw.get("props_grade") or [[0, 0.48, 0.6, 0.7, 0.78, 0.84]] * 3,
        total_grade=raw.get("total_grade") or [0, 0.48, 0.6, 0.7, 0.78, 0.84],
        grade=raw.get("grade", {}),
        is_default=is_default,
    )


@lru_cache(maxsize=1)
def _load_all() -> dict[str, CharConfig]:
    raw: Mapping[str, Mapping] = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {
        name: _parse(name, cfg, is_default=(name == DEFAULT_KEY)) for name, cfg in raw.items()
    }


def get_config(character: str) -> CharConfig:
    """按角色名取配置；未收录时回落 default。"""
    configs = _load_all()
    if character in configs:
        return configs[character]
    return configs[DEFAULT_KEY]


def known_characters() -> list[str]:
    """已收录角色名列表（不含 default）。"""
    return sorted(k for k in _load_all() if k != DEFAULT_KEY)
