from dataclasses import dataclass
from typing import Protocol

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorSetResult


EXPERIMENTAL = "experimental"
INSUFFICIENT_DATA = "insufficient_data"
READY = "ready"


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    version: str
    lifecycle: str
    description: str
    required_features: tuple[str, ...]
    interpretation: str = "research_observation_not_trading_signal"


@dataclass(frozen=True)
class StrategyObservation:
    bar_end_at: str
    status: str
    relation: str | None
    close: float
    reference_value: float | None


@dataclass(frozen=True)
class StrategySummary:
    ready: int
    insufficient_data: int
    above: int
    below: int
    equal: int


@dataclass(frozen=True)
class StrategyResult:
    definition: StrategyDefinition
    symbol: str
    timeframe: str
    parameters: tuple[tuple[str, int | float | str], ...]
    dataset_fingerprint: str
    bar_fingerprint: str
    indicator_fingerprint: str
    observations: tuple[StrategyObservation, ...]
    summary: StrategySummary
    fingerprint: str


class StrategyModule(Protocol):
    definition: StrategyDefinition

    def evaluate(
        self,
        *,
        symbol: str,
        timeframe: str,
        bars: tuple[MarketBar, ...],
        indicators: IndicatorSetResult,
        dataset_fingerprint: str,
    ) -> StrategyResult: ...
