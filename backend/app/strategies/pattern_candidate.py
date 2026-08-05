from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from backend.app.analysis.bos_choch import BosChochResult
from backend.app.analysis.liquidity_sweep import LiquiditySweepResult
from backend.app.analysis.market_structure import MarketStructureResult
from backend.app.analysis.retest import RetestResult
from backend.app.strategies.pattern_hypothesis_registry import get_pattern_hypothesis_registry


PATTERN_CANDIDATE_VERSION = "1.0.0"
LIFECYCLE_STATE = "draft"
INTERPRETATION = "research_pattern_candidate_draft_not_trading_signal_not_order"


@dataclass(frozen=True)
class PatternCandidateSlot:
    candidate_id: str
    hypothesis_id: str
    hypothesis_version: str
    family: str
    direction: str
    lifecycle_state: str
    condition_state: str
    observed_at: str | None
    evidence: dict[str, object]


@dataclass(frozen=True)
class PatternCandidateResult:
    version: str
    hypothesis_registry_version: str
    slots: tuple[PatternCandidateSlot, ...]
    fingerprint: str
    interpretation: str = INTERPRETATION


def _candidate_id(hypothesis_id: str, observed_at: str | None, evidence: dict[str, object]) -> str:
    payload = json.dumps(
        {"hypothesis_id": hypothesis_id, "observed_at": observed_at, "evidence": evidence},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    digest = sha256(payload.encode()).hexdigest()[:16]
    return f"{hypothesis_id}:{digest}"


def _slot(hypothesis: dict[str, object], condition_state: str, observed_at: str | None, evidence: dict[str, object]) -> PatternCandidateSlot:
    hypothesis_id = str(hypothesis["hypothesis_id"])
    return PatternCandidateSlot(
        candidate_id=_candidate_id(hypothesis_id, observed_at, evidence),
        hypothesis_id=hypothesis_id,
        hypothesis_version=str(hypothesis["version"]),
        family=str(hypothesis["family"]),
        direction=str(hypothesis["direction"]),
        lifecycle_state=LIFECYCLE_STATE,
        condition_state=condition_state,
        observed_at=observed_at,
        evidence=evidence,
    )


def _structure_slot(hypothesis: dict[str, object], observation) -> PatternCandidateSlot:
    if observation.state == "confirmed_structure":
        return _slot(hypothesis, "candidate_confirmed", observation.observed_at, {
            "latest_high": observation.latest_high, "latest_low": observation.latest_low,
        })
    if observation.state == "insufficient_data":
        return _slot(hypothesis, "insufficient_data", None, {})
    return _slot(hypothesis, "no_candidate", None, {"structure_state": observation.state})


def _liquidity_slot(hypothesis: dict[str, object], observation) -> PatternCandidateSlot:
    if observation.state == "confirmed_sweep":
        return _slot(hypothesis, "candidate_confirmed", observation.observed_at, {
            "pool_side": observation.pool_side, "pool_level": observation.pool_level,
            "pool_touch_count": observation.pool_touch_count, "excursion_bps": observation.excursion_bps,
        })
    if observation.state == "insufficient_data":
        return _slot(hypothesis, "insufficient_data", None, {})
    return _slot(hypothesis, "no_candidate", None, {"sweep_state": observation.state})


def _structure_break_slot(hypothesis: dict[str, object], observation) -> PatternCandidateSlot:
    if observation.state == "confirmed_retest":
        return _slot(hypothesis, "candidate_confirmed", observation.observed_at, {
            "break_type": observation.break_type, "level": observation.level,
            "break_observed_at": observation.break_observed_at, "touched_at": observation.touched_at,
            "close_distance_bps": observation.close_distance_bps,
        })
    if observation.state == "insufficient_data":
        return _slot(hypothesis, "insufficient_data", None, {})
    return _slot(hypothesis, "no_candidate", None, {"retest_state": observation.state})


def detect_pattern_candidates(
    *, market_structure: MarketStructureResult, liquidity_sweep: LiquiditySweepResult,
    bos_choch: BosChochResult, retest: RetestResult,
) -> PatternCandidateResult:
    """Combine already-causal detector outputs into draft, versioned pattern candidate slots.

    This does not run its own bar loop; causality is inherited from the upstream
    detectors. No candidate is ever promoted beyond the "draft" lifecycle state here
    -- backtest, labeling, persistence and SHADOW eligibility are separate, later steps.
    """
    for result in (market_structure, liquidity_sweep, bos_choch, retest):
        if not result.fingerprint.strip():
            raise ValueError("upstream fingerprints must not be empty")

    registry = get_pattern_hypothesis_registry()
    hypotheses = {str(item["hypothesis_id"]): item for item in registry["hypotheses"]}

    slots = (
        _structure_slot(hypotheses["market_structure_long"], market_structure.long_observation),
        _structure_slot(hypotheses["market_structure_short"], market_structure.short_observation),
        _liquidity_slot(hypotheses["liquidity_sweep_reclaim_long"], liquidity_sweep.bullish_observation),
        _liquidity_slot(hypotheses["liquidity_sweep_reclaim_short"], liquidity_sweep.bearish_observation),
        _structure_break_slot(hypotheses["structure_break_long"], retest.bullish_observation),
        _structure_break_slot(hypotheses["structure_break_short"], retest.bearish_observation),
    )

    payload = {
        "version": PATTERN_CANDIDATE_VERSION,
        "hypothesis_registry_version": registry["registry_version"],
        "market_structure_fingerprint": market_structure.fingerprint,
        "liquidity_sweep_fingerprint": liquidity_sweep.fingerprint,
        "bos_choch_fingerprint": bos_choch.fingerprint,
        "retest_fingerprint": retest.fingerprint,
        "slots": [asdict(item) for item in slots],
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return PatternCandidateResult(
        version=PATTERN_CANDIDATE_VERSION,
        hypothesis_registry_version=str(registry["registry_version"]),
        slots=slots,
        fingerprint=f"sha256:{digest}",
    )
