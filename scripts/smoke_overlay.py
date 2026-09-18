"""悬浮窗冒烟（Windows 桌面会话手动运行，不入 pytest）。

断言：Win32 扩展样式位全就位（穿透/不抢焦点/工具窗/分层）、显示后
前台窗口不是悬浮窗（不抢焦点）、评分卡内容可渲染（grab 出图非空）。

    python scripts/smoke_overlay.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from wwechoes.overlay.view import ScoreCard  # noqa: E402
from wwechoes.overlay.win_overlay import Corner, OverlayWindow  # noqa: E402
from wwechoes.scoring import Echo, StatEntry, score_echo_for_character  # noqa: E402
from wwechoes.scoring.characters import get_config  # noqa: E402
from wwechoes.scoring.models import CharacterScore  # noqa: E402


def demo_score() -> tuple:
    character = "今汐"
    echo = Echo(
        cost=4,
        main_stats=(StatEntry("攻击", 150.0), StatEntry("暴击", 22.0)),
        sub_stats=(
            StatEntry("暴击", 10.5),
            StatEntry("暴击伤害", 21.0),
            StatEntry("攻击%", 11.6),
            StatEntry("共鸣效率", 6.8),
        ),
    )
    echo_score, _ = score_echo_for_character(echo, character)
    char_score = CharacterScore(character=character, echoes=(echo_score, None, None, None, None))
    char_score.grade(get_config(character).total_grade)
    return echo_score, char_score


def main() -> int:
    import ctypes

    user32 = ctypes.windll.user32

    app = QApplication([])
    echo_score, char_score = demo_score()
    card = ScoreCard()
    card.show_echo(echo_score, char_score, slot_index=0)
    card.resize(320, 420)

    overlay = OverlayWindow(content=card, corner=Corner.TOP_RIGHT, margin_px=16)
    overlay.show_no_activate()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.02)

    hwnd = overlay.hwnd
    print(f"[1] 悬浮窗 hwnd={hwnd}")
    if hwnd is None or not user32.IsWindowVisible(hwnd):
        print("[1] FAIL: 窗口不可见")
        return 1
    print("[1] OK: 窗口已显示")

    if not overlay.win32_styles_ok:
        exstyle = user32.GetWindowLongW(hwnd, -20)
        print(f"[2] FAIL: 扩展样式位缺失 exstyle={exstyle:#x}")
        return 1
    print("[2] OK: WS_EX_LAYERED|TRANSPARENT|NOACTIVATE|TOOLWINDOW 全部就位")

    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        print("[3] FAIL: 显示后悬浮窗抢到了前台焦点")
        return 1
    print(f"[3] OK: 前台窗口不是悬浮窗（fg={fg}），未抢焦点")

    pix = card.grab()
    if pix.isNull() or pix.width() == 0:
        print("[4] FAIL: 评分卡渲染为空")
        return 1
    out = os.path.join("docs", "assets", "raw", "smoke_overlay_preview.png")
    pix.save(out)
    print(f"[4] OK: 评分卡渲染 {pix.width()}x{pix.height()}，预览已存 {out}（本地不入库）")

    overlay.hide()
    time.sleep(0.05)
    if user32.IsWindowVisible(hwnd):
        print("[5] FAIL: hide 后窗口仍可见")
        return 1
    print("[5] OK: hide 生效")
    print("冒烟通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
