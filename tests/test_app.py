"""app 装配层单测（平台无关部分：config 值 -> 枚举转换等）。"""

from __future__ import annotations

import pytest

from wwechoes.config import Settings


def test_overlay_corner_from_settings():
    from wwechoes.overlay.win_overlay import Corner

    for value, expect in [
        ("top-right", Corner.TOP_RIGHT),
        ("top-left", Corner.TOP_LEFT),
        ("bottom-right", Corner.BOTTOM_RIGHT),
        ("bottom-left", Corner.BOTTOM_LEFT),
    ]:
        assert Corner(Settings(overlay_corner=value).overlay_corner.replace("-", "_")) is expect


def test_overlay_corner_invalid_value_raises():
    from wwechoes.overlay.win_overlay import Corner

    with pytest.raises(ValueError, match="not a valid Corner"):
        Corner("top-right")  # 连字符不是合法枚举值（曾致真机崩溃的转换缺失）


def test_fmt_value_percent_suffix():
    from wwechoes.overlay.view import _fmt_value

    assert _fmt_value("暴击", 8.1) == "8.1%"
    assert _fmt_value("攻击%", 11.6) == "11.6%"
    assert _fmt_value("湮灭伤害加成", 30.0) == "30%"
    assert _fmt_value("攻击", 150.0) == "150"
    assert _fmt_value("生命", 470.0) == "470"
