from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from backend.app.analysis.bars import MarketBar


LABEL_SPEC_VERSION = "1.0.0"
_THRESHOLD_EPSILON = 1e-9
UP = "up"
DOWN = "down"
FLAT = "flat"
LABELED = "labeled"
INCOMPLETE_HORIZON = "incomplete_horizon"


@dataclass(frozen=True)
class LabelSpec:
    """A pre-registered horizon/threshold rule. Must be frozen by the caller
    BEFORE looking at any dataset -- this module has no dataset-wide fitting
    logic at all (by construction, it only ever looks at one sample's own
    bars), which is how the contract's "class həddi bütün datasetə baxılaraq
    optimallaşdırılmır" rule is satisfied: there is nowhere in this code for
    such optimization to even happen.
    """

    horizon_bars: int
    up_threshold_bps: float
    down_threshold_bps: float
    version: str = LABEL_SPEC_VERSION


@dataclass(frozen=True)
class LabelResult:
    label_spec_id: str
    status: str
    label_value: str | None
    label_available_at: str | None
    return_bps: float | None


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def label_spec_id(spec: LabelSpec) -> str:
    return f"sha256:{sha256(_canonical_json(asdict(spec))).hexdigest()}"


def _validate_bars(bars: tuple[MarketBar, ...]) -> None:
    if not bars:
        raise ValueError("bars must not be empty")
    symbol = bars[0].symbol
    timeframe = bars[0].timeframe
    previous_end: str | None = None
    for bar in bars:
        if bar.symbol != symbol or bar.timeframe != timeframe:
            raise ValueError("bars must share the same symbol and timeframe")
        if previous_end is not None and bar.start_at < previous_end:
            raise ValueError("bars must be sorted by start_at without overlap")
        previous_end = bar.end_at


def _validate_spec(spec: LabelSpec) -> None:
    if isinstance(spec.horizon_bars, bool) or not isinstance(spec.horizon_bars, int) or spec.horizon_bars < 1:
        raise ValueError("horizon_bars must be a positive integer")
    if spec.up_threshold_bps < spec.down_threshold_bps:
        raise ValueError("up_threshold_bps must be >= down_threshold_bps")


def compute_label(
    bars: tuple[MarketBar, ...], *, observation_end_at: str, spec: LabelSpec,
) -> LabelResult:
    """Classify the return from the observation window's last close to the
    close `spec.horizon_bars` bars later as UP/DOWN/FLAT against the
    pre-registered thresholds. `bars` must be the full historical series
    (observation window AND the bars that follow it) -- the renderer itself
    never sees these future bars, only this separate labelling pass does,
    matching the contract's "Label ... şəkil yaradılmasına təsir etmir" rule.

    If the horizon bar does not exist yet in `bars`, the label is
    INCOMPLETE_HORIZON (label_value=None) rather than guessed -- matching
    "horizon tamamlanmayan nümunə təlimə daxil edilmir". `label_available_at`
    is the horizon bar's own `end_at`: the earliest instant this label could
    actually be known, since it depends on that bar's close.
    """
    _validate_bars(bars)
    _validate_spec(spec)
    spec_id = label_spec_id(spec)

    index_by_end = {bar.end_at: index for index, bar in enumerate(bars)}
    reference_index = index_by_end.get(observation_end_at)
    if reference_index is None:
        raise ValueError("observation_end_at does not match any bar's end_at in bars")

    target_index = reference_index + spec.horizon_bars
    if target_index >= len(bars):
        return LabelResult(spec_id, INCOMPLETE_HORIZON, None, None, None)

    reference_close = bars[reference_index].close
    target_bar = bars[target_index]
    return_bps = (target_bar.close - reference_close) / reference_close * 10_000

    if return_bps >= spec.up_threshold_bps - _THRESHOLD_EPSILON:
        value = UP
    elif return_bps <= spec.down_threshold_bps + _THRESHOLD_EPSILON:
        value = DOWN
    else:
        value = FLAT

    return LabelResult(spec_id, LABELED, value, target_bar.end_at, return_bps)
