from pydantic import BaseModel, ConfigDict, Field


class PatternCandidateRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    timeframe: str = Field(default="M5", pattern="^(M1|M5|M15|H1)$")
    bar_limit: int = Field(default=500, ge=1, le=5_000)
    pivot_left: int = Field(default=2, ge=1, le=50)
    pivot_right: int = Field(default=2, ge=1, le=50)
    equality_tolerance_bps: float = Field(default=0.0, ge=0, le=500)
    liquidity_pool_tolerance_bps: float = Field(default=10.0, ge=0, le=500)
    liquidity_minimum_touches: int = Field(default=2, ge=2, le=20)
    liquidity_minimum_sweep_bps: float = Field(default=1.0, ge=0, le=500)
    liquidity_maximum_pool_age_bars: int = Field(default=250, ge=1, le=5_000)
    bos_choch_minimum_close_break_bps: float = Field(default=1.0, ge=0, le=500)
    bos_choch_maximum_pivot_age_bars: int = Field(default=250, ge=1, le=5_000)
    retest_touch_tolerance_bps: float = Field(default=5.0, ge=0, le=500)
    retest_confirmation_close_bps: float = Field(default=0.0, ge=0, le=500)
    retest_invalidation_close_bps: float = Field(default=10.0, ge=0, le=500)
    retest_maximum_age_bars: int = Field(default=100, ge=1, le=5_000)


class PatternCandidateArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_state_version: int = Field(ge=0)


class PatternCandidateClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_state_version: int = Field(ge=0)


class PatternCandidateBacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon_bars: int = Field(default=3, ge=1, le=100)
    spread_bps: float = Field(default=2.0, ge=0, le=1_000)
    commission_bps: float = Field(default=1.0, ge=0, le=1_000)
    slippage_bps: float = Field(default=1.0, ge=0, le=1_000)
    latency_bps: float = Field(default=0.5, ge=0, le=1_000)
    adverse_multiplier: float = Field(default=1.5, ge=1, le=10)
    stress_multiplier: float = Field(default=2.5, ge=1, le=10)
