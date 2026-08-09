from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.visual_label import (
    DOWN,
    FLAT,
    INCOMPLETE_HORIZON,
    LABELED,
    UP,
    LabelSpec,
    compute_label,
    label_spec_id,
)


BASE_TIME = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
SPEC = LabelSpec(horizon_bars=2, up_threshold_bps=10.0, down_threshold_bps=-10.0)


def bar(index: int, close: float) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close, high=close, low=close, close=close,
        tick_count=2, tick_volume=2,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def test_rejects_empty_bars() -> None:
    with pytest.raises(ValueError):
        compute_label((), observation_end_at="irrelevant", spec=SPEC)


def test_rejects_mixed_symbol_or_timeframe() -> None:
    a = bar(0, 100.0)
    b = MarketBar(**{**a.__dict__, "symbol": "SILVER"})
    with pytest.raises(ValueError):
        compute_label((a, b), observation_end_at=a.end_at, spec=SPEC)


def test_rejects_non_positive_horizon_bars() -> None:
    bars = (bar(0, 100.0),)
    with pytest.raises(ValueError):
        compute_label(bars, observation_end_at=bars[0].end_at, spec=LabelSpec(0, 10.0, -10.0))


def test_rejects_up_threshold_below_down_threshold() -> None:
    bars = (bar(0, 100.0),)
    with pytest.raises(ValueError):
        compute_label(bars, observation_end_at=bars[0].end_at, spec=LabelSpec(2, -10.0, 10.0))


def test_rejects_unknown_observation_end_at() -> None:
    bars = (bar(0, 100.0), bar(1, 100.0))
    with pytest.raises(ValueError):
        compute_label(bars, observation_end_at="2099-01-01T00:00:00+00:00", spec=SPEC)


def test_incomplete_horizon_when_target_bar_does_not_exist_yet() -> None:
    bars = (bar(0, 100.0), bar(1, 100.0))
    result = compute_label(bars, observation_end_at=bars[0].end_at, spec=SPEC)
    assert result.status == INCOMPLETE_HORIZON
    assert result.label_value is None
    assert result.label_available_at is None
    assert result.return_bps is None


def test_up_classification_hand_verified() -> None:
    bars = (bar(0, 100.0), bar(1, 100.5), bar(2, 100.2))
    result = compute_label(bars, observation_end_at=bars[0].end_at, spec=SPEC)
    assert result.status == LABELED
    assert result.return_bps == pytest.approx(20.0)
    assert result.label_value == UP
    assert result.label_available_at == bars[2].end_at


def test_down_classification_hand_verified() -> None:
    bars = (bar(0, 100.0), bar(1, 99.9), bar(2, 99.8))
    result = compute_label(bars, observation_end_at=bars[0].end_at, spec=SPEC)
    assert result.return_bps == pytest.approx(-20.0)
    assert result.label_value == DOWN


def test_flat_classification_between_thresholds() -> None:
    bars = (bar(0, 100.0), bar(1, 100.02), bar(2, 100.05))
    result = compute_label(bars, observation_end_at=bars[0].end_at, spec=SPEC)
    assert result.return_bps == pytest.approx(5.0)
    assert result.label_value == FLAT


def test_boundary_exactly_at_up_threshold_is_up() -> None:
    bars = (bar(0, 100.0), bar(1, 100.0), bar(2, 100.1))
    result = compute_label(bars, observation_end_at=bars[0].end_at, spec=SPEC)
    assert result.return_bps == pytest.approx(10.0)
    assert result.label_value == UP


def test_boundary_exactly_at_down_threshold_is_down() -> None:
    bars = (bar(0, 100.0), bar(1, 100.0), bar(2, 99.9))
    result = compute_label(bars, observation_end_at=bars[0].end_at, spec=SPEC)
    assert result.return_bps == pytest.approx(-10.0)
    assert result.label_value == DOWN


def test_label_spec_id_is_deterministic_and_distinguishes_specs() -> None:
    a = label_spec_id(SPEC)
    b = label_spec_id(SPEC)
    c = label_spec_id(LabelSpec(3, 10.0, -10.0))
    assert a == b
    assert a != c
