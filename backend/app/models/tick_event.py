from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TickPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bid: float = Field(ge=0)
    ask: float = Field(ge=0)
    last: float = Field(ge=0)
    volume: int = Field(ge=0)
    flags: int = Field(ge=0)
    source_time_msc: int = Field(gt=0)


class TickMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    module_version: str


class TickReceivedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str
    event_type: Literal["TICK_RECEIVED"]
    timestamp: datetime
    source: Literal["esas.mt5.bridge"]
    version: Literal["1.0"]
    symbol: str = Field(min_length=1)
    payload: TickPayload
    metadata: TickMetadata