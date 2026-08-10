from pydantic import BaseModel, ConfigDict, Field


class RenderSpecInput(BaseModel):
    """Mirrors `backend.app.analysis.visual_render.RenderSpec` exactly --
    defaults match `DEFAULT_RENDER_SPEC` so a caller can register an
    experiment without touching image geometry/colour at all.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    width: int = Field(default=512, ge=16, le=4_096)
    height: int = Field(default=256, ge=16, le=4_096)
    padding_top: int = Field(default=8, ge=0, le=512)
    padding_bottom: int = Field(default=8, ge=0, le=512)
    padding_left: int = Field(default=8, ge=0, le=512)
    padding_right: int = Field(default=8, ge=0, le=512)
    background_rgb: tuple[int, int, int] = (255, 255, 255)
    bullish_rgb: tuple[int, int, int] = (0, 128, 0)
    bearish_rgb: tuple[int, int, int] = (192, 0, 0)
    wick_rgb: tuple[int, int, int] = (32, 32, 32)


class LabelSpecInput(BaseModel):
    """Mirrors `backend.app.analysis.visual_label.LabelSpec` exactly. No
    default thresholds -- the caller must consciously choose the horizon
    and up/down bands rather than inherit an implicit trading assumption.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon_bars: int = Field(ge=1, le=5_000)
    up_threshold_bps: float = Field(ge=-100_000, le=100_000)
    down_threshold_bps: float = Field(ge=-100_000, le=100_000)


class VisualExperimentRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(pattern="^(S1|S10|M1|M5|M15|M30|H1|H4|D1)$")
    source_bar_fingerprint: str = Field(min_length=1)
    render_spec: RenderSpecInput = RenderSpecInput()
    label_spec: LabelSpecInput
    observation_window_bars: int = Field(ge=1, le=5_000)
    train_end_at: str = Field(min_length=1)
    validation_end_at: str = Field(min_length=1)


class VisualExperimentArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_state_version: int = Field(ge=0)


class VisualExperimentRenderingJobRequest(BaseModel):
    """No render/label/split parameters here -- everything the materializer
    needs is already frozen on the experiment at registration time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    idempotency_key: str = Field(min_length=1, max_length=200)
    priority: int = Field(default=3, ge=1, le=5)


class VisualExperimentTrainingJobRequest(BaseModel):
    """Unlike rendering, the model/training spec is NOT frozen on the
    experiment at registration time -- the caller chooses it here. Mirrors
    `backend.app.analysis.visual_model_spec.ModelSpec`/`TrainingSpec`
    exactly; the trainer itself (not this model) validates that
    `architecture_id` is a supported architecture.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    idempotency_key: str = Field(min_length=1, max_length=200)
    priority: int = Field(default=3, ge=1, le=5)

    architecture_id: str = Field(min_length=1, max_length=200)
    preprocessing_policy: str = Field(min_length=1, max_length=200)
    class_weight_policy: str = Field(min_length=1, max_length=50)

    seed: int
    optimizer: str = Field(min_length=1, max_length=100)
    loss: str = Field(min_length=1, max_length=100)
    batch_size: int = Field(ge=1, le=1_000_000)
    max_epochs: int = Field(ge=1, le=1_000_000)
    compute_requirement: str = Field(min_length=1, max_length=20)
