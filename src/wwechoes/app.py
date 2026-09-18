"""应用入口编排（实现版）。

管线：capture(帧, WGC 自由线程) -> detect(前台校验 + 去抖状态机)
-> [DETAIL 态 + 槽位变化] ocr(词条区) -> scoring -> overlay(悬浮窗)。

线程模型：帧观测在捕获线程（纯 numpy，毫秒级）；OCR 与 GUI 在主线程
（Qt 跨线程 GUI 禁止，经 Signal 投递）。托盘 + 全局热键（仅监听，
RegisterHotKey）控制显隐；退出即停捕获。合规红线（ADR-0003）：
全链路只读截图，无内存读取/注入/输入模拟。
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
import threading

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from wwechoes.config import Settings, load_settings, save_settings
from wwechoes.detect import PageState, PageStateMachine, detect_slot, is_16_9, observe_page
from wwechoes.detect.roi import (
    DETAIL_ECHO_NAME,
    DETAIL_EQUIPPED_BY,
    DETAIL_MAIN_STATS,
    DETAIL_SUB_STATS,
)
from wwechoes.ocr.engine import OcrEngine
from wwechoes.scoring import Echo
from wwechoes.scoring.characters import get_config, known_characters
from wwechoes.scoring.engine import score_echo_for_character
from wwechoes.scoring.models import CharacterScore, EchoScore

#: 槽位 -> 该槽位声骸的 Cost（1×4 + 2×3 + 2×1）
SLOT_COST = {1: 4, 2: 3, 3: 3, 4: 1, 5: 1}

_WM_HOTKEY = 0x0312
_HOTKEY_ID = 0xBEE1


def _game_foreground(game_hwnd: int) -> bool:
    """前台校验：仅当游戏窗口在前台时观测有效（否则一律 UNKNOWN）。"""
    return ctypes.windll.user32.GetForegroundWindow() == game_hwnd


class Pipeline(QObject):
    """捕获线程 -> 主线程的桥（Signal 跨线程 queued）。"""

    detail_ready = Signal(int, object)  # (槽位 1..5, 帧拷贝)
    overlay_hide = Signal()

    def __init__(self, backend, game_hwnd: int, settings: Settings) -> None:
        super().__init__()
        self._backend = backend
        self._game_hwnd = game_hwnd
        self._settings = settings
        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._last_slot: int | None = None
        self._diag_keys: set[tuple[int, int]] = set()  # 已诊断过的帧尺寸

        def observer() -> PageState:
            with self._lock:
                frame = self._latest
            if frame is None or not _game_foreground(game_hwnd):
                return PageState.UNKNOWN
            return observe_page(frame)

        self._machine = PageStateMachine(observer, confirm_count=2, evidence_timeout=1.0)

    def start(self) -> None:
        self._backend.start(self._on_frame)

    def stop(self) -> None:
        self._backend.stop()

    def _diagnose(self, frame: np.ndarray) -> None:
        """帧尺寸变化时输出一次诊断（真机对齐排查用）。

        关注三点：帧尺寸（窗口模式约 1920×1049 客户区 / 全屏 1920×1080）、
        顶部是否有截图素材中的 31px 白条（WGC 抓窗口应不含其他置顶窗口，
        出现即说明对齐假设需复核）、16:9 校验。
        """
        h, w = frame.shape[:2]
        top = frame[2:30].astype(np.int16) if h >= 32 else np.zeros((1, 1, 3), np.int16)
        white_bar = bool(np.all(np.abs(top - (249, 244, 238)) < 12))
        print(
            f"[wwechoes] 捕获帧 {w}x{h}（16:9={is_16_9(w, h)}）"
            f" 顶部白条={'有(坐标对齐需复核)' if white_bar else '无(预期)'}",
            file=sys.stderr,
        )
        self._diag_keys.add((w, h))

    def _on_frame(self, frame: np.ndarray) -> None:
        """捕获线程回调：仅做检测与状态机（无 GUI 调用）。"""
        with self._lock:
            self._latest = frame
        key = (frame.shape[1], frame.shape[0])
        if key not in self._diag_keys:
            self._diagnose(frame)
        state = self._machine.tick()
        if state is PageState.DETAIL:
            slot = detect_slot(frame)
            if slot is not None and slot != self._last_slot:
                self._last_slot = slot
                self.detail_ready.emit(slot, frame.copy())
        elif self._last_slot is not None:
            self._last_slot = None
            self.overlay_hide.emit()


class AppRuntime:
    """主线程装配：悬浮窗 + OCR + 评分 + 托盘 + 热键。"""

    def __init__(self, app: QApplication, backend, game_hwnd: int, settings: Settings) -> None:
        from wwechoes.overlay.view import ScoreCard
        from wwechoes.overlay.win_overlay import Corner, OverlayWindow

        self._app = app
        self._settings = settings
        self._overlay_enabled = True  # 热键切换的手动总开关
        self._ocr = OcrEngine()
        self._scores: dict[int, EchoScore] = {}  # slot -> EchoScore（会话内累计）
        self._slot_best: dict[int, tuple[float, str]] = {}  # slot -> (最高分, 声骸名)

        self.card = ScoreCard()
        corner = Corner(settings.overlay_corner.replace("-", "_"))  # "top-right" -> "top_right"
        anchor = tuple(settings.overlay_anchor_pos) if settings.overlay_use_anchor else None
        self.overlay = OverlayWindow(content=self.card, corner=corner, anchor_pos=anchor)

        self.pipeline = Pipeline(backend, game_hwnd, settings)
        self.pipeline.detail_ready.connect(self._on_detail)
        self.pipeline.overlay_hide.connect(self._on_hide)
        self._game_hwnd = game_hwnd
        self._last_detail: tuple[int, np.ndarray] | None = None  # (slot, frame)，选角色后重评用

        # hide 去抖：切槽位动画期间检测短暂回落 UNKNOWN，直接 hide 会闪烁
        from PySide6.QtCore import QTimer

        self._hide_timer = QTimer(self._app)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(450)
        self._hide_timer.timeout.connect(lambda: self.overlay.hide())

        self._register_hotkey()
        self._setup_tray()
        self._follow_timer = None

    def start_following(self) -> None:
        """轮询游戏窗口位置，悬浮窗跟随（move 级开销，非逐帧重绘）。"""
        from PySide6.QtCore import QTimer

        self._last_ref = self._game_client_rect()
        self._follow_timer = QTimer(self._app)
        self._follow_timer.timeout.connect(self._on_follow_tick)
        self._follow_timer.start(400)

    def _on_follow_tick(self) -> None:
        ref = self._game_client_rect()
        if ref != self._last_ref:
            self._last_ref = ref
            if self.overlay.is_visible:
                self.overlay.reposition(ref)

    def _game_client_rect(self) -> tuple[int, int, int, int]:
        """游戏客户区的屏幕坐标矩形（悬浮窗定位参考；窗口模式游戏不铺满屏）。"""
        user32 = ctypes.windll.user32
        pt = ctypes.wintypes.POINT(0, 0)
        user32.ClientToScreen(self._game_hwnd, ctypes.byref(pt))
        rect = ctypes.wintypes.RECT()
        user32.GetClientRect(self._game_hwnd, ctypes.byref(rect))
        return (pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top)

    # --- 详情面板处理（主线程）---

    def _current_character(self) -> str:
        s = self._settings
        return s.manual_character or s.last_character or "default"

    def _auto_detect_character(self, frame: np.ndarray) -> str | None:
        """从详情面板底部"XX装配中"横条 OCR 角色名（手动选择优先时跳过）。

        实测（真机帧）：该行 OCR 干净命中；名字不在评分库（新角色，社区
        数据源均未收录）时也采纳——按通用权重评分但角色名正确显示，
        vendor 数据更新后自动升级为专属权重。
        """
        if self._settings.manual_character:
            return None
        import re

        known = set(known_characters())
        for line in self._ocr.read_lines(frame, DETAIL_EQUIPPED_BY):
            m = re.search(r"([\u4e00-\u9fff]{1,10})装配中", line)
            if not m:
                continue
            name = m.group(1)
            if len(name) < 2:
                continue
            if name in known:
                return self._adopt_character(name)
            # OCR 噪声容错：已知角色名作为子串出现（如"爱弥斯装配中"混入杂字）
            for k in known:
                if k in name or name in k:
                    return self._adopt_character(k)
            return self._adopt_character(name)  # 库外新角色：名字照采，权重用通用
        return None

    def _adopt_character(self, name: str) -> str:
        if self._settings.last_character != name:
            self._settings.last_character = name
            save_settings(self._settings)
            self._rebuild_tray_menu()
        return name

    def _on_detail(self, slot: int, frame: np.ndarray) -> None:
        self._hide_timer.stop()  # 取消挂起的 hide（切槽位动画去抖）
        self._last_detail = (slot, frame)
        mains = self._ocr.read_stats(frame, DETAIL_MAIN_STATS)
        subs = self._ocr.read_stats(frame, DETAIL_SUB_STATS)
        character = self._auto_detect_character(frame) or self._current_character()
        echo = Echo(cost=SLOT_COST[slot], main_stats=tuple(mains), sub_stats=tuple(subs))
        echo_score, _cfg = score_echo_for_character(echo, character)

        # 本槽历史最佳（声骸名区分同槽不同件，换装取舍依据）
        name_line = " ".join(self._ocr.read_lines(frame, DETAIL_ECHO_NAME))
        best = self._slot_best.get(slot)
        is_new_best = best is None or echo_score.score > best[0]
        if is_new_best:
            self._slot_best[slot] = (echo_score.score, name_line)
        self.card.set_slot_best(None if is_new_best else best[0])

        self._scores[slot] = echo_score
        echoes = tuple(self._scores.get(k) for k in range(1, 6))
        char_score = CharacterScore(character=character, echoes=echoes)
        char_score.grade(get_config(character).total_grade)
        self.card.show_echo(echo_score, char_score, slot_index=slot - 1)
        ref = self._game_client_rect()
        if self._overlay_enabled:
            self.overlay.show_no_activate(ref)
        elif self.overlay.is_visible:
            self.overlay.reposition(ref)

    def _on_hide(self) -> None:
        self._hide_timer.start()

    def _select_character(self, name: str) -> None:
        """托盘手动选角色：持久化 + 用最近详情帧立即重评（含汇总重置）。"""
        self._settings.manual_character = name
        self._settings.last_character = name
        save_settings(self._settings)
        self._scores.clear()  # 切角色 = 汇总条与本槽最佳重置（产品语义）
        self._slot_best.clear()
        if self._last_detail is not None:
            slot, frame = self._last_detail
            self._last_detail = None
            self._on_detail(slot, frame)
        self._rebuild_tray_menu()

    # --- 热键（仅监听，不注入输入）---

    def _register_hotkey(self) -> None:
        from PySide6.QtCore import QAbstractNativeEventFilter

        user32 = ctypes.windll.user32
        mods, vk = _parse_hotkey(self._settings.hotkey_toggle)
        ok = user32.RegisterHotKey(None, _HOTKEY_ID, mods, vk)
        if not ok:
            hotkey = self._settings.hotkey_toggle
            print(f"[warn] 热键 {hotkey} 注册失败（可能被其他程序占用）", file=sys.stderr)
            return

        runtime = self

        class HotkeyFilter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):  # noqa: N802
                if event_type == b"windows_generic_MSG":
                    msg = ctypes.wintypes.MSG.from_address(int(message))
                    if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                        runtime._overlay_enabled = not runtime._overlay_enabled
                        if runtime._overlay_enabled:
                            if runtime._scores:
                                runtime.overlay.show_no_activate()
                        else:
                            runtime.overlay.hide()
                        return True, 0
                return False, 0

        self._hotkey_filter = HotkeyFilter()
        self._app.installNativeEventFilter(self._hotkey_filter)

    def unregister_hotkey(self) -> None:
        ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)

    # --- 托盘 ---

    def _setup_tray(self) -> None:
        # 程序化图标（无资源文件）：深底金圈
        pix = QPixmap(64, 64)
        pix.fill(QColor("#15181e"))
        painter = QPainter(pix)
        painter.setBrush(QColor("#e6b422"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(14, 14, 36, 36)
        painter.end()
        tray = QSystemTrayIcon(QIcon(pix))
        tray.setToolTip("WWEchoes 声骸评分（Alt+E 切换显示）")
        tray.show()
        self._tray = tray
        self._rebuild_tray_menu()

    def _rebuild_tray_menu(self) -> None:
        """托盘菜单：当前角色状态 + 角色选择 + 位置微调 + 退出（选角后重建）。"""
        from wwechoes.scoring.characters import known_characters

        menu = QMenu()
        current = self._current_character()
        label = "当前角色：default（通用权重）" if current == "default" else f"当前角色：{current}"
        menu.addAction(label).setEnabled(False)

        char_menu = menu.addMenu("选择角色")
        for name in known_characters():
            act = char_menu.addAction(("● " if name == current else "") + name)
            act.triggered.connect(lambda checked=False, n=name: self._select_character(n))

        pos_menu = menu.addMenu("悬浮窗位置微调（20px/步）")
        for text, dx, dy in (
            ("← 左移", -20, 0), ("→ 右移", 20, 0),
            ("↑ 上移", 0, -20), ("↓ 下移", 0, 20),
        ):
            act = pos_menu.addAction(text)
            act.triggered.connect(lambda checked=False, dx=dx, dy=dy: self._adjust_anchor(dx, dy))

        menu.addSeparator()
        menu.addAction("退出").triggered.connect(self._app.quit)
        self._tray.setContextMenu(menu)

    def _adjust_anchor(self, dx: int, dy: int) -> None:
        """托盘位置微调：改锚点 + 持久化 + 立即重定位。"""
        pos = self._settings.overlay_anchor_pos
        self._settings.overlay_anchor_pos = [pos[0] + dx, pos[1] + dy]
        save_settings(self._settings)
        if self._settings.overlay_use_anchor:
            self.overlay.set_anchor_pos(tuple(self._settings.overlay_anchor_pos))


def _messagebox_error(*lines: str) -> None:
    """无控制台（双击 exe）场景下的错误弹窗兜底。"""
    ctypes.windll.user32.MessageBoxW(None, "\n".join(lines), "WWEchoes", 0x10)  # MB_ICONERROR


def _parse_hotkey(text: str) -> tuple[int, int]:
    """'Alt+E' -> (MOD_ALT, vk)；支持 Ctrl/Alt/Shift 修饰与单字符键。"""
    MOD_ALT, MOD_CONTROL, MOD_SHIFT = 0x1, 0x2, 0x4
    mods = 0
    key = ""
    for part in text.split("+"):
        part = part.strip().lower()
        if part == "alt":
            mods |= MOD_ALT
        elif part == "ctrl" or part == "control":
            mods |= MOD_CONTROL
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part:
            key = part
    vk = ord(key.upper()) if key and key.isascii() else ord("E")
    return mods, vk


def main() -> int:
    if sys.platform != "win32":
        print(
            "WWEchoes 运行时仅支持 Windows。\n"
            "开发提示：mac 会话请跑 pytest / ScoreCard 预览（python -m wwechoes.overlay.view）",
            file=sys.stderr,
        )
        return 1

    from wwechoes.capture.win_wgc import WgcCaptureBackend, ensure_per_monitor_v2, find_game_hwnd

    ensure_per_monitor_v2()
    settings = load_settings()

    try:
        game_hwnd = find_game_hwnd()
    except LookupError as e:
        print(f"[error] {e}", file=sys.stderr)
        hint = "请先启动游戏再运行 WWEchoes（若已启动仍报错，试试切换游戏内显示模式为『窗口』）。"
        print(hint, file=sys.stderr)
        _messagebox_error(str(e), hint)
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 悬浮窗 hide 不退出，托盘退出

    try:
        backend = WgcCaptureBackend(hwnd=game_hwnd)
    except (LookupError, RuntimeError) as e:
        print(f"[error] 捕获初始化失败: {e}", file=sys.stderr)
        return 1

    runtime = AppRuntime(app, backend, game_hwnd, settings)
    runtime.pipeline.start()
    runtime.start_following()
    try:
        return app.exec()
    finally:
        runtime.unregister_hotkey()
        runtime.pipeline.stop()


if __name__ == "__main__":
    raise SystemExit(main())
