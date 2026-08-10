from dataclasses import dataclass
from hashlib import sha256
from math import comb
import json

from backend.app.analysis.visual_acceptance import ACCEPTED_FOR_SHADOW, MINIMUM_IMPROVEMENT_OVER_BASELINE, REJECTED
from backend.app.analysis.visual_evaluation import INSUFFICIENT_EVIDENCE, MINIMUM_HOLDOUT_SAMPLES


STATISTICAL_ACCEPTANCE_VERSION = "1.0.0"
TESTING_FAMILY_VERSION = "1.0.0"
BASE_ALPHA = 0.05
# Fixed z-score for a two-sided 95% Wilson score interval. Hardcoded rather
# than computed from an inverse-normal-CDF (which would need scipy/a new
# dependency) -- this is the well-known constant for that one confidence
# level; a different confidence level is a separate, later decision.
WILSON_Z_95 = 1.959963985


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def compute_testing_family_id(dataset_fingerprint: str) -> str:
    """Groups every trial (architecture/seed/hyperparameter variation)
    attempted against the SAME frozen dataset under one family, so
    multiple-testing correction can see how many things were tried before
    this one "worked". Deliberately keyed on `dataset_fingerprint` alone --
    not `model_spec_id`/`training_spec_id`, which are exactly what is
    allowed to vary WITHIN a family.
    """
    payload = {"dataset_fingerprint": dataset_fingerprint, "version": TESTING_FAMILY_VERSION}
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"


def one_sided_binomial_p_value(successes: int, n: int, baseline_probability: float) -> float:
    """Exact one-sided binomial test: P(X >= successes) under
    Binomial(n, baseline_probability) -- the probability of seeing a
    holdout result at least this good if the model's true accuracy were
    really only the naive majority-baseline rate (the null hypothesis).
    Summed in a FIXED ascending-k order for byte-for-byte determinism, and
    computed exactly via `math.comb` rather than a normal approximation
    (no scipy/numpy dependency needed for reasonably small holdout sizes).
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("successes must be between 0 and n")
    if not 0.0 <= baseline_probability <= 1.0:
        raise ValueError("baseline_probability must be between 0 and 1")
    if n == 0:
        return 1.0
    if baseline_probability <= 0.0:
        return 0.0 if successes > 0 else 1.0
    if baseline_probability >= 1.0:
        return 1.0

    p = baseline_probability
    total = 0.0
    for k in range(successes, n + 1):
        total += comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
    return min(1.0, total)


def wilson_score_interval(successes: int, n: int, *, z: float = WILSON_Z_95) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion --
    better-behaved than a normal approximation at small `n` (this system's
    holdout sizes are typically small). Informational/audit only: the
    acceptance decision below gates on the p-value, not this interval.
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("successes must be between 0 and n")
    if n == 0:
        return (0.0, 1.0)

    phat = successes / n
    denominator = 1 + z * z / n
    center = phat + z * z / (2 * n)
    margin = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5)
    lower = (center - margin) / denominator
    upper = (center + margin) / denominator
    return (max(0.0, lower), min(1.0, upper))


def bonferroni_corrected_alpha(base_alpha: float, family_trial_count: int) -> float:
    """The more trials (architectures/seeds/hyperparameters) a family has
    accumulated, the smaller the p-value any ONE of them needs to clear --
    this is the whole point: a family that tried 20 things and found 1
    "significant" result needs much stronger evidence than a family that
    only ever tried 1 thing.
    """
    if family_trial_count < 1:
        raise ValueError("family_trial_count must be at least 1")
    if not 0.0 < base_alpha < 1.0:
        raise ValueError("base_alpha must be between 0 and 1")
    return base_alpha / family_trial_count


@dataclass(frozen=True)
class StatisticalAcceptanceDecision:
    """The Phase 5 statistical acceptance gate's full record: which family
    and how many trials it has seen, the corrected significance threshold
    that implies, the holdout evidence (raw counts, not just a derived
    accuracy, so the exact binomial test is always reproducible from this
    artifact alone), and every condition checked. `reasons` is empty only
    for `accepted_for_shadow`.
    """

    testing_family_id: str
    family_trial_count: int
    base_alpha: float
    corrected_alpha: float
    trial_registered: bool
    reproduction_verified: bool
    evaluation_outcome: str
    holdout_sample_count: int
    holdout_correct_count: int
    holdout_accuracy: float
    majority_baseline_accuracy: float
    improvement_over_baseline: float
    minimum_improvement_required: float
    p_value: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    evaluation_checksum: str
    model_checksum: str
    version: str
    decision: str
    reasons: tuple[str, ...]
    checksum: str


def _decision_payload(
    *,
    testing_family_id: str,
    family_trial_count: int,
    base_alpha: float,
    corrected_alpha: float,
    trial_registered: bool,
    reproduction_verified: bool,
    evaluation_outcome: str,
    holdout_sample_count: int,
    holdout_correct_count: int,
    holdout_accuracy: float,
    majority_baseline_accuracy: float,
    improvement_over_baseline: float,
    minimum_improvement_required: float,
    p_value: float,
    confidence_interval_lower: float,
    confidence_interval_upper: float,
    evaluation_checksum: str,
    model_checksum: str,
    version: str,
    decision: str,
    reasons: tuple[str, ...],
) -> dict:
    return {
        "base_alpha": base_alpha,
        "confidence_interval_lower": confidence_interval_lower,
        "confidence_interval_upper": confidence_interval_upper,
        "corrected_alpha": corrected_alpha,
        "decision": decision,
        "evaluation_checksum": evaluation_checksum,
        "evaluation_outcome": evaluation_outcome,
        "family_trial_count": family_trial_count,
        "holdout_accuracy": holdout_accuracy,
        "holdout_correct_count": holdout_correct_count,
        "holdout_sample_count": holdout_sample_count,
        "improvement_over_baseline": improvement_over_baseline,
        "majority_baseline_accuracy": majority_baseline_accuracy,
        "minimum_improvement_required": minimum_improvement_required,
        "model_checksum": model_checksum,
        "p_value": p_value,
        "reasons": list(reasons),
        "reproduction_verified": reproduction_verified,
        "testing_family_id": testing_family_id,
        "trial_registered": trial_registered,
        "version": version,
    }


def statistical_acceptance_decision_artifact_bytes(decision: StatisticalAcceptanceDecision) -> bytes:
    payload = _decision_payload(
        testing_family_id=decision.testing_family_id, family_trial_count=decision.family_trial_count,
        base_alpha=decision.base_alpha, corrected_alpha=decision.corrected_alpha,
        trial_registered=decision.trial_registered, reproduction_verified=decision.reproduction_verified,
        evaluation_outcome=decision.evaluation_outcome, holdout_sample_count=decision.holdout_sample_count,
        holdout_correct_count=decision.holdout_correct_count, holdout_accuracy=decision.holdout_accuracy,
        majority_baseline_accuracy=decision.majority_baseline_accuracy,
        improvement_over_baseline=decision.improvement_over_baseline,
        minimum_improvement_required=decision.minimum_improvement_required, p_value=decision.p_value,
        confidence_interval_lower=decision.confidence_interval_lower,
        confidence_interval_upper=decision.confidence_interval_upper,
        evaluation_checksum=decision.evaluation_checksum, model_checksum=decision.model_checksum,
        version=decision.version, decision=decision.decision, reasons=decision.reasons,
    )
    return _canonical_json(payload)


def decide_statistical_acceptance(
    *,
    testing_family_id: str,
    family_trial_count: int,
    trial_registered: bool,
    reproduction_verified: bool,
    evaluation_outcome: str,
    holdout_sample_count: int,
    holdout_correct_count: int,
    majority_baseline_accuracy: float,
    evaluation_checksum: str,
    model_checksum: str,
    base_alpha: float = BASE_ALPHA,
) -> StatisticalAcceptanceDecision:
    """The Phase 5 statistical acceptance gate. `accepted_for_shadow`
    requires ALL of:

    1. the exact (family, model_spec, training_spec) trial was registered
       BEFORE this decision -- `trial_registered`;
    2. the model reproduces byte-for-byte from the same dataset/spec --
       `reproduction_verified`;
    3. the evaluation this decision is based on actually completed
       validly -- `evaluation_outcome == "evaluated"` (not OOD, not an
       earlier abstain);
    4. enough holdout samples to trust any conclusion at all;
    5. improvement over the naive majority-baseline meets the minimum
       margin;
    6. the one-sided exact binomial test beats alpha=0.05 AFTER Bonferroni
       correction for how many trials this family has accumulated.

    Any other failure (including #1, #2, #3, #5, #6) is `rejected` with
    every failing reason listed; too few holdout samples is `insufficient_evidence`
    instead, checked first since none of the other numbers can be trusted
    from too little evidence anyway. The existing simple threshold-only
    `visual_acceptance.decide_acceptance()` is no longer sufficient on its
    own to reach `accepted_for_shadow` -- this function is now the only
    path the acceptance orchestrator calls.
    """
    corrected_alpha = bonferroni_corrected_alpha(base_alpha, family_trial_count)
    holdout_accuracy = (holdout_correct_count / holdout_sample_count) if holdout_sample_count > 0 else 0.0
    improvement_over_baseline = holdout_accuracy - majority_baseline_accuracy

    if holdout_sample_count > 0:
        p_value = one_sided_binomial_p_value(holdout_correct_count, holdout_sample_count, majority_baseline_accuracy)
        ci_lower, ci_upper = wilson_score_interval(holdout_correct_count, holdout_sample_count)
    else:
        p_value = 1.0
        ci_lower, ci_upper = 0.0, 1.0

    reasons: list[str] = []
    if holdout_sample_count < MINIMUM_HOLDOUT_SAMPLES:
        reasons.append(
            f"holdout_sample_count {holdout_sample_count} is below the minimum required {MINIMUM_HOLDOUT_SAMPLES}"
        )
        decision = INSUFFICIENT_EVIDENCE
    else:
        if not trial_registered:
            reasons.append("trial_not_preregistered")
        if not reproduction_verified:
            reasons.append("model_reproduction_checksum_mismatch")
        if evaluation_outcome != "evaluated":
            reasons.append(f"evaluation_outcome_not_evaluated:{evaluation_outcome}")
        if improvement_over_baseline < MINIMUM_IMPROVEMENT_OVER_BASELINE:
            reasons.append(
                f"improvement_over_baseline {improvement_over_baseline:.6f} is below the minimum "
                f"required {MINIMUM_IMPROVEMENT_OVER_BASELINE:.6f}"
            )
        if p_value >= corrected_alpha:
            reasons.append(
                f"p_value {p_value:.6f} does not clear the Bonferroni-corrected alpha "
                f"{corrected_alpha:.6f} (family_trial_count={family_trial_count})"
            )
        decision = REJECTED if reasons else ACCEPTED_FOR_SHADOW

    payload = _decision_payload(
        testing_family_id=testing_family_id, family_trial_count=family_trial_count, base_alpha=base_alpha,
        corrected_alpha=corrected_alpha, trial_registered=trial_registered,
        reproduction_verified=reproduction_verified, evaluation_outcome=evaluation_outcome,
        holdout_sample_count=holdout_sample_count, holdout_correct_count=holdout_correct_count,
        holdout_accuracy=holdout_accuracy, majority_baseline_accuracy=majority_baseline_accuracy,
        improvement_over_baseline=improvement_over_baseline,
        minimum_improvement_required=MINIMUM_IMPROVEMENT_OVER_BASELINE, p_value=p_value,
        confidence_interval_lower=ci_lower, confidence_interval_upper=ci_upper,
        evaluation_checksum=evaluation_checksum, model_checksum=model_checksum,
        version=STATISTICAL_ACCEPTANCE_VERSION, decision=decision, reasons=tuple(reasons),
    )
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"

    return StatisticalAcceptanceDecision(
        testing_family_id=testing_family_id, family_trial_count=family_trial_count, base_alpha=base_alpha,
        corrected_alpha=corrected_alpha, trial_registered=trial_registered,
        reproduction_verified=reproduction_verified, evaluation_outcome=evaluation_outcome,
        holdout_sample_count=holdout_sample_count, holdout_correct_count=holdout_correct_count,
        holdout_accuracy=holdout_accuracy, majority_baseline_accuracy=majority_baseline_accuracy,
        improvement_over_baseline=improvement_over_baseline,
        minimum_improvement_required=MINIMUM_IMPROVEMENT_OVER_BASELINE, p_value=p_value,
        confidence_interval_lower=ci_lower, confidence_interval_upper=ci_upper,
        evaluation_checksum=evaluation_checksum, model_checksum=model_checksum,
        version=STATISTICAL_ACCEPTANCE_VERSION, decision=decision, reasons=tuple(reasons), checksum=checksum,
    )
