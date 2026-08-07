from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import statistics

from backend.app.analysis.bars import TIMEFRAME_SECONDS
from backend.app.database.tick_replay_repository import ReplayTick


TICK_VOLUME_VERSION = "1.0.0"
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
class FlagCombination:
    flags: int
    count: int


@dataclass(frozen=True)
class VersionSegment:
    module_version: str
    event_version: str
    count: int


@dataclass(frozen=True)
class TickVolumeResult:
    version: str
    symbol: str
    timeframe: str
    n_total: int
    n_zero_volume: int
    n_positive_volume: int
    tick_volume: DistributionSummary
    window_volume_sum: DistributionSummary
    flag_combinations: tuple[FlagCombination, ...]
    version_segments: tuple[VersionSegment, ...]
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
    *, symbol: str, timeframe: str, minimum_sample: int, n_total: int,
    n_zero_volume: int, n_positive_volume: int, tick_volume: DistributionSummary,
    window_volume_sum: DistributionSummary, flag_combinations: tuple[FlagCombination, ...],
    version_segments: tuple[VersionSegment, ...],
) -> str:
    payload = {
        "version": TICK_VOLUME_VERSION, "symbol": symbol, "timeframe": timeframe,
        "minimum_sample": minimum_sample, "n_total": n_total,
        "n_zero_volume": n_zero_volume, "n_positive_volume": n_positive_volume,
        "tick_volume": asdict(tick_volume), "window_volume_sum": asdict(window_volume_sum),
        "flag_combinations": [asdict(item) for item in flag_combinations],
        "version_segments": [asdict(item) for item in version_segments],
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_tick_volume_statistics(
    ticks: Iterable[ReplayTick], *, symbol: str, timeframe: str,
    start_at: datetime, end_at: datetime, minimum_sample: int = 30,
) -> TickVolumeResult:
    """SA-005 tick volume and flags: the existing `volume` field is MT5
    tick-volume (a count of price updates behind the tick), NOT real
    exchange trade volume, order-book depth, or executable liquidity --
    the contract is explicit that it must not be presented as any of
    those. Like `tick_rate.py`, this reads raw ticks directly (no
    bid/ask validity filter applied -- volume/flags are independent of
    price quality).

    `tick_volume` is the distribution of each individual tick's raw
    volume value (all ticks, zero included). `window_volume_sum`
    aggregates one point per populated epoch-aligned window (that
    window's total volume), the same "one point per window" convention
    SA-003/SA-004 use -- empty windows are not zero-filled.

    `flag_combinations` reports raw observed `flags` integer values and
    their counts, deliberately UNDECODED: the contract says flags
    semantics must not be interpreted without a separate, versioned MT5
    bit-mapping, which this platform does not have. `version_segments`
    groups ticks by (`module_version`, `event_version`) so a caller can
    see whether the range spans a bridge/schema upgrade.
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

    n_total = len(filtered)
    n_zero_volume = sum(1 for tick in filtered if tick.volume == 0)
    n_positive_volume = sum(1 for tick in filtered if tick.volume > 0)

    tick_volume = _summarize(
        [float(tick.volume) for tick in filtered], n_total=n_total, minimum_sample=minimum_sample,
    )

    window_sums: dict[datetime, int] = {}
    for tick in filtered:
        window_start = _window_start(_timestamp(tick.event_timestamp), seconds)
        if window_start + timedelta(seconds=seconds) > normalized_end:
            continue
        window_sums[window_start] = window_sums.get(window_start, 0) + tick.volume
    total_window_count = _total_window_count(normalized_start, normalized_end, seconds)
    window_volume_sum = _summarize(
        [float(value) for value in window_sums.values()],
        n_total=total_window_count, minimum_sample=minimum_sample,
    )

    flag_counts: dict[int, int] = {}
    version_counts: dict[tuple[str, str], int] = {}
    for tick in filtered:
        flag_counts[tick.flags] = flag_counts.get(tick.flags, 0) + 1
        key = (tick.module_version, tick.event_version)
        version_counts[key] = version_counts.get(key, 0) + 1

    flag_combinations = tuple(
        FlagCombination(flags, count)
        for flags, count in sorted(flag_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    version_segments = tuple(
        VersionSegment(module_version, event_version, count)
        for (module_version, event_version), count in sorted(
            version_counts.items(), key=lambda item: (-item[1], item[0])
        )
    )

    return TickVolumeResult(
        TICK_VOLUME_VERSION, normalized_symbol, timeframe,
        n_total, n_zero_volume, n_positive_volume,
        tick_volume, window_volume_sum, flag_combinations, version_segments,
        _fingerprint(
            symbol=normalized_symbol, timeframe=timeframe, minimum_sample=minimum_sample,
            n_total=n_total, n_zero_volume=n_zero_volume, n_positive_volume=n_positive_volume,
            tick_volume=tick_volume, window_volume_sum=window_volume_sum,
            flag_combinations=flag_combinations, version_segments=version_segments,
        ),
    )
