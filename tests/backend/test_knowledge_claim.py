from datetime import UTC, datetime, timedelta

import pytest

from backend.app.knowledge.knowledge_claim import (
    ACCEPTED,
    ARCHIVED,
    CANDIDATE,
    CLAIM_TYPES,
    QUARANTINED,
    REJECTED,
    RESTRICTED,
    REVIEW_DUE,
    STATISTICAL_RELATION,
    SUPERSEDED,
    UNDER_REVIEW,
    KnowledgeScope,
    build_knowledge_claim,
    is_valid_transition,
)


BASE_TIME = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)


def scope(**overrides) -> KnowledgeScope:
    defaults = dict(
        symbol="GOLD", asset_class="metal", data_source="esas.mt5.bridge",
        timeframe="M1", horizon="10_bars", interval_start_at=BASE_TIME.isoformat(),
        interval_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        minimum_data_quality="ok", cost_scenario="normal",
        contract_versions={"statistical_analysis": "1.7.0"},
    )
    defaults.update(overrides)
    return KnowledgeScope(**defaults)


def build(**overrides):
    defaults = dict(
        knowledge_id="kc_001", knowledge_version=1, claim_type=STATISTICAL_RELATION,
        statement="Volatility is higher in the first UTC hour.",
        scope=scope(), evidence_bundle_ids=("exp_1",), dataset_fingerprints=("sha256:bars",),
        method_versions={"volatility": "1.1.0"}, created_by="TEST-USER",
        valid_from=BASE_TIME.isoformat(),
        review_due_at=(BASE_TIME + timedelta(days=90)).isoformat(),
    )
    defaults.update(overrides)
    return build_knowledge_claim(**defaults)


def test_build_creates_candidate_status() -> None:
    claim = build()
    assert claim.status == CANDIDATE
    assert claim.knowledge_id == "kc_001"
    assert claim.knowledge_version == 1
    assert claim.checksum.startswith("sha256:")


def test_all_nine_claim_types_are_accepted() -> None:
    assert len(CLAIM_TYPES) == 9
    for claim_type in CLAIM_TYPES:
        claim = build(claim_type=claim_type)
        assert claim.claim_type == claim_type


def test_rejects_unknown_claim_type() -> None:
    with pytest.raises(ValueError):
        build(claim_type="trade_signal")


def test_rejects_empty_statement() -> None:
    with pytest.raises(ValueError):
        build(statement="   ")


def test_rejects_empty_evidence_bundle_ids() -> None:
    with pytest.raises(ValueError):
        build(evidence_bundle_ids=())


def test_rejects_empty_dataset_fingerprints() -> None:
    with pytest.raises(ValueError):
        build(dataset_fingerprints=())


def test_rejects_non_positive_knowledge_version() -> None:
    with pytest.raises(ValueError):
        build(knowledge_version=0)


def test_rejects_review_due_at_not_after_valid_from() -> None:
    with pytest.raises(ValueError):
        build(valid_from=BASE_TIME.isoformat(), review_due_at=BASE_TIME.isoformat())


def test_rejects_uncertainty_low_greater_than_high() -> None:
    with pytest.raises(ValueError):
        build(effect_size=1.0, uncertainty_low=2.0, uncertainty_high=1.0)


def test_checksum_is_deterministic_for_identical_content() -> None:
    """created_at is wall-clock, not part of the content -- two builds with
    identical inputs must produce the same checksum regardless of it."""
    first = build()
    second = build()
    assert first.checksum == second.checksum


def test_checksum_differs_for_different_statement() -> None:
    first = build(statement="Claim A")
    second = build(statement="Claim B")
    assert first.checksum != second.checksum


def test_supersedes_is_stored() -> None:
    claim = build(supersedes="kc_000")
    assert claim.supersedes == "kc_000"


def test_scope_requires_all_core_fields() -> None:
    claim = build()
    assert claim.scope.symbol == "GOLD"
    assert claim.scope.contract_versions == {"statistical_analysis": "1.7.0"}


DIAGRAM_EDGES = [
    (CANDIDATE, UNDER_REVIEW),
    (UNDER_REVIEW, ACCEPTED),
    (UNDER_REVIEW, REJECTED),
    (ACCEPTED, REVIEW_DUE),
    (REVIEW_DUE, UNDER_REVIEW),
    (ACCEPTED, RESTRICTED),
    (ACCEPTED, SUPERSEDED),
    (ACCEPTED, QUARANTINED),
    (ACCEPTED, ARCHIVED),
]


@pytest.mark.parametrize("current_status,next_status", DIAGRAM_EDGES)
def test_documented_diagram_edges_are_valid(current_status, next_status) -> None:
    assert is_valid_transition(current_status, next_status) is True


def test_candidate_cannot_skip_straight_to_accepted() -> None:
    assert is_valid_transition(CANDIDATE, ACCEPTED) is False


def test_rejected_is_terminal() -> None:
    assert is_valid_transition(REJECTED, UNDER_REVIEW) is False
    assert is_valid_transition(REJECTED, CANDIDATE) is False


@pytest.mark.parametrize("terminal_status", [RESTRICTED, SUPERSEDED, QUARANTINED, ARCHIVED])
def test_accepted_terminal_branches_have_no_further_documented_transition(terminal_status) -> None:
    assert is_valid_transition(terminal_status, ARCHIVED) is False
    assert is_valid_transition(terminal_status, UNDER_REVIEW) is False


def test_is_valid_transition_rejects_unknown_current_status() -> None:
    with pytest.raises(ValueError):
        is_valid_transition("not_a_status", CANDIDATE)


def test_is_valid_transition_rejects_unknown_next_status() -> None:
    with pytest.raises(ValueError):
        is_valid_transition(CANDIDATE, "not_a_status")
