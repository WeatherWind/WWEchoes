"""悬浮窗内容视图：单件评分卡 + 5 槽位汇总条。

纯 PySide6 绘制，可在任意平台开发预览（``python -m wwechoes.overlay.view``）；
窗口置顶/穿透等 Win32 行为由 ``win_overlay.py`` 在 Windows 上叠加。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from wwechoes.scoring.characters import get_config
from wwechoes.scoring.models import CharacterScore, EchoScore
from wwechoes.scoring.tables import (
    ELEMENT_PREFIXES,
    PHANTOM_MAIN_VALUES,
    PHANTOM_SUB_VALUES,
)

#: 等级 -> 颜色（SSS 金 / SS S 橙紫 / A 蓝 / B 绿 / C 灰）
GRADE_COLORS = {
    "sss": QColor("#e6b422"),
    "ss": QColor("#d29415"),
    "s": QColor("#b07fd8"),
    "a": QColor("#4a90d9"),
    "b": QColor("#5bbd6b"),
    "c": QColor("#c3c9d1"),  # C 档灰提亮（原 #8a8a8a 真机不可读）
    None: QColor("#555555"),
}

VALID_TIER_COLORS = {
    "s": QColor("#e6b422"),
    "a": QColor("#9d7bd8"),
    "b": QColor("#5bbd6b"),
    None: QColor("#dde2e8"),  # 非有效词条：暗灰真机不可读，提亮至近白
}

#: 面板底色（真机像素取证：QWidget 不开 WA_StyledBackground 时 QSS 背景
#: 不绘制，文字直压游戏画面对比度仅 1.3-1.6:1；开启后 #e8eaf0 约 14:1）
_PANEL_QSS = """
#scoreCard { background-color: rgba(12,14,20,245); border-radius: 10px; }
QLabel { color: #f2f4f8; font-size: 11pt; font-weight: 600; }
#summaryBar { background-color: rgba(0,0,0,115); border-radius: 6px; }
"""


def _fmt_value(name: str, value: float) -> str:
    """按词条数值档位表判断是否百分比词条，输出带 % 的显示串。"""
    key = "属性伤害加成" if name[:2] in ELEMENT_PREFIXES else name
    for table in (PHANTOM_SUB_VALUES, PHANTOM_MAIN_VALUES):
        vals = table.get(key)
        if vals and any("%" in str(v) for v in vals):
            return f"{value:g}%"
    return f"{value:g}"


class SummaryBar(QFrame):
    """底部 5 槽位汇总条（含整套总分）。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("summaryBar")
        self.setFixedHeight(38)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self.slots: list[QLabel] = []
        for _ in range(5):
            slot = QLabel("--")
            slot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slot.setMinimumWidth(42)
            layout.addWidget(slot)
            self.slots.append(slot)
        self.slot_names: list[str] = [""] * 5  # 预留：槽位声骸名（对比增强用）
        self.total = QLabel("0.0")
        self.total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total.setFont(QFont(self.font().family(), 10, QFont.Weight.Bold))
        layout.addWidget(self.total)

    def update_score(self, score: CharacterScore | None) -> None:
        if score is None:
            for slot in self.slots:
                slot.setText("--")
                slot.setStyleSheet("")
            self.total.setText("0.0")
            return
        for slot, echo in zip(self.slots, score.echoes, strict=False):
            if echo is None:
                slot.setText("--")
                slot.setStyleSheet("")
            else:
                slot.setText(f"{echo.score:g}")
                slot.setStyleSheet(
                    f"color:{GRADE_COLORS[echo.grade].name()};font-weight:bold;"
                )
        self.total.setText(f"{score.total:g} / 250")


class ScoreCard(QWidget):
    """单件声骸评分卡：头部（角色/等级/分数）+ 逐词条明细 + 汇总条。"""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("scoreCard")
        # 普通 QWidget 默认不绘制 QSS 背景，必须显式开启（真机可读性根因）
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_PANEL_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 18, 12, 8)  # 顶边 18：标题行整体下移 ~10px
        root.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.char_label = QLabel("—")
        self.char_label.setFont(QFont(self.font().family(), 11, QFont.Weight.Bold))
        self.score_label = QLabel("0.0")
        self.score_label.setFont(QFont(self.font().family(), 11))
        # 等级大字带底色 pill 放最右（真机反馈：分级不明显；pill 高度收紧）
        self.grade_label = QLabel("--")
        self.grade_label.setFont(QFont(self.font().family(), 15, QFont.Weight.Black))
        self.grade_label.setFixedHeight(26)
        self.grade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.char_label)
        header.addStretch(1)
        header.addWidget(self.score_label)
        header.addWidget(self.grade_label)
        root.addLayout(header)
        self.best_label = QLabel("")  # 本槽历史最佳（同槽换声骸对比）
        self.best_label.setStyleSheet("color:#ccd2da; font-size: 8pt; margin: 0; padding: 0;")
        root.addWidget(self.best_label)

        self.entries_box = QVBoxLayout()
        self.entries_box.setSpacing(4)
        entries_host = QWidget()
        entries_host.setLayout(self.entries_box)
        # 词条区固定按满配 7 行（2 主+5 副）高度：卡片总高恒定、与词条数
        # 无关（真机根因：DPI 缩放下 pt 行高大于标称，固定像素总高会溢出
        # 挤掉汇总条；字体度量已含缩放，按它算行高即可）
        from PySide6.QtGui import QFontMetrics

        line_h = QFontMetrics(QFont(self.font().family(), 11)).height()
        entries_host.setFixedHeight(7 * line_h + 6 * 4 + 4)
        root.addWidget(entries_host)
        root.addSpacing(4)

        self.summary = SummaryBar()
        root.addWidget(self.summary)
        self._entry_labels: list[QLabel] = []
        self.setMinimumWidth(336)
        self.adjustSize()  # 总高一次性按布局算定（含 DPI），此后恒定

    def show_character(self, score: CharacterScore) -> None:
        if score.character == "default":
            self.char_label.setText("通用评分·未选角色")
        elif get_config(score.character).is_default:
            self.char_label.setText(f"{score.character}·通用权重")  # 库外新角色
        else:
            self.char_label.setText(score.character)
        self.summary.update_score(score)

    def show_echo(self, echo: EchoScore, character: CharacterScore, slot_index: int) -> None:
        """显示当前详情面板对应声骸的评分。

        slot_index: 0-4 槽位（汇总条对应格子高亮）。
        """
        self.grade_label.setText(echo.grade.upper())
        self.grade_label.setStyleSheet(
            f"color:{GRADE_COLORS[echo.grade].name()};"
            "background-color: rgba(255,255,255,30);"
            "border-radius: 5px; padding: 0 10px;"
        )
        self.score_label.setText(f"{echo.score:g} / 50")
        self.show_character(character)

        for label in self._entry_labels:
            label.deleteLater()
        self._entry_labels.clear()
        for entry in echo.entries:
            color = VALID_TIER_COLORS[entry.valid_tier].name()
            suffix = " ●" if entry.is_max_roll else ""
            text = (
                f"<span style='color:{color};font-weight:600'>{entry.name} "
                f"{_fmt_value(entry.name, entry.value)}{suffix}</span>"
            )
            label = QLabel(text)
            self.entries_box.addWidget(label)
            self._entry_labels.append(label)

        for i, slot in enumerate(self.summary.slots):
            if i == slot_index:
                slot.setStyleSheet(
                    "border: 1px solid rgba(255,255,255,150); border-radius: 4px;"
                    "background-color: rgba(255,255,255,40);"
                )
            elif slot.styleSheet():
                slot.setStyleSheet("")

    def set_slot_best(self, best: float | None) -> None:
        """头部副行：本槽历史最佳对比（同槽换声骸的取舍依据）。"""
        if best is None:
            self.best_label.setText("")
        else:
            self.best_label.setText(f"本槽最佳 {best:g}")


def preview() -> None:
    """开发预览：示例数据渲染评分卡（macOS 可用）。"""
    import sys

    from PySide6.QtWidgets import QApplication

    from wwechoes.scoring import Echo, StatEntry, score_echo_for_character
    from wwechoes.scoring.characters import get_config

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
    cfg = get_config(character)
    char_score = CharacterScore(
        character=character,
        echoes=(echo_score, None, None, None, None),
    )
    char_score.grade(cfg.total_grade)

    app = QApplication(sys.argv)
    card = ScoreCard()
    card.show_echo(echo_score, char_score, slot_index=0)
    card.resize(320, 420)
    card.show()
    sys.exit(app.exec())
