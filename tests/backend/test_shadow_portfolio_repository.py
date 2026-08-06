from pathlib import Path

import pytest

from backend.app.database.migration_runner import apply_migrations
from backend.app.database.connection import initialize_database
from backend.app.database.shadow_event_repository import list_shadow_run_events
from backend.app.database.shadow_portfolio_repository import (
    ShadowPositionConflictError,
    ShadowPositionNotFoundError,
    ShadowRiskBlockedResult,
    close_theoretical_position,
    get_theoretical_portfolio_summary,
    open_theoretical_position,
)
from backend.app.database.shadow_run_repository import ShadowRunOwnershipError, register_shadow_run


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _register_run(risk_budget: dict[str, object] | None = None, created_by: str = "TEST-USER"):
    run = register_shadow_run(
        created_by=created_by, planned_end_at="2026-09-01T00:00:00+00:00",
        code_commit="abc123", config_hash="sha256:config",
        feature_claim_versions=("market_structure:1.0.0",), symbols=("GOLD",), timeframes=("M5",),
        sessions=("london",), accepted_market_regimes=("trending",),
        minimum_market_open_duration_seconds=3600, minimum_eligible_decision_count=30,
        primary_metric="net_return_percent", primary_metric_threshold=0.5,
        secondary_metrics={}, failure_rules={}, theoretical_fill_model={},
        risk_budget=risk_budget or {}, data_quality_policy={},
        approved_by="RISK-OFFICER", rollback_plan="halt and archive run",
        participants=(("champion", "structure_break_long", "1.0.0"),),
    )
    return run


def _open(run, *, symbol: str = "GOLD", direction: str = "long", size: float = 1.0, risk: float = 1.0, actor: str = "TEST-USER"):
    return open_theoretical_position(
        shadow_run_id=run.shadow_run_id, participant_id=run.participants[0].participant_id,
        symbol=symbol, direction=direction, theoretical_size=size, reserved_risk_amount=risk,
        actor=actor, correlation_id="corr-1",
    )


def test_open_position_persists_and_links_recorded_event(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    position = _open(run)
    assert position.state == "open"
    assert position.reserved_risk_amount == 1.0
    events = list_shadow_run_events(run.shadow_run_id)
    assert any(event.event_id == position.open_event_id and event.event_type == "SHADOW_THEORETICAL_POSITION_OPENED" for event in events)


def test_open_position_with_empty_risk_budget_is_never_blocked(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run(risk_budget={})
    for _ in range(5):
        result = _open(run)
        assert not isinstance(result, ShadowRiskBlockedResult)


def test_open_blocked_by_max_concurrent_positions(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run(risk_budget={"max_concurrent_positions": 1})
    first = _open(run)
    assert not isinstance(first, ShadowRiskBlockedResult)
    second = _open(run, symbol="SILVER")
    assert isinstance(second, ShadowRiskBlockedResult)
    assert second.reason == "max_concurrent_positions_exceeded"
    events = list_shadow_run_events(run.shadow_run_id)
    assert any(event.event_id == second.event_id and event.event_type == "SHADOW_RISK_BLOCKED" for event in events)


def test_open_blocked_by_same_symbol_direction_concentration(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run(risk_budget={"max_concurrent_per_symbol_direction": 1})
    first = _open(run, symbol="GOLD", direction="long")
    assert not isinstance(first, ShadowRiskBlockedResult)
    blocked = _open(run, symbol="GOLD", direction="long")
    assert isinstance(blocked, ShadowRiskBlockedResult)
    assert blocked.reason == "max_concurrent_per_symbol_direction_exceeded"
    # A different symbol/direction is unaffected by this limit.
    other = _open(run, symbol="GOLD", direction="short")
    assert not isinstance(other, ShadowRiskBlockedResult)


def test_open_blocked_by_total_reserved_risk(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run(risk_budget={"max_total_reserved_risk_percent": 5.0})
    first = _open(run, risk=3.0)
    assert not isinstance(first, ShadowRiskBlockedResult)
    blocked = _open(run, symbol="SILVER", risk=3.0)
    assert isinstance(blocked, ShadowRiskBlockedResult)
    assert blocked.reason == "max_total_reserved_risk_percent_exceeded"


def test_open_enforces_shadow_run_ownership(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    with pytest.raises(ShadowRunOwnershipError):
        _open(run, actor="OTHER-USER")


def test_close_theoretical_position_releases_risk_and_records_event(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    position = _open(run, risk=2.0)
    before = get_theoretical_portfolio_summary(run.shadow_run_id)
    assert before["open_position_count"] == 1
    assert before["total_reserved_risk_amount"] == 2.0

    closed = close_theoretical_position(
        position_id=position.position_id, actor="TEST-USER", correlation_id="corr-2",
        theoretical_pnl_percent=1.25, expected_state_version=position.state_version,
    )
    assert closed.state == "closed"
    assert closed.theoretical_pnl_percent == 1.25
    events = list_shadow_run_events(run.shadow_run_id)
    assert any(event.event_id == closed.close_event_id and event.event_type == "SHADOW_THEORETICAL_POSITION_CLOSED" for event in events)

    after = get_theoretical_portfolio_summary(run.shadow_run_id)
    assert after["open_position_count"] == 0
    assert after["total_reserved_risk_amount"] == 0.0
    assert after["closed_position_count"] == 1
    assert after["net_realized_theoretical_pnl_percent"] == 1.25


def test_close_rejects_wrong_state_missing_and_optimistic_lock(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    position = _open(run)
    close_theoretical_position(
        position_id=position.position_id, actor="TEST-USER", correlation_id="corr-2",
        theoretical_pnl_percent=1.0, expected_state_version=position.state_version,
    )
    with pytest.raises(ShadowPositionConflictError):
        close_theoretical_position(
            position_id=position.position_id, actor="TEST-USER", correlation_id="corr-3",
            theoretical_pnl_percent=1.0, expected_state_version=position.state_version,
        )
    with pytest.raises(ShadowPositionNotFoundError):
        close_theoretical_position(
            position_id="missing", actor="TEST-USER", correlation_id="corr-4",
            theoretical_pnl_percent=1.0, expected_state_version=0,
        )


def test_close_enforces_shadow_run_ownership(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    position = _open(run)
    with pytest.raises(ShadowRunOwnershipError):
        close_theoretical_position(
            position_id=position.position_id, actor="OTHER-USER", correlation_id="corr-2",
            theoretical_pnl_percent=1.0, expected_state_version=position.state_version,
        )


def test_open_and_close_reject_invalid_inputs(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register_run()
    with pytest.raises(ValueError):
        _open(run, direction="sideways")
    with pytest.raises(ValueError):
        _open(run, size=0)
    with pytest.raises(ValueError):
        _open(run, risk=-1.0)
