from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from backend.app.database.connection import get_connection
from backend.app.database.replay_session_repository import (
    ReplaySessionNotFoundError,
    ReplayTransitionConflictError,
)
from backend.app.database.tick_replay_repository import (
    TickPosition,
    iter_tick_identity_batches,
)


RESULT_MANIFEST_VERSION = "1.0"
RESULT_FINGERPRINT_VERSION = "sha256-replay-event-id-v1"
_RESULT_DOMAIN = b"ESAS_REPLAY_RESULT_V1\x00"


class ReplayManifestMismatchError(ValueError):
    pass


class Digest(Protocol):
    def update(self, data: bytes) -> None: ...


@dataclass(frozen=True)
class ReplayResultManifest:
    manifest_version: str
    session_id: str
    symbol: str
    start_at: str
    end_at: str
    mode: str
    replay_contract_version: str
    quality_rule_version: str
    dataset_tick_count: int
    dataset_fingerprint: str
    result_tick_count: int
    result_fingerprint: str
    result_fingerprint_version: str
    first_position: TickPosition | None
    last_position: TickPosition | None
    completed_at: str


@dataclass(frozen=True)
class ReplayReproductionProof:
    first_session_id: str
    second_session_id: str
    result_tick_count: int
    result_fingerprint: str
    result_fingerprint_version: str


def _row_position(
    row: object,
    timestamp_field: str,
    event_field: str,
) -> TickPosition | None:
    timestamp = row[timestamp_field]
    event_id = row[event_field]
    if timestamp is None and event_id is None:
        return None
    if timestamp is None or event_id is None:
        raise ReplayTransitionConflictError(
            "stored replay position is incomplete"
        )
    return TickPosition(datetime.fromisoformat(timestamp), event_id)


def _update_result_fingerprint(digest: Digest, event_id: str) -> None:
    encoded = event_id.encode("utf-8")
    digest.update(len(encoded).to_bytes(8, byteorder="big"))
    digest.update(encoded)


def create_replay_result_manifest(
    *,
    session_id: str,
    batch_size: int = 1000,
) -> ReplayResultManifest:
    normalized_session_id = session_id.strip()
    if not normalized_session_id:
        raise ValueError("session_id must not be empty")
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")

    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM replay_sessions WHERE session_id = ?;",
            (normalized_session_id,),
        ).fetchone()
    if row is None:
        raise ReplaySessionNotFoundError("replay session was not found")
    if row["state"] != "completed":
        raise ReplayTransitionConflictError(
            "only a completed replay session can produce a final manifest"
        )
    if row["processed_ticks"] != row["dataset_tick_count"]:
        raise ReplayTransitionConflictError(
            "completed replay progress does not match its dataset"
        )

    digest = sha256()
    digest.update(_RESULT_DOMAIN)
    dataset_digest = sha256()
    tick_count = 0
    first_position = None
    last_position = None
    for batch in iter_tick_identity_batches(
        symbol=row["symbol"],
        start_at=datetime.fromisoformat(row["start_at"]),
        end_at=datetime.fromisoformat(row["end_at"]),
        batch_size=batch_size,
    ):
        for position in batch:
            if first_position is None:
                first_position = position
            last_position = position
            tick_count += 1
            _update_result_fingerprint(digest, position.event_id)
            _update_result_fingerprint(dataset_digest, position.event_id)

    stored_first = _row_position(
        row, "first_event_timestamp", "first_event_id"
    )
    stored_last = _row_position(
        row, "last_event_timestamp", "last_event_id"
    )
    checkpoint = _row_position(
        row, "checkpoint_event_timestamp", "checkpoint_event_id"
    )
    if (
        tick_count != row["dataset_tick_count"]
        or f"sha256:{dataset_digest.hexdigest()}"
        != row["dataset_fingerprint"]
        or first_position != stored_first
        or last_position != stored_last
        or (tick_count > 0 and checkpoint != stored_last)
        or (tick_count == 0 and checkpoint is not None)
    ):
        raise ReplayTransitionConflictError(
            "replay result no longer matches the session dataset"
        )

    return ReplayResultManifest(
        manifest_version=RESULT_MANIFEST_VERSION,
        session_id=normalized_session_id,
        symbol=row["symbol"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        mode=row["mode"],
        replay_contract_version=row["replay_contract_version"],
        quality_rule_version=row["quality_rule_version"],
        dataset_tick_count=row["dataset_tick_count"],
        dataset_fingerprint=row["dataset_fingerprint"],
        result_tick_count=tick_count,
        result_fingerprint=f"sha256:{digest.hexdigest()}",
        result_fingerprint_version=RESULT_FINGERPRINT_VERSION,
        first_position=first_position,
        last_position=last_position,
        completed_at=row["completed_at"],
    )


def prove_replay_reproduction(
    first: ReplayResultManifest,
    second: ReplayResultManifest,
) -> ReplayReproductionProof:
    comparable_fields = (
        "manifest_version",
        "symbol",
        "start_at",
        "end_at",
        "mode",
        "replay_contract_version",
        "quality_rule_version",
        "dataset_tick_count",
        "dataset_fingerprint",
        "result_tick_count",
        "result_fingerprint",
        "result_fingerprint_version",
        "first_position",
        "last_position",
    )
    mismatches = [
        field
        for field in comparable_fields
        if getattr(first, field) != getattr(second, field)
    ]
    if mismatches:
        raise ReplayManifestMismatchError(
            "replay manifests are incompatible: " + ", ".join(mismatches)
        )

    return ReplayReproductionProof(
        first_session_id=first.session_id,
        second_session_id=second.session_id,
        result_tick_count=first.result_tick_count,
        result_fingerprint=first.result_fingerprint,
        result_fingerprint_version=first.result_fingerprint_version,
    )
