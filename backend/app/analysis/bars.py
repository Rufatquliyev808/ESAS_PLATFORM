from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import math

from backend.app.database.tick_replay_repository import ReplayTick


BAR_BUILDER_VERSION = "1.1.0"
TIMEFRAME_SECONDS = {
    "S1": 1,
    "S10": 10,
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
}


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    timeframe: str
    start_at: str
    end_at: str
    open: float
    high: float
    low: float
    close: float
    tick_count: int
    tick_volume: int
    spread_min: float
    spread_max: float
    spread_mean: float
    first_event_id: str
    last_event_id: str
    builder_version: str = BAR_BUILDER_VERSION


@dataclass(frozen=True)
class BarBuildResult:
    bars: tuple[MarketBar, ...]
    timeframe: str
    source_fingerprint: str
    fingerprint: str
    builder_version: str = BAR_BUILDER_VERSION


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _timestamp(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), "event_timestamp")


def _bar_start(value: datetime, seconds: int) -> datetime:
    epoch_seconds = int(value.timestamp())
    return datetime.fromtimestamp(epoch_seconds - epoch_seconds % seconds, tz=UTC)


def _fingerprint(
    bars: tuple[MarketBar, ...], *, timeframe: str, source_fingerprint: str
) -> str:
    payload = {
        "bars": [asdict(bar) for bar in bars],
        "builder_version": BAR_BUILDER_VERSION,
        "source_fingerprint": source_fingerprint,
        "timeframe": timeframe,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def build_closed_mid_bars(
    ticks: Iterable[ReplayTick],
    *,
    timeframe: str,
    end_at: datetime,
    source_fingerprint: str,
) -> BarBuildResult:
    """Build closed UTC bars without filling missing intervals or changing ticks."""
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"timeframe must be one of: {', '.join(TIMEFRAME_SECONDS)}")
    normalized_fingerprint = source_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("source_fingerprint must not be empty")

    normalized_end = _utc(end_at, "end_at")
    seconds = TIMEFRAME_SECONDS[timeframe]
    ordered = sorted(
        ticks, key=lambda tick: (_timestamp(tick.event_timestamp), tick.event_id)
    )
    grouped: dict[datetime, list[tuple[ReplayTick, float, float]]] = {}

    for tick in ordered:
        timestamp = _timestamp(tick.event_timestamp)
        if timestamp >= normalized_end:
            continue
        if not all(math.isfinite(value) for value in (tick.bid, tick.ask)):
            continue
        if tick.bid <= 0 or tick.ask <= 0 or tick.ask < tick.bid:
            continue

        start = _bar_start(timestamp, seconds)
        if start + timedelta(seconds=seconds) > normalized_end:
            continue
        grouped.setdefault(start, []).append(
            (tick, (tick.bid + tick.ask) / 2.0, tick.ask - tick.bid)
        )

    bars: list[MarketBar] = []
    for start in sorted(grouped):
        items = grouped[start]
        mids = [item[1] for item in items]
        spreads = [item[2] for item in items]
        bars.append(
            MarketBar(
                symbol=items[0][0].symbol,
                timeframe=timeframe,
                start_at=start.isoformat(timespec="microseconds"),
                end_at=(start + timedelta(seconds=seconds)).isoformat(timespec="microseconds"),
                open=mids[0],
                high=max(mids),
                low=min(mids),
                close=mids[-1],
                tick_count=len(items),
                tick_volume=sum(item[0].volume for item in items),
                spread_min=min(spreads),
                spread_max=max(spreads),
                spread_mean=sum(spreads) / len(spreads),
                first_event_id=items[0][0].event_id,
                last_event_id=items[-1][0].event_id,
            )
        )

    result_bars = tuple(bars)
    return BarBuildResult(
        bars=result_bars,
        timeframe=timeframe,
        source_fingerprint=normalized_fingerprint,
        fingerprint=_fingerprint(
            result_bars,
            timeframe=timeframe,
            source_fingerprint=normalized_fingerprint,
        ),
    )
