"""OCR 文本解析单测。

注意：游戏内实际文案未核对（待 Windows 会话 1080p 截图），
本测试只锁定解析机制（别名映射/全角归一/数值抽取/未知词条丢弃），
截图核对后如有出入改 ``_ALIASES`` 而非本测试。
"""

from __future__ import annotations

from wwechoes.ocr import parse_stat_line


def _eq(line: str, name: str, value: float) -> bool:
    entry = parse_stat_line(line)
    return entry is not None and entry.name == name and entry.value == value


def test_basic_lines():
    assert _eq("暴击 +8.1%", "暴击", 8.1)
    assert _eq("攻击力 40", "攻击", 40.0)
    assert _eq("暴击伤害 +21.0%", "暴击伤害", 21.0)
    assert _eq("攻击 +11.6%", "攻击%", 11.6)  # 百分比基础词条补 % 后缀
    assert _eq("共鸣效率 +10.8%", "共鸣效率", 10.8)


def test_fullwidth_and_decimal():
    assert _eq("暴击＋８．１％", "暴击", 8.1)


def test_elemental_damage():
    assert _eq("湮灭伤害加成 +30%", "湮灭伤害加成", 30.0)


def test_unknown_returns_none():
    assert parse_stat_line("奇怪词条 +5") is None
    assert parse_stat_line("") is None
    assert parse_stat_line("没有数值") is None
