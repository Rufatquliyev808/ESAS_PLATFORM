from dataclasses import dataclass
from datetime import datetime

from backend.app.analysis.bars import build_closed_mid_bars
from backend.app.analysis.replay_analysis import ReplayDatasetChangedError
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_materializer import (
    BarFingerprintMismatchError,
    VisualDatasetMaterialization,
    materialize_visual_dataset,
)
from backend.app.analysis.visual_render import RenderSpec
from backend.app.database.replay_session_repository import (
    ReplaySession,
    ReplayTransitionConflictError,
    get_replay_session,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_dataset_repository import (
    PersistedVisualDatasetManifest,
    artifact_checksum_for,
    persist_dataset_manifest,
    persist_materialized_samples,
)
from backend.app.database.visual_experiment_repository import (
    PersistedVisualExperiment,
    VisualExperimentOwnershipError,
    get_visual_experiment,
    mark_rendering_failed,
    start_rendering,
)
from backend.app.replay.dataset_snapshot import create_dataset_snapshot
from backend.app.storage.artifact_store import ArtifactIntegrityError, put_artifact


ARTIFACT_EXTENSION = "png"


@dataclass(frozen=True)
class VisualExperimentRenderingResult:
    experiment: PersistedVisualExperiment
    manifest: PersistedVisualDatasetManifest
    sample_count: int


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _render_spec_from_dict(payload: dict[str, object]) -> RenderSpec:
    return RenderSpec(
        width=payload["width"], height=payload["height"],
        padding_top=payload["padding_top"], padding_bottom=payload["padding_bottom"],
        padding_left=payload["padding_left"], padding_right=payload["padding_right"],
        background_rgb=tuple(payload["background_rgb"]),
        bullish_rgb=tuple(payload["bullish_rgb"]),
        bearish_rgb=tuple(payload["bearish_rgb"]),
        wick_rgb=tuple(payload["wick_rgb"]),
        version=payload["version"],
    )


def _label_spec_from_dict(payload: dict[str, object]) -> LabelSpec:
    return LabelSpec(
        horizon_bars=payload["horizon_bars"], up_threshold_bps=payload["up_threshold_bps"],
        down_threshold_bps=payload["down_threshold_bps"], version=payload["version"],
    )


def render_visual_experiment(
    experiment_id: str, *, actor: str, actor_role: str,
) -> VisualExperimentRenderingResult:
    """Orchestrates the Phase 5 `registered -> rendering` step: rebuilds the
    experiment's replay session bars, runs the Deterministic Visual Dataset
    Materializer v1, writes each sample's PNG to the local content-addressed
    artifact store (`storage/artifact_store.py` -- see
    `docs/architecture/ARTIFACT_STORE_CONTRACT.md`), and persists the
    resulting sample lineage/manifest rows. Every computation step
    (rendering, labelling, splitting, manifesting) is done by the existing,
    already-tested `visual_materializer.py` -- this module only adds the
    replay-session bar rebuild, the lifecycle transition, artifact writes,
    and persistence around it.

    On any failure (dataset drift, bar-fingerprint mismatch, or any other
    materialization error) the experiment is moved to `failed` and the
    original exception is re-raised -- it is never left silently stuck in
    `rendering`.
    """
    experiment = get_visual_experiment(experiment_id)
    if experiment.created_by != actor:
        raise VisualExperimentOwnershipError("visual experiment belongs to another user")

    session: ReplaySession = get_replay_session(experiment.replay_session_id)
    if session.state != "completed":
        raise ReplayTransitionConflictError("Replay session is not completed")

    start_at, end_at = _timestamp(session.start_at), _timestamp(session.end_at)
    snapshot = create_dataset_snapshot(symbol=session.symbol, start_at=start_at, end_at=end_at)
    if (
        snapshot.tick_count != session.dataset_tick_count
        or snapshot.fingerprint != session.dataset_fingerprint
        or snapshot.first_position != session.first_position
        or snapshot.last_position != session.last_position
    ):
        raise ReplayDatasetChangedError(
            "Replay dataset no longer matches the completed session snapshot"
        )

    rendering_experiment = start_rendering(
        experiment_id=experiment.experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=experiment.state_version,
    )

    try:
        ticks = (
            tick
            for batch in iter_tick_batches(symbol=session.symbol, start_at=start_at, end_at=end_at)
            for tick in batch
        )
        bar_result = build_closed_mid_bars(
            ticks, timeframe=experiment.timeframe, end_at=end_at,
            source_fingerprint=session.dataset_fingerprint,
        )
        materialization: VisualDatasetMaterialization = materialize_visual_dataset(
            bar_result.bars,
            bar_fingerprint=bar_result.fingerprint,
            source_bar_fingerprint=experiment.source_bar_fingerprint,
            render_spec=_render_spec_from_dict(experiment.render_spec),
            label_spec=_label_spec_from_dict(experiment.label_spec),
            observation_window_bars=experiment.observation_window_bars,
            train_end_at=experiment.train_end_at,
            validation_end_at=experiment.validation_end_at,
        )
        for item in materialization.samples:
            put_artifact(artifact_checksum_for(item), item.image.png_bytes, extension=ARTIFACT_EXTENSION)
    except (
        BarFingerprintMismatchError, ReplayDatasetChangedError, ValueError,
        ArtifactIntegrityError, OSError,
    ):
        mark_rendering_failed(
            experiment_id=experiment.experiment_id, actor=actor, actor_role=actor_role,
            expected_state_version=rendering_experiment.state_version,
        )
        raise

    persist_materialized_samples(experiment.experiment_id, materialization.samples)
    manifest = persist_dataset_manifest(
        experiment.experiment_id, materialization.manifest,
        dataset_fingerprint=materialization.dataset_fingerprint,
    )

    return VisualExperimentRenderingResult(
        experiment=rendering_experiment, manifest=manifest, sample_count=len(materialization.samples),
    )
