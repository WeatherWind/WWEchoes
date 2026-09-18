"""OCR 文本 -> 规范词条（StatEntry）。

负责把声骸详情面板 OCR 出的文本行归一化为 WWUID 规范词条名：
- 别名映射（游戏内文案 / 常见 OCR 错字 -> 规范名）；
- 数值解析（去 %、去加号、全角转半角）；
- 未匹配词条返回 None（调用方决定忽略或提示）。

注意：别名表当前基于公开资料整理，**游戏内实际文案以 Windows 会话的
1080p 截图核对为准**（docs/assets/），核对后在此表补充修正。
"""

from __future__ import annotations

import re

from wwechoes.scoring.models import StatEntry
from wwechoes.scoring.tables import PHANTOM_SUB_VALUES

#: 游戏文案/OCR 错字 -> 规范名（规范名键集 = PHANTOM_SUB_VALUES ∪ 主词条名，见 tables.py）
_ALIASES: dict[str, str] = {
    # 数值型基础词条
    "攻击力": "攻击",
    "生命值": "生命",
    "防御力": "防御",
    "百分比攻击": "攻击%",
    "百分比生命": "生命%",
    "百分比防御": "防御%",
    # 常见 OCR 形变（待截图核对后增补）
    "暴击率": "暴击",
    "暴击": "暴击",
    "爆伤": "暴击伤害",
    "共鸣效率": "共鸣效率",
    "属性伤害加成": "属性伤害加成",
}

_FULLWIDTH = str.maketrans("０１２３４５６７８９．％＋", "0123456789.%+")
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%?")


def normalize_name(raw: str) -> str | None:
    """OCR 词条名 -> 规范名；无法归一返回 None。

    游戏内词条名前可能带小图标/装饰，OCR 常把它们误识成首字符噪声
    （实测 3.6 版：``* 暴击``、``又攻击``、``X攻击``）。归一失败时
    逐次剥离首字符重试（最长后缀匹配），保留至少 2 个字符。
    """
    name = raw.strip().replace(" ", "")
    if not name:
        return None
    valid = set(PHANTOM_SUB_VALUES) | {
        "攻击", "攻击%", "生命", "生命%", "防御%", "暴击", "暴击伤害",
        "共鸣效率", "治疗效果加成",
    } | {f"{e}伤害加成" for e in ("冷凝", "衍射", "导电", "热熔", "气动", "湮灭")}
    for candidate in (name, *(name[i:] for i in range(1, max(len(name) - 1, 0)))):
        candidate = _ALIASES.get(candidate, candidate)
        if candidate in valid:
            return candidate
    return None


def parse_stat_line(line: str) -> StatEntry | None:
    """解析一行 OCR 文本（如 ``暴击 +8.1%`` / ``攻击力 40``）为 StatEntry。

    百分比词条的规范名以 ``%`` 结尾（攻击%/生命%/防御% 之外的百分比词条
    规范名本身不含 %，如「暴击」数值即按百分数理解）。
    """
    line = line.strip().translate(_FULLWIDTH)
    m = _NUM_RE.search(line)
    if m is None:
        return None
    value = float(m.group(1))
    is_percent = "%" in line[m.end() - 1 :] or "%" in line[m.start(): m.end()]
    raw_name = line[: m.start()].strip(" +:：")
    name = normalize_name(raw_name)
    if name is None:
        return None
    if is_percent and name in ("攻击", "生命", "防御"):
        name += "%"
    return StatEntry(name=name, value=value)
