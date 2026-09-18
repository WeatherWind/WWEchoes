"""游戏页面状态检测（去抖状态机）。

范式参考 WWMAP-TOOLS 的 MapUiStateController：观测证据需连续
``confirm_count`` 次一致才切换稳定态，避免页面切换动画造成误判。
模板匹配本身（OpenCV matchTemplate）由 Windows 会话在 capture 管线中
实现，本模块只负责状态机逻辑，便于在任意平台单测。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum, auto


class PageState(Enum):
    """悬浮窗可见性依据的游戏页面状态。"""

    UNKNOWN = auto()  # 不在装配页（或游戏未前台）
    ASSEMBLY = auto()  # 装配页（未打开详情面板）
    DETAIL = auto()  # 装配页 + 声骸详情面板已打开（触发评分）


class PageStateMachine:
    """观测 -> 稳定状态的去抖状态机。

    observer: 返回当前瞬时观测（如模板匹配得分超阈值的判定结果）；
    evidence_timeout: 稳定态超过该秒数没有新观测确认时回落 UNKNOWN
    （范式参考 WWMAP-TOOLS OverlayVisibilityPolicy 的 500ms 新鲜度）。
    """

    def __init__(
        self,
        observer: Callable[[], PageState],
        confirm_count: int = 2,
        evidence_timeout: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._observer = observer
        self._confirm = confirm_count
        self._timeout = evidence_timeout
        self._clock = clock
        self._state = PageState.UNKNOWN
        self._candidate: PageState | None = None
        self._candidate_count = 0
        self._last_confirmed_at: float | None = None

    @property
    def state(self) -> PageState:
        """当前稳定状态（含新鲜度超时检查）。"""
        if self._state is not PageState.UNKNOWN and self._last_confirmed_at is not None:
            if self._clock() - self._last_confirmed_at > self._timeout:
                self._state = PageState.UNKNOWN
        return self._state

    def tick(self) -> PageState:
        """一次观测周期：读取瞬时观测，维护候选/稳定状态。"""
        observed = self._observer()
        now = self._clock()
        if observed == self._state:
            self._candidate = None
            self._candidate_count = 0
            self._last_confirmed_at = now
            return self.state

        if observed == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = observed
            self._candidate_count = 1

        if self._candidate_count >= self._confirm:
            self._state = observed
            self._candidate = None
            self._candidate_count = 0
            self._last_confirmed_at = now
        return self.state
