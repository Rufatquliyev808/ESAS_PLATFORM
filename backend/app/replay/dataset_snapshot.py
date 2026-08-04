from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from backend.app.database.tick_replay_repository import (
    TickPosition,
    iter_tick_identity_batches,
)


DATASET_FINGERPRINT_VERSION = "sha256-event-id-v1"
EMPTY_DATASET_FINGERPRINT = f"sha256:{sha256().hexdigest()}"


class Digest(Protocol):
    def update(self, data: bytes) -> None: ...


@dataclass(frozen=True)
class ReplayDatasetSnapshot:
    tick_count: int
    first_position: TickPosition | None
    last_position: TickPosition | None
    fingerprint: str
    fingerprint_version: str = DATASET_FINGERPRINT_VERSION


def _update_event_id_fingerprint(digest: Digest, event_id: str) -> None:
    encoded_event_id = event_id.encode("utf-8")
    digest.update(len(encoded_event_id).to_bytes(8, byteorder="big"))
    digest.update(encoded_event_id)


def create_dataset_snapshot(
    *,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    batch_size: int = 1000,
) -> ReplayDatasetSnapshot:
    digest = sha256()
    tick_count = 0
    first_position: TickPosition | None = None
    last_position: TickPosition | None = None

    for batch in iter_tick_identity_batches(
        symbol=symbol,
        start_at=start_at,
        end_at=end_at,
        batch_size=batch_size,
    ):
        for position in batch:
            if first_position is None:
                first_position = position
            last_position = position
            tick_count += 1
            _update_event_id_fingerprint(digest, position.event_id)

    return ReplayDatasetSnapshot(
        tick_count=tick_count,
        first_position=first_position,
        last_position=last_position,
        fingerprint=f"sha256:{digest.hexdigest()}",
    )
