from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from math import isfinite

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
                self.reason,
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
        "DQ-005": _FindingAccumulator(
            "DQ-005", "critical", "ask was lower than bid"
        ),
        "DQ-003-warning": _FindingAccumulator(
            "DQ-003", "warning", "event and source time differed by over 2 seconds"
        ),
        "DQ-003-critical": _FindingAccumulator(
            "DQ-003", "critical", "event and source time differed by over 30 seconds"
        ),
        "DQ-006-partial": _FindingAccumulator(
            "DQ-006", "info", "only one side of the price pair was zero"
        ),
        "DQ-006-zero": _FindingAccumulator(
            "DQ-006", "info", "both sides of the price pair were zero"
        ),
        "DQ-007": _FindingAccumulator(
            "DQ-007", "critical", "numeric field was non-finite or negative"
        ),
        "DQ-008": _FindingAccumulator(
            "DQ-008", "critical", "tick event contract was invalid"
        ),
        "DQ-009-negative": _FindingAccumulator(
            "DQ-009", "warning", "received_at preceded event_timestamp"
        ),
        "DQ-009-info": _FindingAccumulator(
            "DQ-009", "info", "acceptance latency exceeded 5 seconds"
        ),
        "DQ-009-warning": _FindingAccumulator(
            "DQ-009", "warning", "acceptance latency exceeded 60 seconds"
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
            event_time = datetime.fromisoformat(tick.event_timestamp)
            event_time_ms = round(event_time.timestamp() * 1000)
            source_difference_ms = abs(event_time_ms - tick.source_time_msc)
            if source_difference_ms > 30_000:
                accumulators["DQ-003-critical"].add(tick)
            elif source_difference_ms > 2_000:
                accumulators["DQ-003-warning"].add(tick)

            if tick.bid > 0 and tick.ask > 0 and tick.ask < tick.bid:
                accumulators["DQ-005"].add(tick)
            if (tick.bid == 0) != (tick.ask == 0):
                accumulators["DQ-006-partial"].add(tick)
            elif tick.bid == 0 and tick.ask == 0:
                accumulators["DQ-006-zero"].add(tick)
            if (
                not all(isfinite(value) for value in (tick.bid, tick.ask, tick.last))
                or min(tick.bid, tick.ask, tick.last) < 0
                or tick.volume < 0
                or tick.flags < 0
            ):
                accumulators["DQ-007"].add(tick)
            if (
                tick.event_type != "TICK_RECEIVED"
                or tick.source != "esas.mt5.bridge"
                or tick.event_version != "1.0"
                or not tick.symbol.strip()
                or not tick.module_version.strip()
                or not tick.event_id.strip()
                or tick.symbol != symbol.strip()
            ):
                accumulators["DQ-008"].add(tick)

            acceptance_latency = (
                datetime.fromisoformat(tick.received_at) - event_time
            ).total_seconds()
            if acceptance_latency < 0:
                accumulators["DQ-009-negative"].add(tick)
            elif acceptance_latency > 60:
                accumulators["DQ-009-warning"].add(tick)
            elif acceptance_latency > 5:
                accumulators["DQ-009-info"].add(tick)
            segment = (tick.source, tick.module_version)
            previous_source_time = source_times.get(segment)
            if previous_source_time is not None and tick.source_time_msc < previous_source_time:
                accumulators["DQ-002"].add(tick)
            source_times[segment] = tick.source_time_msc

            if previous_tick is not None:
                gap = (
                    event_time
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
