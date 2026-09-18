"""用户设置持久化（stdlib only）。

设置文件位置：用户目录 ~/.wwechoes/config.json（打包 exe 下与用户目录解耦，
避免写安装目录）。字段与默认值见 ``Defaults``。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

CONFIG_PATH = Path.home() / ".wwechoes" / "config.json"


@dataclass(slots=True)
class Settings:
    overlay_corner: str = "top-right"  # top-right/top-left/bottom-right/bottom-left
    overlay_scale: float = 1.0
    overlay_use_anchor: bool = True  # 用自定义锚点位置（优先于 corner）
    # 客户区坐标：ax=左缘、ay=底边目标（默认值来自用户红圈标注+反馈，
    # 精确位置由托盘"位置微调"菜单调整后持久化）
    overlay_anchor_pos: list[int] = field(default_factory=lambda: [550, 1050])
    hotkey_toggle: str = "Alt+E"  # 显示/隐藏（RegisterHotKey，仅监听）
    manual_character: str = ""  # 手动指定角色（非空时优先，禁用自动识别）
    last_character: str = ""  # 上次识别成功的角色（兜底沿用）
    remember_last: bool = True


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    if not path.exists():
        return Settings()
    raw = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in raw.items() if k in known})


def save_settings(settings: Settings, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
