from pydantic import BaseModel, ConfigDict, Field


class VisualExperimentRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(pattern="^(S1|S10|M1|M5|M15|M30|H1|H4|D1)$")
    source_bar_fingerprint: str = Field(min_length=1)
    render_spec_id: str = Field(min_length=1)
    label_spec_id: str = Field(min_length=1)
    observation_window_bars: int = Field(ge=1, le=5_000)
    train_end_at: str = Field(min_length=1)
    validation_end_at: str = Field(min_length=1)


class VisualExperimentArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_state_version: int = Field(ge=0)
