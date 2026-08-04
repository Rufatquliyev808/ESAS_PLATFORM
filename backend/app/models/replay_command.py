from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplayCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command: Literal["start", "step", "pause", "resume", "cancel"]
    expected_state_version: int = Field(ge=0)
    requested_ticks: int | None = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_requested_ticks(self) -> "ReplayCommandRequest":
        if self.command == "step" and self.requested_ticks is None:
            raise ValueError("requested_ticks is required for step")
        if self.command != "step" and self.requested_ticks is not None:
            raise ValueError("requested_ticks is only valid for step")
        return self
