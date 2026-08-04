from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from backend.app.database.tick_replay_repository import ReplayTick, iter_tick_batches


QUALITY_RULE_VERSION = "1.0"
DEFAULT_GAP_SECONDS = 30.0
DEFAULT_LONG_GAP_SECONDS = 300.0
MAX_FINDING_SAMPLES = 5


@dataclass(frozen=True)
class QualityFinding:
    finding_id: str
    rule_id: str
    rule_version: str
    severity: str
    reason: str
    count: int
    first_event_id: str
    last_event_id: str
    first_timestamp: str
    last_timestamp: str
    sample_event_ids: tuple[str, ...]


@dataclass(frozen=True)
class TickQualityResult:
    symbol: str
    start_at: str
    end_at: str
    rule_version: str
    tick_count: int
    findings: tuple[QualityFinding, ...]


@dataclass
class _FindingAccumulator:
    rule_id: str
    severity: str
    reason: str
    count: int = 0
    first_event_id: str = ""
    last_event_id: str = ""
    first_timestamp: str = ""
    last_timestamp: str = ""
    samples: list[str] | None = None

    def add(self, tick: ReplayTick) -> None:
        if self.samples is None:
            self.samples = []
        if self.count == 0:
            self.first_event_id = tick.event_id
            self.first_timestamp = tick.event_timestamp
        self.count += 1
        self.last_event_id = tick.event_id
        self.last_timestamp = tick.event_timestamp
        if len(self.samples) < MAX_FINDING_SAMPLES:
            self.samples.append(tick.event_id)

    def freeze(self) -> QualityFinding:
        identity = "|".join(
            (
                QUALITY_RULE_VERSION,
                self.rule_id,
                self.severity,
                self.first_event_id,
                self.last_event_id,
                str(self.count),
            )
        )
        finding_id = "dqf_" + sha256(identity.encode("utf-8")).hexdigest()[:24]
        return QualityFinding(
            finding_id=finding_id,
            rule_id=self.rule_id,
            rule_version=QUALITY_RULE_VERSION,
            severity=self.severity,
            reason=self.reason,
            count=self.count,
            first_event_id=self.first_event_id,
            last_event_id=self.last_event_id,
            first_timestamp=self.first_timestamp,
            last_timestamp=self.last_timestamp,
            sample_event_ids=tuple(self.samples or ()),
        )


def _payload_identity(tick: ReplayTick) -> tuple[object, ...]:
    return (
        tick.source,
        tick.module_version,
        tick.source_time_msc,
        tick.bid,
        tick.ask,
        tick.last,
        tick.volume,
        tick.flags,
    )


def analyze_tick_quality(
    *,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    batch_size: int = 1000,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
    long_gap_seconds: float = DEFAULT_LONG_GAP_SECONDS,
) -> TickQualityResult:
    if gap_seconds <= 0:
        raise ValueError("gap_seconds must be positive")
    if long_gap_seconds <= gap_seconds:
        raise ValueError("long_gap_seconds must be greater than gap_seconds")

    accumulators = {
        "DQ-002": _FindingAccumulator(
            "DQ-002", "warning", "source_time_msc moved backwards"
        ),
        "DQ-004-info": _FindingAccumulator(
            "DQ-004", "info", "consecutive tick gap exceeded threshold"
        ),
        "DQ-004-warning": _FindingAccumulator(
            "DQ-004", "warning", "consecutive tick gap exceeded long threshold"
        ),
        "DQ-011": _FindingAccumulator(
            "DQ-011", "info", "consecutive market payload duplicate candidate"
        ),
    }
    previous_tick: ReplayTick | None = None
    source_times: dict[tuple[str, str], int] = {}
    tick_count = 0

    for batch in iter_tick_batches(
        symbol=symbol,
        start_at=start_at,
        end_at=end_at,
        batch_size=batch_size,
    ):
        for tick in batch:
            tick_count += 1
            segment = (tick.source, tick.module_version)
            previous_source_time = source_times.get(segment)
            if previous_source_time is not None and tick.source_time_msc < previous_source_time:
                accumulators["DQ-002"].add(tick)
            source_times[segment] = tick.source_time_msc

            if previous_tick is not None:
                gap = (
                    datetime.fromisoformat(tick.event_timestamp)
                    - datetime.fromisoformat(previous_tick.event_timestamp)
                ).total_seconds()
                if gap > long_gap_seconds:
                    accumulators["DQ-004-warning"].add(tick)
                elif gap > gap_seconds:
                    accumulators["DQ-004-info"].add(tick)
                if _payload_identity(tick) == _payload_identity(previous_tick):
                    accumulators["DQ-011"].add(tick)
            previous_tick = tick

    findings = tuple(
        accumulator.freeze()
        for accumulator in accumulators.values()
        if accumulator.count > 0
    )
    return TickQualityResult(
        symbol=symbol.strip(),
        start_at=start_at.isoformat(timespec="microseconds"),
        end_at=end_at.isoformat(timespec="microseconds"),
        rule_version=QUALITY_RULE_VERSION,
        tick_count=tick_count,
        findings=findings,
    )
