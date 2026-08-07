from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import statistics

from backend.app.analysis.bars import TIMEFRAME_SECONDS
from backend.app.database.tick_replay_repository import ReplayTick


TICK_RATE_VERSION = "1.0.0"
QUANTILE_METHOD = "linear-interpolation-v1"
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class DistributionSummary:
    status: str
    n_total: int
    n_valid: int
    mean: float | None
    median: float | None
    std_dev: float | None
    minimum: float | None
    maximum: float | None
    p95: float | None
    p99: float | None


@dataclass(frozen=True)
class TickRateResult:
    version: str
    symbol: str
    timeframe: str
    total_window_count: int
    populated_window_count: int
    empty_window_count: int
    window_tick_count: DistributionSummary
    window_ticks_per_second: DistributionSummary
    interval_seconds: DistributionSummary
    same_timestamp_tick_count: int
    fingerprint: str
    quantile_method: str = QUANTILE_METHOD
    interpretation: str = "research_observation_not_trading_signal"


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value.astimezone(UTC)


def _timestamp(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")), "event_timestamp")


def _window_start(value: datetime, seconds: int) -> datetime:
    epoch_seconds = int(value.timestamp())
    return datetime.fromtimestamp(epoch_seconds - epoch_seconds % seconds, tz=UTC)


def _total_window_count(start_at: datetime, end_at: datetime, seconds: int) -> int:
    first = _window_start(start_at, seconds)
    span = (end_at - first).total_seconds()
    if span < seconds:
        return 0
    return int(span // seconds)


def _quantile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _summarize(values: list[float], *, n_total: int, minimum_sample: int) -> DistributionSummary:
    n_valid = len(values)
    if n_valid < minimum_sample:
        return DistributionSummary(INSUFFICIENT_DATA, n_total, n_valid, None, None, None, None, None, None, None)
    ordered = sorted(values)
    return DistributionSummary(
        COMPLETED, n_total, n_valid,
        statistics.fmean(ordered),
        statistics.median(ordered),
        statistics.stdev(ordered) if len(ordered) > 1 else 0.0,
        ordered[0],
        ordered[-1],
        _quantile(ordered, 0.95),
        _quantile(ordered, 0.99),
    )


def _fingerprint(
    *, symbol: str, timeframe: str, minimum_sample: int,
    window_tick_count: DistributionSummary, window_ticks_per_second: DistributionSummary,
    interval_seconds: DistributionSummary, same_timestamp_tick_count: int,
) -> str:
    payload = {
        "version": TICK_RATE_VERSION, "symbol": symbol, "timeframe": timeframe,
        "minimum_sample": minimum_sample,
        "window_tick_count": asdict(window_tick_count),
        "window_ticks_per_second": asdict(window_ticks_per_second),
        "interval_seconds": asdict(interval_seconds),
        "same_timestamp_tick_count": same_timestamp_tick_count,
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_tick_rate_statistics(
    ticks: Iterable[ReplayTick], *, symbol: str, timeframe: str,
    start_at: datetime, end_at: datetime, minimum_sample: int = 30,
) -> TickRateResult:
    """SA-004 tick speed/interval: how densely ticks arrive, independent of
    price quality. Unlike `bars.py` (which only keeps ticks with a valid
    positive bid/ask pair, since it builds a mid-price series), this counts
    EVERY tick with a parseable timestamp -- arrival rate is a property of
    the feed, not of price validity, and the contract explicitly warns not
    to equate tick rate with liquidity or real trade volume.

    Per-window `window_tick_count`/`window_ticks_per_second` are aggregated
    across all populated windows (one point per window, same convention as
    SA-003 spread); `interval_seconds` (the gap between canonically-ordered
    consecutive ticks) is aggregated across the whole requested range rather
    than re-bucketed per window, since a single window often has too few
    ticks for its own percentile to mean anything.

    Windows are epoch-aligned exactly like `bars.py`'s window definition, so
    `populated_window_count` lines up with the bar count a caller would get
    from `build_closed_mid_bars` at the same timeframe. `empty_window_count`
    covers windows with zero ticks; a separate "partial boundary window"
    count is deliberately not reported in this first increment -- epoch
    alignment already treats a window clipped by `start_at`/`end_at` the
    same as any other window (bars.py does the same), and distinguishing it
    would need session-level tick-density modelling this platform does not
    have yet.
    """
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"timeframe must be one of: {', '.join(TIMEFRAME_SECONDS)}")
    if isinstance(minimum_sample, bool) or not isinstance(minimum_sample, int) or minimum_sample < 1:
        raise ValueError("minimum_sample must be a positive integer")
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    normalized_start = _utc(start_at, "start_at")
    normalized_end = _utc(end_at, "end_at")
    if normalized_start >= normalized_end:
        raise ValueError("start_at must be before end_at")

    seconds = TIMEFRAME_SECONDS[timeframe]
    filtered: list[ReplayTick] = []
    for tick in ticks:
        if tick.symbol != normalized_symbol:
            raise ValueError("all ticks must match the requested symbol")
        timestamp = _timestamp(tick.event_timestamp)
        if normalized_start <= timestamp < normalized_end:
            filtered.append(tick)
    filtered.sort(key=lambda tick: (_timestamp(tick.event_timestamp), tick.event_id))

    total_window_count = _total_window_count(normalized_start, normalized_end, seconds)
    window_buckets: dict[datetime, int] = {}
    for tick in filtered:
        window_start = _window_start(_timestamp(tick.event_timestamp), seconds)
        if window_start + timedelta(seconds=seconds) > normalized_end:
            continue
        window_buckets[window_start] = window_buckets.get(window_start, 0) + 1
    populated_window_count = len(window_buckets)
    empty_window_count = max(0, total_window_count - populated_window_count)

    tick_counts = [float(count) for count in window_buckets.values()]
    ticks_per_second = [count / seconds for count in tick_counts]

    intervals: list[float] = []
    same_timestamp_tick_count = 0
    for previous, current in zip(filtered, filtered[1:]):
        gap = (_timestamp(current.event_timestamp) - _timestamp(previous.event_timestamp)).total_seconds()
        intervals.append(gap)
        if gap == 0.0:
            same_timestamp_tick_count += 1

    window_tick_count = _summarize(tick_counts, n_total=total_window_count, minimum_sample=minimum_sample)
    window_ticks_per_second = _summarize(ticks_per_second, n_total=total_window_count, minimum_sample=minimum_sample)
    interval_seconds = _summarize(intervals, n_total=max(0, len(filtered) - 1), minimum_sample=minimum_sample)

    return TickRateResult(
        TICK_RATE_VERSION, normalized_symbol, timeframe,
        total_window_count, populated_window_count, empty_window_count,
        window_tick_count, window_ticks_per_second, interval_seconds, same_timestamp_tick_count,
        _fingerprint(
            symbol=normalized_symbol, timeframe=timeframe, minimum_sample=minimum_sample,
            window_tick_count=window_tick_count, window_ticks_per_second=window_ticks_per_second,
            interval_seconds=interval_seconds, same_timestamp_tick_count=same_timestamp_tick_count,
        ),
    )
