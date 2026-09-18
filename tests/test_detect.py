"""ROI 缩放与页面状态机单测（纯逻辑，任意平台可跑）。"""

from __future__ import annotations

from wwechoes.detect import PageState, PageStateMachine, Roi, is_16_9, scale_roi


def test_scale_roi_2x():
    roi = Roi(100, 200, 300, 50)
    scaled = scale_roi(roi, 2560, 1440)
    assert (scaled.x, scaled.y, scaled.w, scaled.h) == (133, 267, 400, 67)


def test_scale_roi_identity():
    roi = Roi(10, 20, 30, 40)
    assert scale_roi(roi, 1920, 1080) == roi


def test_is_16_9():
    assert is_16_9(1920, 1080)
    assert is_16_9(2560, 1440)
    assert is_16_9(3840, 2160)
    assert not is_16_9(1920, 1200)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_machine(observations: list[PageState]):
    """observer 依次弹出观测；时钟可控。"""
    it = iter(observations)

    def observe() -> PageState:
        try:
            return next(it)
        except StopIteration:
            return PageState.UNKNOWN

    clock = FakeClock()
    return PageStateMachine(observe, confirm_count=2, evidence_timeout=0.5, clock=clock), clock


def test_state_machine_requires_confirmation():
    m, _ = make_machine([PageState.DETAIL, PageState.UNKNOWN, PageState.DETAIL, PageState.DETAIL])
    assert m.tick() is PageState.UNKNOWN  # 第 1 次观测：候选，不切换
    assert m.tick() is PageState.UNKNOWN  # 观测不一致：候选重置
    assert m.tick() is PageState.UNKNOWN  # 第 1 次 DETAIL
    assert m.tick() is PageState.DETAIL  # 连续第 2 次：切换


def test_state_machine_evidence_timeout():
    m, clock = make_machine([PageState.DETAIL, PageState.DETAIL])
    m.tick()
    assert m.tick() is PageState.DETAIL
    clock.now = 0.6  # 超过 0.5s 无新确认
    assert m.state is PageState.UNKNOWN


def test_state_machine_same_state_refreshes_evidence():
    m, clock = make_machine([PageState.DETAIL, PageState.DETAIL, PageState.DETAIL])
    m.tick()
    m.tick()
    clock.now = 0.4
    assert m.tick() is PageState.DETAIL  # 稳定态内再次观测：刷新新鲜度
    clock.now = 0.8
    assert m.state is PageState.DETAIL  # 距上次确认 0.4s，未超时
