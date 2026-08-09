from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json


KNOWLEDGE_CLAIM_VERSION = "1.0.0"

DESCRIPTIVE_FACT = "descriptive_fact"
STATISTICAL_RELATION = "statistical_relation"
REGIME_OBSERVATION = "regime_observation"
PATTERN_CANDIDATE = "pattern_candidate"
VISUAL_MODEL_FINDING = "visual_model_finding"
NEWS_IMPACT_FINDING = "news_impact_finding"
DATA_QUALITY_LIMITATION = "data_quality_limitation"
NEGATIVE_RESULT = "negative_result"
OPERATIONAL_CONSTRAINT = "operational_constraint"

CLAIM_TYPES = frozenset({
    DESCRIPTIVE_FACT, STATISTICAL_RELATION, REGIME_OBSERVATION, PATTERN_CANDIDATE,
    VISUAL_MODEL_FINDING, NEWS_IMPACT_FINDING, DATA_QUALITY_LIMITATION,
    NEGATIVE_RESULT, OPERATIONAL_CONSTRAINT,
})

CANDIDATE = "candidate"
UNDER_REVIEW = "under_review"
ACCEPTED = "accepted"
REVIEW_DUE = "review_due"
REJECTED = "rejected"
RESTRICTED = "restricted"
SUPERSEDED = "superseded"
QUARANTINED = "quarantined"
ARCHIVED = "archived"

STATUSES = frozenset({
    CANDIDATE, UNDER_REVIEW, ACCEPTED, REVIEW_DUE, REJECTED, RESTRICTED,
    SUPERSEDED, QUARANTINED, ARCHIVED,
})

# Exactly the edges drawn in the Phase 7 contract's "Vəziyyətlər" diagram --
# no additional transitions are invented for states the diagram leaves
# terminal (rejected/restricted/superseded/quarantined/archived).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    CANDIDATE: frozenset({UNDER_REVIEW}),
    UNDER_REVIEW: frozenset({ACCEPTED, REJECTED}),
    ACCEPTED: frozenset({REVIEW_DUE, RESTRICTED, SUPERSEDED, QUARANTINED, ARCHIVED}),
    REVIEW_DUE: frozenset({UNDER_REVIEW}),
    REJECTED: frozenset(),
    RESTRICTED: frozenset(),
    SUPERSEDED: frozenset(),
    QUARANTINED: frozenset(),
    ARCHIVED: frozenset(),
}


@dataclass(frozen=True)
class KnowledgeScope:
    """Every claim's applicability boundary. The contract requires all of
    these to be present -- a claim with no stated scope cannot be
    distinguished from a universally-applicable one, which the contract
    explicitly forbids ("scope-dan kənar sorğu not_applicable verir").
    """

    symbol: str
    asset_class: str
    data_source: str
    timeframe: str
    horizon: str
    interval_start_at: str
    interval_end_at: str
    minimum_data_quality: str
    cost_scenario: str
    contract_versions: dict[str, str]
    session: str | None = None
    regime: str | None = None
    regime_detector_version: str | None = None
    excluded_use: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeClaim:
    """One immutable, versioned unit of the Knowledge Base's "bilik vahidi".
    Always created in `candidate` status -- that is the diagram's only entry
    state. `knowledge_id` is stable across amendments (supplied by the
    caller/future repository layer, not derived here); `knowledge_version`
    increments only when the claim's substance -- statement, scope,
    evidence, or threshold -- changes, per the contract's versioning rule.
    A pure lifecycle status change (e.g. accepted -> review_due) does NOT
    require a new knowledge_version.
    """

    version: str
    knowledge_id: str
    knowledge_version: int
    claim_type: str
    statement: str
    scope: KnowledgeScope
    applicability: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    dataset_fingerprints: tuple[str, ...]
    method_versions: dict[str, str]
    effect_size: float | None
    uncertainty_low: float | None
    uncertainty_high: float | None
    limitations: tuple[str, ...]
    valid_from: str
    review_due_at: str
    status: str
    created_at: str
    created_by: str
    supersedes: str | None
    conflicts_with: tuple[str, ...]
    checksum: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _required_utc(value: str, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return normalized


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def is_valid_transition(current_status: str, next_status: str) -> bool:
    if current_status not in ALLOWED_TRANSITIONS:
        raise ValueError(f"unknown status: {current_status}")
    if next_status not in STATUSES:
        raise ValueError(f"unknown status: {next_status}")
    return next_status in ALLOWED_TRANSITIONS[current_status]


def build_knowledge_claim(
    *,
    knowledge_id: str,
    knowledge_version: int,
    claim_type: str,
    statement: str,
    scope: KnowledgeScope,
    evidence_bundle_ids: tuple[str, ...],
    dataset_fingerprints: tuple[str, ...],
    method_versions: dict[str, str],
    created_by: str,
    valid_from: str,
    review_due_at: str,
    applicability: tuple[str, ...] = (),
    effect_size: float | None = None,
    uncertainty_low: float | None = None,
    uncertainty_high: float | None = None,
    limitations: tuple[str, ...] = (),
    supersedes: str | None = None,
    conflicts_with: tuple[str, ...] = (),
) -> KnowledgeClaim:
    """Construct a new `candidate` knowledge claim. Never accepts, rejects,
    or otherwise transitions the claim -- lifecycle changes are a separate,
    later (repository-layer) concern, matching how `visual_render.py`/
    `visual_dataset.py`/`visual_label.py` stayed pure in Phase 5 and left
    persistence/lifecycle to `visual_experiment_repository.py`.
    """
    normalized_id = _required_text(knowledge_id, "knowledge_id")
    if isinstance(knowledge_version, bool) or not isinstance(knowledge_version, int) or knowledge_version < 1:
        raise ValueError("knowledge_version must be a positive integer")
    if claim_type not in CLAIM_TYPES:
        raise ValueError(f"claim_type must be one of: {', '.join(sorted(CLAIM_TYPES))}")
    normalized_statement = _required_text(statement, "statement")
    normalized_creator = _required_text(created_by, "created_by")
    if not evidence_bundle_ids:
        raise ValueError("evidence_bundle_ids must not be empty")
    if not dataset_fingerprints:
        raise ValueError("dataset_fingerprints must not be empty")
    normalized_valid_from = _required_utc(valid_from, "valid_from")
    normalized_review_due_at = _required_utc(review_due_at, "review_due_at")
    if normalized_review_due_at <= normalized_valid_from:
        raise ValueError("review_due_at must be after valid_from")
    if supersedes is not None:
        supersedes = _required_text(supersedes, "supersedes")
    if (
        effect_size is not None
        and uncertainty_low is not None
        and uncertainty_high is not None
        and uncertainty_low > uncertainty_high
    ):
        raise ValueError("uncertainty_low must not be greater than uncertainty_high")

    now = datetime.now(UTC).isoformat(timespec="microseconds")
    payload = {
        "applicability": list(applicability),
        "claim_type": claim_type,
        "conflicts_with": list(conflicts_with),
        "created_by": normalized_creator,
        "dataset_fingerprints": list(dataset_fingerprints),
        "effect_size": effect_size,
        "evidence_bundle_ids": list(evidence_bundle_ids),
        "knowledge_id": normalized_id,
        "knowledge_version": knowledge_version,
        "limitations": list(limitations),
        "method_versions": method_versions,
        "review_due_at": normalized_review_due_at,
        "scope": asdict(scope),
        "statement": normalized_statement,
        "status": CANDIDATE,
        "supersedes": supersedes,
        "uncertainty_high": uncertainty_high,
        "uncertainty_low": uncertainty_low,
        "valid_from": normalized_valid_from,
        "version": KNOWLEDGE_CLAIM_VERSION,
    }
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"

    return KnowledgeClaim(
        version=KNOWLEDGE_CLAIM_VERSION,
        knowledge_id=normalized_id,
        knowledge_version=knowledge_version,
        claim_type=claim_type,
        statement=normalized_statement,
        scope=scope,
        applicability=applicability,
        evidence_bundle_ids=evidence_bundle_ids,
        dataset_fingerprints=dataset_fingerprints,
        method_versions=method_versions,
        effect_size=effect_size,
        uncertainty_low=uncertainty_low,
        uncertainty_high=uncertainty_high,
        limitations=limitations,
        valid_from=normalized_valid_from,
        review_due_at=normalized_review_due_at,
        status=CANDIDATE,
        created_at=now,
        created_by=normalized_creator,
        supersedes=supersedes,
        conflicts_with=conflicts_with,
        checksum=checksum,
    )
