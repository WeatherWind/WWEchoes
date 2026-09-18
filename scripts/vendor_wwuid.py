"""从 WWUID 仓库同步角色评分配置到 src/wwechoes/scoring/data/。

用法：
    python scripts/vendor_wwuid.py --from-dir /tmp/wwuid/chenxun   # 从已解包目录合并
    python scripts/vendor_wwuid.py                                 # 从 GitHub 重新拉取

产物：
    characters.json —— {角色名: calc.json 内容}，default 目录映射为 "__default__"
    SOURCE.md —— 数据来源与快照记录（GPL-3.0 传染声明）

每次更新数据必须重跑本脚本（而不是手改 characters.json），保证来源可追溯。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = "ChenXun-123/WutheringWavesUID"
BRANCH = "master"
COMMIT = "1d693a2df0f940824cb34e102cec1cf3b381e70f"  # 2025-11-23 快照，44 角色
DEFAULT_KEY = "__default__"

ROOT = Path(__file__).resolve().parents[1]
CHAR_DIR = ROOT / "src" / "wwechoes" / "scoring" / "data"


def fetch_extracted(target: Path) -> dict[str, dict]:
    """从已解包目录（含 PROVENANCE.txt 与 character/）读取 calc.json 集合。"""
    configs: dict[str, dict] = {}
    for path in sorted((target / "character").glob("*/calc.json")):
        key = path.parent.name
        configs[DEFAULT_KEY if key == "default" else key] = json.loads(path.read_text("utf-8"))
    if DEFAULT_KEY not in configs:
        raise SystemExit("解包目录缺少 default/calc.json")
    return configs


def fetch_github() -> tuple[dict[str, dict], str]:
    """从 GitHub tarball 拉取 calc.json 集合，返回 (configs, commit)。"""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/tarball/{COMMIT}",
        headers={"User-Agent": "wwechoes-vendor"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        tar = tarfile.open(fileobj=io.BytesIO(resp.read()), mode="r:gz")
    configs: dict[str, dict] = {}
    for member in tar.getmembers():
        parts = member.name.split("/", 1)
        if len(parts) < 2 or not member.isfile():
            continue
        rel = parts[1]
        prefix = "WutheringWavesUID/utils/map/character/"
        if rel.startswith(prefix) and rel.endswith("calc.json"):
            key = rel[len(prefix):].split("/", 1)[0]
            configs[DEFAULT_KEY if key == "default" else key] = json.loads(
                tar.extractfile(member).read().decode("utf-8")
            )
    if DEFAULT_KEY not in configs:
        raise SystemExit("上游缺少 default/calc.json")
    return configs, COMMIT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-dir", type=Path, help="已解包目录（character/ 与 PROVENANCE.txt）")
    args = parser.parse_args()

    if args.from_dir:
        configs = fetch_extracted(args.from_dir)
        provenance = (args.from_dir / "PROVENANCE.txt").read_text("utf-8").strip()
    else:
        configs, commit = fetch_github()
        provenance = f"repo={REPO}\nbranch={BRANCH}\ncommit={commit}\nfetched=live"

    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    (CHAR_DIR / "characters.json").write_text(
        json.dumps(configs, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (CHAR_DIR / "SOURCE.md").write_text(
        "# 角色评分配置来源\n\n"
        "角色词条权重（skill_weight / main_props / sub_props / score_max / grade）"
        "提取自 WutheringWavesUID 的 `utils/map/character/<角色>/calc.json`，"
        "该项目为 **GPL-3.0**，故本文件及其衍生（characters.json）同样受 GPL-3.0 约束，"
        "不得脱离 GPL 许可证分发。\n\n"
        "```\n" + provenance + "\n```\n\n"
        "更新方式：`python scripts/vendor_wwuid.py`（勿手改 characters.json）。\n"
        "已知边界：快照晚于该日期上线的新角色未收录，评分时回落 `__default__` 通用权重。\n",
        encoding="utf-8",
    )
    print(f"characters.json: {len(configs)} 个配置（含 __default__）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
