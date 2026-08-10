from pydantic import BaseModel, ConfigDict, Field


class ShadowRunParticipantInput(BaseModel):
    """`visual_experiment_id` is a lineage-only connection (Phase 5 ->
    Phase 9): when set, the repository verifies the referenced Visual AI
    experiment is currently `accepted_for_shadow` and pins its trained
    model's and acceptance decision's checksums as an immutable snapshot.
    It never generates decisions -- only "champion"/"challenger" role and
    module_id/module_version do that. Only a "challenger" may set it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    role: str = Field(pattern="^(champion|challenger)$")
    module_id: str = Field(min_length=1, max_length=200)
    module_version: str = Field(min_length=1, max_length=50)
    visual_experiment_id: str | None = Field(default=None, min_length=1, max_length=200)


class ShadowRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    planned_end_at: str = Field(min_length=1)
    code_commit: str = Field(min_length=1, max_length=100)
    config_hash: str = Field(min_length=1, max_length=200)
    feature_claim_versions: list[str] = Field(min_length=1)
    symbols: list[str] = Field(min_length=1)
    timeframes: list[str] = Field(min_length=1)
    sessions: list[str] = Field(min_length=1)
    accepted_market_regimes: list[str] = Field(min_length=1)
    minimum_market_open_duration_seconds: int = Field(ge=0)
    minimum_eligible_decision_count: int = Field(ge=1)
    primary_metric: str = Field(min_length=1, max_length=200)
    primary_metric_threshold: float
    secondary_metrics: dict[str, object] = Field(default_factory=dict)
    failure_rules: dict[str, object] = Field(default_factory=dict)
    theoretical_fill_model: dict[str, object] = Field(default_factory=dict)
    risk_budget: dict[str, object] = Field(default_factory=dict)
    data_quality_policy: dict[str, object] = Field(default_factory=dict)
    approved_by: str = Field(min_length=1, max_length=200)
    rollback_plan: str = Field(min_length=1, max_length=2_000)
    participants: list[ShadowRunParticipantInput] = Field(min_length=1, max_length=20)


class ShadowRunTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_state_version: int = Field(ge=0)


class ShadowRunHaltRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    expected_state_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=2_000)


class ShadowEventCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_type: str = Field(min_length=1, max_length=100)
    correlation_id: str = Field(min_length=1, max_length=200)
    payload: dict[str, object] = Field(default_factory=dict)


class ShadowPositionOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    participant_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1, max_length=20)
    direction: str = Field(pattern="^(long|short)$")
    theoretical_size: float = Field(gt=0)
    reserved_risk_amount: float = Field(ge=0)
    correlation_id: str = Field(min_length=1, max_length=200)


class ShadowPositionCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    theoretical_pnl_percent: float
    expected_state_version: int = Field(ge=0)
    correlation_id: str = Field(min_length=1, max_length=200)
