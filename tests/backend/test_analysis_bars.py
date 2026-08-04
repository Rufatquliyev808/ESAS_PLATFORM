from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import BAR_BUILDER_VERSION, build_closed_mid_bars
from backend.app.database.tick_replay_repository import ReplayTick


BASE_TIME = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def tick(event_id: str, offset: timedelta, *, bid: float, ask: float, volume: int = 1) -> ReplayTick:
    timestamp = BASE_TIME + offset
    timestamp_text = timestamp.isoformat(timespec="microseconds")
    return ReplayTick(
        event_id=event_id,
        event_type="TICK_RECEIVED",
        event_timestamp=timestamp_text,
        received_at=timestamp_text,
        symbol="GOLD",
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        volume=volume,
        flags=6,
        source_time_msc=int(timestamp.timestamp() * 1000),
        source="esas.mt5.bridge",
        event_version="1.0",
        module_version="1.6.1",
    )


def build(items, *, end_at=None, timeframe="M1"):
    return build_closed_mid_bars(
        items,
        timeframe=timeframe,
        end_at=end_at or BASE_TIME + timedelta(minutes=2),
        source_fingerprint="sha256:source",
    )


def test_builds_deterministic_mid_ohlc_and_lineage() -> None:
    items = [
        tick("event:3", timedelta(seconds=30), bid=101, ask=103, volume=3),
        tick("event:1", timedelta(seconds=1), bid=99, ask=101, volume=1),
        tick("event:2", timedelta(seconds=20), bid=103, ask=105, volume=2),
    ]
    first = build(items)
    second = build(reversed(items))
    assert first == second
    assert first.builder_version == BAR_BUILDER_VERSION
    assert len(first.bars) == 1
    bar = first.bars[0]
    assert (bar.open, bar.high, bar.low, bar.close) == (100, 104, 100, 102)
    assert (bar.tick_count, bar.tick_volume) == (3, 6)
    assert (bar.spread_min, bar.spread_max, bar.spread_mean) == (2, 2, 2)
    assert (bar.first_event_id, bar.last_event_id) == ("event:1", "event:3")


@pytest.mark.parametrize("timeframe", ["M1", "M5", "M15", "H1"])
def test_supports_initial_timeframes(timeframe: str) -> None:
    result = build(
        [tick("event:1", timedelta(seconds=1), bid=100, ask=102)],
        timeframe=timeframe,
        end_at=BASE_TIME + timedelta(hours=1),
    )
    assert result.timeframe == timeframe
    assert len(result.bars) == 1


def test_open_bar_is_not_returned() -> None:
    result = build(
        [tick("event:1", timedelta(seconds=30), bid=100, ask=102)],
        end_at=BASE_TIME + timedelta(seconds=59),
    )
    assert result.bars == ()


def test_missing_interval_is_not_forward_filled() -> None:
    result = build(
        [
            tick("event:1", timedelta(seconds=1), bid=100, ask=102),
            tick("event:2", timedelta(minutes=2, seconds=1), bid=102, ask=104),
        ],
        end_at=BASE_TIME + timedelta(minutes=3),
    )
    assert [bar.start_at for bar in result.bars] == [
        BASE_TIME.isoformat(timespec="microseconds"),
        (BASE_TIME + timedelta(minutes=2)).isoformat(timespec="microseconds"),
    ]


def test_invalid_prices_are_excluded() -> None:
    result = build(
        [
            tick("valid", timedelta(seconds=1), bid=100, ask=102),
            tick("crossed", timedelta(seconds=2), bid=103, ask=102),
            tick("zero", timedelta(seconds=3), bid=0, ask=1),
        ]
    )
    assert result.bars[0].tick_count == 1
    assert result.bars[0].first_event_id == "valid"


def test_requires_safe_versioned_inputs() -> None:
    items = [tick("event:1", timedelta(seconds=1), bid=100, ask=102)]
    with pytest.raises(ValueError, match="timeframe"):
        build_closed_mid_bars(
            items,
            timeframe="M2",
            end_at=BASE_TIME + timedelta(minutes=1),
            source_fingerprint="sha256:source",
        )
    with pytest.raises(ValueError, match="source_fingerprint"):
        build_closed_mid_bars(
            items,
            timeframe="M1",
            end_at=BASE_TIME + timedelta(minutes=1),
            source_fingerprint=" ",
        )
