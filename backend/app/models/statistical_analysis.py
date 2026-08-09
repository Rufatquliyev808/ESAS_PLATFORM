from pydantic import BaseModel, ConfigDict, Field


class StatisticalAnalysisJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    idempotency_key: str = Field(min_length=1, max_length=200)
    priority: int = Field(default=3, ge=1, le=5)
    timeframe: str = Field(default="M1", pattern="^(S1|S10|M1|M5|M15|M30|H1|H4|D1)$")
    minimum_sample_size: int = Field(default=30, ge=1, le=10_000)
