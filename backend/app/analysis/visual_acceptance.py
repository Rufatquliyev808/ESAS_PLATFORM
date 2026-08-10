from dataclasses import dataclass
from hashlib import sha256
import json


ACCEPTANCE_VERSION = "1.0.0"
ACCEPTED_FOR_SHADOW = "accepted_for_shadow"
REJECTED = "rejected"

# v1 sanity threshold -- like every other MINIMUM_*/OOD_* constant in this
# Phase 5 pipeline, this is a documented engineering floor, not a
# statistically validated governance policy. Revisiting it is a separate,
# later decision. Beating the naive majority-class baseline by less than
# this margin is treated as "not meaningfully better than guessing".
MINIMUM_IMPROVEMENT_OVER_BASELINE = 0.05


class AcceptanceDecisionError(ValueError):
    pass


@dataclass(frozen=True)
class AcceptanceDecision:
    """The Phase 5 `evaluated -> accepted_for_shadow | rejected` step's
    record of the decision and why it was made. `reasons` is empty for an
    accepted decision and non-empty for a rejected one, so a rejection is
    always self-explaining without needing to re-derive the threshold math.
    This decision governs eligibility for a (separate, not-yet-built)
    SHADOW run -- it never authorizes real trading by itself.
    """

    evaluation_checksum: str
    version: str
    holdout_accuracy: float
    majority_baseline_accuracy: float
    improvement_over_baseline: float
    minimum_improvement_required: float
    decision: str
    reasons: tuple[str, ...]
    checksum: str


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _decision_payload(
    *,
    evaluation_checksum: str,
    version: str,
    holdout_accuracy: float,
    majority_baseline_accuracy: float,
    improvement_over_baseline: float,
    minimum_improvement_required: float,
    decision: str,
    reasons: tuple[str, ...],
) -> dict:
    return {
        "decision": decision,
        "evaluation_checksum": evaluation_checksum,
        "holdout_accuracy": holdout_accuracy,
        "improvement_over_baseline": improvement_over_baseline,
        "majority_baseline_accuracy": majority_baseline_accuracy,
        "minimum_improvement_required": minimum_improvement_required,
        "reasons": list(reasons),
        "version": version,
    }


def acceptance_decision_artifact_bytes(decision: AcceptanceDecision) -> bytes:
    payload = _decision_payload(
        evaluation_checksum=decision.evaluation_checksum, version=decision.version,
        holdout_accuracy=decision.holdout_accuracy, majority_baseline_accuracy=decision.majority_baseline_accuracy,
        improvement_over_baseline=decision.improvement_over_baseline,
        minimum_improvement_required=decision.minimum_improvement_required,
        decision=decision.decision, reasons=decision.reasons,
    )
    return _canonical_json(payload)


def decide_acceptance(
    *,
    outcome: str,
    evaluation_checksum: str,
    holdout_accuracy: float,
    majority_baseline_accuracy: float,
) -> AcceptanceDecision:
    """v1 accept/reject heuristic: SHADOW-eligible only if the model beats
    the naive majority-class baseline by at least
    `MINIMUM_IMPROVEMENT_OVER_BASELINE` on holdout. Only ever callable for
    an evaluation whose `outcome` was `evaluated` -- an OOD or
    insufficient-evidence evaluation was never trustworthy enough to make
    ANY accept/reject call from, so this raises rather than guessing.
    """
    if outcome != "evaluated":
        raise AcceptanceDecisionError(
            f"can only decide acceptance for an evaluation with outcome 'evaluated', got {outcome!r}"
        )

    improvement_over_baseline = holdout_accuracy - majority_baseline_accuracy
    reasons: list[str] = []
    if improvement_over_baseline < MINIMUM_IMPROVEMENT_OVER_BASELINE:
        reasons.append(
            f"improvement_over_baseline {improvement_over_baseline:.6f} is below the minimum "
            f"required {MINIMUM_IMPROVEMENT_OVER_BASELINE:.6f}"
        )
    decision = REJECTED if reasons else ACCEPTED_FOR_SHADOW

    payload = _decision_payload(
        evaluation_checksum=evaluation_checksum, version=ACCEPTANCE_VERSION, holdout_accuracy=holdout_accuracy,
        majority_baseline_accuracy=majority_baseline_accuracy, improvement_over_baseline=improvement_over_baseline,
        minimum_improvement_required=MINIMUM_IMPROVEMENT_OVER_BASELINE, decision=decision,
        reasons=tuple(reasons),
    )
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"

    return AcceptanceDecision(
        evaluation_checksum=evaluation_checksum, version=ACCEPTANCE_VERSION, holdout_accuracy=holdout_accuracy,
        majority_baseline_accuracy=majority_baseline_accuracy, improvement_over_baseline=improvement_over_baseline,
        minimum_improvement_required=MINIMUM_IMPROVEMENT_OVER_BASELINE, decision=decision,
        reasons=tuple(reasons), checksum=checksum,
    )
