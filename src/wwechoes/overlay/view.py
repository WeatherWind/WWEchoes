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

from wwechoes.scoring.models import CharacterScore, EchoScore

#: 等级 -> 颜色（SSS 金 / SS S 橙紫 / A 蓝 / B 绿 / C 灰）
GRADE_COLORS = {
    "sss": QColor("#e6b422"),
    "ss": QColor("#d29415"),
    "s": QColor("#b07fd8"),
    "a": QColor("#4a90d9"),
    "b": QColor("#5bbd6b"),
    "c": QColor("#8a8a8a"),
    None: QColor("#555555"),
}

VALID_TIER_COLORS = {
    "s": QColor("#e6b422"),
    "a": QColor("#9d7bd8"),
    "b": QColor("#5bbd6b"),
    None: QColor("#cccccc"),
}


class SummaryBar(QFrame):
    """底部 5 槽位汇总条（含整套总分）。"""

    def __init__(self) -> None:
        super().__init__()
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
        self.total = QLabel("0.0")
        self.total.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
                slot.setStyleSheet(f"color:{GRADE_COLORS[echo.grade].name()};font-weight:bold;")
        self.total.setText(f"{score.total:g} / 250")


class ScoreCard(QWidget):
    """单件声骸评分卡：头部（角色/等级/分数）+ 逐词条明细 + 汇总条。"""

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(4)

        header = QHBoxLayout()
        self.char_label = QLabel("—")
        self.char_label.setFont(QFont(self.font().family(), 12, QFont.Weight.Bold))
        self.grade_label = QLabel("--")
        self.grade_label.setFont(QFont(self.font().family(), 16, QFont.Weight.Black))
        self.score_label = QLabel("0.0")
        self.score_label.setFont(QFont(self.font().family(), 12))
        header.addWidget(self.char_label)
        header.addStretch(1)
        header.addWidget(self.grade_label)
        header.addWidget(self.score_label)
        root.addLayout(header)

        self.entries_box = QVBoxLayout()
        self.entries_box.setSpacing(0)
        root.addLayout(self.entries_box)
        root.addSpacing(6)

        self.summary = SummaryBar()
        root.addWidget(self.summary)
        self._entry_labels: list[QLabel] = []

    def show_character(self, score: CharacterScore) -> None:
        self.char_label.setText(score.character)
        self.summary.update_score(score)

    def show_echo(self, echo: EchoScore, character: CharacterScore, slot_index: int) -> None:
        """显示当前详情面板对应声骸的评分。

        slot_index: 0-4 槽位（汇总条对应格子高亮由 UI 细化迭代处理）。
        """
        self.grade_label.setText(echo.grade.upper())
        self.grade_label.setStyleSheet(f"color:{GRADE_COLORS[echo.grade].name()};")
        self.score_label.setText(f"{echo.score:g} / 50")
        self.show_character(character)

        for label in self._entry_labels:
            label.deleteLater()
        self._entry_labels.clear()
        for entry in echo.entries:
            color = VALID_TIER_COLORS[entry.valid_tier].name()
            suffix = " ●" if entry.is_max_roll else ""
            text = f"<span style='color:{color}'>{entry.name} {entry.value:g}{suffix}</span>"
            label = QLabel(text)
            self.entries_box.addWidget(label)
            self._entry_labels.append(label)


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
