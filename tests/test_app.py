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
