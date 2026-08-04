from dataclasses import dataclass
from datetime import datetime
from math import ceil

from backend.app.database.tick_replay_repository import iter_tick_batches

STATISTICS_VERSION = "1.0"
QUANTILE_METHOD = "bounded-sample-v1"
MAX_QUANTILE_SAMPLES = 2048

@dataclass(frozen=True)
class DistributionSummary:
    count: int
    minimum: float | None
    median: float | None
    p95: float | None
    maximum: float | None

@dataclass(frozen=True)
class TickQualityStatistics:
    version: str
    quantile_method: str
    tick_count: int
    duration_seconds: float
    ticks_per_second: float
    ticks_per_minute: float
    interval_seconds: DistributionSummary
    spread: DistributionSummary
    zero_price_pairs: int
    partial_price_pairs: int

class _BoundedDistribution:
    def __init__(self) -> None:
        self.count = 0
        self.minimum: float | None = None
        self.maximum: float | None = None
        self.samples: list[float] = []

    def add(self, value: float) -> None:
        self.count += 1
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        if len(self.samples) < MAX_QUANTILE_SAMPLES:
            self.samples.append(value)
        else:
            slot = (self.count * 2654435761) % self.count
            if slot < MAX_QUANTILE_SAMPLES:
                self.samples[slot] = value

    def freeze(self) -> DistributionSummary:
        if not self.samples:
            return DistributionSummary(0, None, None, None, None)
        ordered = sorted(self.samples)
        def quantile(value: float) -> float:
            return ordered[max(0, ceil(value * len(ordered)) - 1)]
        return DistributionSummary(self.count, self.minimum, quantile(0.5), quantile(0.95), self.maximum)

def calculate_tick_quality_statistics(*, symbol: str, start_at: datetime, end_at: datetime, batch_size: int = 1000) -> TickQualityStatistics:
    duration = (end_at - start_at).total_seconds()
    if duration <= 0:
        raise ValueError("end_at must be later than start_at")
    intervals, spreads = _BoundedDistribution(), _BoundedDistribution()
    tick_count = zero_pairs = partial_pairs = 0
    previous_time: datetime | None = None
    for batch in iter_tick_batches(symbol=symbol, start_at=start_at, end_at=end_at, batch_size=batch_size):
        for tick in batch:
            tick_count += 1
            current_time = datetime.fromisoformat(tick.event_timestamp)
            if previous_time is not None:
                intervals.add((current_time - previous_time).total_seconds())
            previous_time = current_time
            if tick.bid > 0 and tick.ask > 0:
                spreads.add(tick.ask - tick.bid)
            elif tick.bid == 0 and tick.ask == 0:
                zero_pairs += 1
            else:
                partial_pairs += 1
    return TickQualityStatistics(STATISTICS_VERSION, QUANTILE_METHOD, tick_count, duration, tick_count / duration, tick_count * 60 / duration, intervals.freeze(), spreads.freeze(), zero_pairs, partial_pairs)
