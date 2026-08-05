from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import secrets

from backend.app.database.connection import get_connection
from backend.app.database.shadow_run_repository import ShadowRunNotFoundError


SHADOW_EVENT_TYPES = frozenset({
    "SHADOW_RUN_STARTED",
    "SHADOW_DECISION_RECORDED",
    "SHADOW_RISK_BLOCKED",
    "SHADOW_THEORETICAL_POSITION_OPENED",
    "SHADOW_THEORETICAL_POSITION_CLOSED",
    "SHADOW_DATA_GAP_RECORDED",
    "SHADOW_RUN_COMPLETED",
    "SHADOW_PROMOTION_RECOMMENDED",
    "SHADOW_PROMOTION_REJECTED",
})

# Contract section 9: "Heç biri ORDER_*, broker ticket-i və ya real mövqe
# identifikatoru yarada bilməz." event_type's CHECK constraint already makes
# an ORDER_* event structurally impossible; this is a second, narrower guard
# against a payload smuggling real broker/order identifiers into an
# otherwise-legal SHADOW_* event.
FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "order_id", "broker_ticket_id", "broker_ticket", "real_position_id",
    "execution_price", "account_id", "mt5_ticket", "mt5_position_id",
})


@dataclass(frozen=True)
class PersistedShadowEvent:
    event_id: str
    shadow_run_id: str
    event_type: str
    correlation_id: str
    actor: str
    payload: dict[str, object]
    payload_hash: str
    occurred_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _row_to_event(row: object) -> PersistedShadowEvent:
    return PersistedShadowEvent(
        event_id=row["event_id"], shadow_run_id=row["shadow_run_id"], event_type=row["event_type"],
        correlation_id=row["correlation_id"], actor=row["actor"],
        payload=json.loads(row["payload_json"]), payload_hash=row["payload_hash"],
        occurred_at=row["occurred_at"],
    )


def record_shadow_event(
    *, shadow_run_id: str, event_type: str, correlation_id: str, actor: str, payload: dict[str, object],
) -> PersistedShadowEvent:
    normalized_run_id = _required_text(shadow_run_id, "shadow_run_id")
    normalized_correlation = _required_text(correlation_id, "correlation_id")
    normalized_actor = _required_text(actor, "actor")
    if event_type not in SHADOW_EVENT_TYPES:
        raise ValueError(f"unsupported shadow event_type: {event_type}")
    forbidden = FORBIDDEN_PAYLOAD_KEYS & set(payload)
    if forbidden:
        raise ValueError(
            f"shadow event payload must not contain reserved order/broker fields: {sorted(forbidden)}"
        )

    now = datetime.now(UTC).isoformat(timespec="microseconds")
    event_id = f"shadow_event_{secrets.token_urlsafe(18)}"
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = f"sha256:{sha256(payload_json.encode()).hexdigest()}"

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        run_row = connection.execute(
            "SELECT shadow_run_id FROM shadow_runs WHERE shadow_run_id = ?;", (normalized_run_id,),
        ).fetchone()
        if run_row is None:
            raise ShadowRunNotFoundError("shadow run was not found")
        connection.execute(
            """
            INSERT INTO shadow_events
            (event_id, shadow_run_id, event_type, correlation_id, actor, payload_json, payload_hash, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (event_id, normalized_run_id, event_type, normalized_correlation, normalized_actor, payload_json, payload_hash, now),
        )
        row = connection.execute("SELECT * FROM shadow_events WHERE event_id = ?;", (event_id,)).fetchone()
    return _row_to_event(row)


def list_shadow_run_events(shadow_run_id: str) -> tuple[PersistedShadowEvent, ...]:
    normalized = _required_text(shadow_run_id, "shadow_run_id")
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM shadow_events WHERE shadow_run_id = ? ORDER BY occurred_at ASC, event_id ASC;",
            (normalized,),
        ).fetchall()
    return tuple(_row_to_event(row) for row in rows)
