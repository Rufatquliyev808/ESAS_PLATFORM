from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BridgeStatusReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["esas.mt5.bridge"]
    module_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    queue_status: Literal["healthy", "backlogged", "full", "degraded"]
    queue_count: int = Field(ge=0)
    queue_capacity: int = Field(gt=0)
    rejected_events: int = Field(ge=0)
    last_queue_error: Literal[
        "none",
        "queue_full",
        "serialization_failed",
        "disk_open_failed",
        "disk_seek_failed",
        "disk_write_failed",
        "corrupt_queue",
    ]

    @model_validator(mode="after")
    def validate_queue_counts(self) -> "BridgeStatusReport":
        if self.queue_count > self.queue_capacity:
            raise ValueError("queue_count cannot exceed queue_capacity")

        if self.queue_status == "full" and (
            self.queue_count != self.queue_capacity
        ):
            raise ValueError(
                "full queue status requires queue_count == queue_capacity"
            )

        return self
