from dataclasses import dataclass
from datetime import UTC, datetime
import secrets

from backend.app.database.connection import get_connection
from backend.app.database.shadow_event_repository import record_shadow_event
from backend.app.database.shadow_run_repository import ShadowRunOwnershipError, get_shadow_run


DIRECTIONS = frozenset({"long", "short"})


class ShadowPositionNotFoundError(LookupError):
    pass


class ShadowPositionConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShadowTheoreticalPosition:
    position_id: str
    shadow_run_id: str
    participant_id: str
    symbol: str
    direction: str
    theoretical_size: float
    reserved_risk_amount: float
    opened_at: str
    open_event_id: str
    state: str
    state_version: int
    closed_at: str | None
    close_event_id: str | None
    theoretical_pnl_percent: float | None
    updated_at: str


@dataclass(frozen=True)
class ShadowRiskBlockedResult:
    reason: str
    event_id: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _new_position_id() -> str:
    return f"shadow_position_{secrets.token_urlsafe(18)}"


def _row_to_position(row: object) -> ShadowTheoreticalPosition:
    return ShadowTheoreticalPosition(
        position_id=row["position_id"], shadow_run_id=row["shadow_run_id"],
        participant_id=row["participant_id"], symbol=row["symbol"], direction=row["direction"],
        theoretical_size=row["theoretical_size"], reserved_risk_amount=row["reserved_risk_amount"],
        opened_at=row["opened_at"], open_event_id=row["open_event_id"],
        state=row["state"], state_version=row["state_version"],
        closed_at=row["closed_at"], close_event_id=row["close_event_id"],
        theoretical_pnl_percent=row["theoretical_pnl_percent"], updated_at=row["updated_at"],
    )


def _open_positions(connection, shadow_run_id: str) -> tuple[object, ...]:
    return tuple(connection.execute(
        "SELECT * FROM shadow_theoretical_positions WHERE shadow_run_id = ? AND state = 'open';",
        (shadow_run_id,),
    ).fetchall())


def _risk_violation(
    open_rows: tuple[object, ...], *, risk_budget: dict[str, object], symbol: str, direction: str,
    reserved_risk_amount: float,
) -> str | None:
    """Contract section 6 position-level limits only (concurrent position
    count, same symbol+direction concentration, total reserved risk).
    Daily-loss and drawdown limits are time-series concepts over realized
    PnL and are deliberately not implemented in this skeleton -- there is
    no live decision feed yet to realize any PnL against. A limit key
    absent from risk_budget is treated as unlimited, not enforced.
    """
    max_concurrent = risk_budget.get("max_concurrent_positions")
    if isinstance(max_concurrent, (int, float)) and len(open_rows) >= max_concurrent:
        return "max_concurrent_positions_exceeded"

    max_same = risk_budget.get("max_concurrent_per_symbol_direction")
    if isinstance(max_same, (int, float)):
        same_count = sum(1 for row in open_rows if row["symbol"] == symbol and row["direction"] == direction)
        if same_count >= max_same:
            return "max_concurrent_per_symbol_direction_exceeded"

    max_total_risk = risk_budget.get("max_total_reserved_risk_percent")
    if isinstance(max_total_risk, (int, float)):
        current_total = sum(row["reserved_risk_amount"] for row in open_rows)
        if current_total + reserved_risk_amount > max_total_risk:
            return "max_total_reserved_risk_percent_exceeded"

    return None


def open_theoretical_position(
    *, shadow_run_id: str, participant_id: str, symbol: str, direction: str,
    theoretical_size: float, reserved_risk_amount: float, actor: str, correlation_id: str,
) -> ShadowTheoreticalPosition | ShadowRiskBlockedResult:
    """Open a theoretical position, or record SHADOW_RISK_BLOCKED instead if
    it would violate the run's own declared risk budget (concentration/
    total reserved risk, contract section 6). This ledger has zero
    relationship to any real account or MT5 position by construction.

    An advisory limit check happens first (own transaction) so a doomed
    open never gets an OPENED event recorded for it; the authoritative
    check happens again atomically with the insert itself, closing the
    race window between two concurrent opens. In the rare case where a
    concurrent open wins that race after this function already recorded
    its OPENED event, ShadowPositionConflictError is raised -- the event
    log then contains an attempt that was not applied, which is an
    accepted limitation of this skeleton (no live concurrent caller exists
    yet to actually trigger it).
    """
    normalized_run_id = _required_text(shadow_run_id, "shadow_run_id")
    normalized_participant_id = _required_text(participant_id, "participant_id")
    normalized_symbol = _required_text(symbol, "symbol")
    normalized_actor = _required_text(actor, "actor")
    if direction not in DIRECTIONS:
        raise ValueError("direction must be 'long' or 'short'")
    if theoretical_size <= 0:
        raise ValueError("theoretical_size must be positive")
    if reserved_risk_amount < 0:
        raise ValueError("reserved_risk_amount must not be negative")

    run = get_shadow_run(normalized_run_id)
    if run.created_by != normalized_actor:
        raise ShadowRunOwnershipError("shadow run belongs to another user")
    risk_budget = run.risk_budget

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        open_rows = _open_positions(connection, normalized_run_id)
        advisory_violation = _risk_violation(
            open_rows, risk_budget=risk_budget, symbol=normalized_symbol,
            direction=direction, reserved_risk_amount=reserved_risk_amount,
        )

    if advisory_violation is not None:
        event = record_shadow_event(
            shadow_run_id=normalized_run_id, event_type="SHADOW_RISK_BLOCKED",
            correlation_id=correlation_id, actor=normalized_actor,
            payload={
                "reason": advisory_violation, "symbol": normalized_symbol, "direction": direction,
                "participant_id": normalized_participant_id,
            },
        )
        return ShadowRiskBlockedResult(reason=advisory_violation, event_id=event.event_id)

    event = record_shadow_event(
        shadow_run_id=normalized_run_id, event_type="SHADOW_THEORETICAL_POSITION_OPENED",
        correlation_id=correlation_id, actor=normalized_actor,
        payload={
            "symbol": normalized_symbol, "direction": direction, "theoretical_size": theoretical_size,
            "reserved_risk_amount": reserved_risk_amount, "participant_id": normalized_participant_id,
        },
    )

    now = _now()
    position_id = _new_position_id()
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        open_rows = _open_positions(connection, normalized_run_id)
        violation = _risk_violation(
            open_rows, risk_budget=risk_budget, symbol=normalized_symbol,
            direction=direction, reserved_risk_amount=reserved_risk_amount,
        )
        if violation is not None:
            raise ShadowPositionConflictError(
                f"risk budget violated by a concurrently opened position ({violation}); "
                f"see event {event.event_id} for the attempted open that lost the race"
            )
        connection.execute(
            """
            INSERT INTO shadow_theoretical_positions
            (position_id, shadow_run_id, participant_id, symbol, direction, theoretical_size,
             reserved_risk_amount, opened_at, open_event_id, state, state_version, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', 0, ?);
            """,
            (
                position_id, normalized_run_id, normalized_participant_id, normalized_symbol, direction,
                theoretical_size, reserved_risk_amount, now, event.event_id, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM shadow_theoretical_positions WHERE position_id = ?;", (position_id,),
        ).fetchone()
    return _row_to_position(row)


def close_theoretical_position(
    *, position_id: str, actor: str, correlation_id: str, theoretical_pnl_percent: float,
    expected_state_version: int,
) -> ShadowTheoreticalPosition:
    """Close an open theoretical position and release its reserved risk."""
    normalized_position_id = _required_text(position_id, "position_id")
    normalized_actor = _required_text(actor, "actor")

    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM shadow_theoretical_positions WHERE position_id = ?;",
            (normalized_position_id,),
        ).fetchone()
        if row is None:
            raise ShadowPositionNotFoundError("shadow theoretical position was not found")
        if row["state_version"] != expected_state_version:
            raise ShadowPositionConflictError("shadow theoretical position changed since it was loaded")
        if row["state"] != "open":
            raise ShadowPositionConflictError(f"cannot close from state {row['state']}")
        shadow_run_id = row["shadow_run_id"]

    run = get_shadow_run(shadow_run_id)
    if run.created_by != normalized_actor:
        raise ShadowRunOwnershipError("shadow run belongs to another user")

    event = record_shadow_event(
        shadow_run_id=shadow_run_id, event_type="SHADOW_THEORETICAL_POSITION_CLOSED",
        correlation_id=correlation_id, actor=normalized_actor,
        payload={"position_id": normalized_position_id, "theoretical_pnl_percent": theoretical_pnl_percent},
    )

    now = _now()
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        updated = connection.execute(
            """
            UPDATE shadow_theoretical_positions
            SET state = 'closed', state_version = state_version + 1, closed_at = ?,
                close_event_id = ?, theoretical_pnl_percent = ?, updated_at = ?
            WHERE position_id = ? AND state_version = ?;
            """,
            (now, event.event_id, theoretical_pnl_percent, now, normalized_position_id, expected_state_version),
        )
        if updated.rowcount != 1:
            raise ShadowPositionConflictError("shadow theoretical position changed during transition")
        result_row = connection.execute(
            "SELECT * FROM shadow_theoretical_positions WHERE position_id = ?;", (normalized_position_id,),
        ).fetchone()
    return _row_to_position(result_row)


def list_theoretical_positions(shadow_run_id: str) -> tuple[ShadowTheoreticalPosition, ...]:
    normalized = _required_text(shadow_run_id, "shadow_run_id")
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM shadow_theoretical_positions WHERE shadow_run_id = ? ORDER BY opened_at DESC;",
            (normalized,),
        ).fetchall()
    return tuple(_row_to_position(row) for row in rows)


def get_theoretical_portfolio_summary(shadow_run_id: str) -> dict[str, object]:
    """Minimal observability (contract section 10): open theoretical
    positions, total reserved risk, and net realized theoretical PnL.
    Drawdown is a running time-series over realized PnL and is not
    computed here yet -- deferred alongside daily-loss limits."""
    normalized = _required_text(shadow_run_id, "shadow_run_id")
    with get_connection() as connection:
        open_rows = _open_positions(connection, normalized)
        closed_rows = connection.execute(
            "SELECT theoretical_pnl_percent FROM shadow_theoretical_positions WHERE shadow_run_id = ? AND state = 'closed';",
            (normalized,),
        ).fetchall()
    realized = [row["theoretical_pnl_percent"] for row in closed_rows if row["theoretical_pnl_percent"] is not None]
    return {
        "shadow_run_id": normalized,
        "open_position_count": len(open_rows),
        "total_reserved_risk_amount": sum(row["reserved_risk_amount"] for row in open_rows),
        "closed_position_count": len(closed_rows),
        "net_realized_theoretical_pnl_percent": sum(realized) if realized else None,
    }
