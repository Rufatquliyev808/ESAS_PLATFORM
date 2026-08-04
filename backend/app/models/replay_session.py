from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplaySessionCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    symbol: str = Field(min_length=1, max_length=64)
    start_at: datetime
    end_at: datetime
    mode: Literal["step", "max_speed"]

    @model_validator(mode="after")
    def validate_interval(self) -> "ReplaySessionCreateRequest":
        if self.start_at.tzinfo is None or self.start_at.utcoffset() is None:
            raise ValueError("start_at must include a timezone")
        if self.end_at.tzinfo is None or self.end_at.utcoffset() is None:
            raise ValueError("end_at must include a timezone")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")
        return self
