from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
import sqlite3
from dataclasses import asdict

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database.tick_repository import save_tick_event
from backend.app.database.tick_statistics import get_tick_statistics
from backend.app.database.operational_status import get_operational_status
from backend.app.database.loss_acknowledgements import acknowledge_loss
from backend.app.operational.bridge_status import (
    get_bridge_status,
    save_bridge_status,
)

from backend.app.database.connection import (
    initialize_database,
    verify_database_writable,
)
from backend.app.models.tick_event import TickReceivedEvent
from backend.app.models.bridge_status import (
    BridgeStatusReport,
    LossAcknowledgementRequest,
)
from backend.app.models.replay_session import ReplaySessionCreateRequest
from backend.app.models.replay_command import ReplayCommandRequest
from backend.app.models.pattern_candidate import (
    PatternCandidateArchiveRequest,
    PatternCandidateBacktestJobRequest,
    PatternCandidateBacktestRequest,
    PatternCandidateClassifyRequest,
    PatternCandidateRegisterRequest,
)
from backend.app.auth import (
    LoginRequest,
    create_session,
    require_bridge_key,
    require_dashboard_session,
    revoke_dashboard_session,
)
from backend.app.database.replay_session_repository import (
    ReplaySessionListPosition,
    ReplaySessionNotFoundError,
    ReplayTransitionConflictError,
    create_replay_session,
    get_replay_session,
    list_replay_sessions,
)
from backend.app.database.replay_command_repository import (
    ReplayOwnershipError,
    execute_replay_command,
)
from backend.app.quality.report import create_replay_quality_report
from backend.app.analysis.replay_analysis import (
    ReplayDatasetChangedError,
    create_replay_technical_analysis,
)
from backend.app.strategies.replay_strategy import create_replay_strategy_analysis
from backend.app.strategies.pattern_hypothesis_registry import get_pattern_hypothesis_registry
from backend.app.strategies.replay_pattern_candidates import (
    PatternCandidateNotConfirmedError,
    classify_replay_pattern_candidate,
    create_replay_pattern_candidates,
    evaluate_replay_pattern_candidate_backtest,
    register_replay_pattern_candidate,
)
from backend.app.strategies.pattern_candidate_backtest import (
    PatternCandidateBacktestUnsupportedError,
)
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateConflictError,
    PatternCandidateListPosition,
    PatternCandidateNotFoundError,
    PatternCandidateOwnershipError,
    archive_pattern_candidate,
    get_pattern_candidate,
    list_pattern_candidates,
)
from backend.app.database.pattern_candidate_backtest_repository import (
    PatternCandidateBacktestNotFoundError,
    get_latest_pattern_candidate_backtest,
)
from backend.app.database.analysis_job_repository import (
    AnalysisJobConflictError,
    AnalysisJobNotFoundError,
    AnalysisJobOwnershipError,
    AnalysisJobQueueFullError,
    enqueue_job,
    get_job,
    queue_metrics,
    request_cancel,
)
from backend.app.workers.analysis_job_worker import drain_queue
from backend.app.replay.cursor import (
    InvalidReplayCursorError,
    decode_replay_session_cursor,
    encode_replay_session_cursor,
    decode_replay_event_cursor,
    encode_replay_event_cursor,
    decode_pattern_candidate_cursor,
    encode_pattern_candidate_cursor,
)
from backend.app.database.tick_replay_repository import TickPosition, read_tick_page


APP_VERSION = "0.3.0"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    verify_database_writable()
    yield


app = FastAPI(
    title="ESAS Platform Backend",
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.get("/api/v2/research/pattern-hypotheses")
def pattern_hypothesis_registry(
    _: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    return {
        "data": get_pattern_hypothesis_registry(),
        "meta": {"api_version": "2"},
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    try:
        verify_database_writable()
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not writable",
        ) from error

    return {
        "status": "ok",
        "service": "esas-platform-backend",
        "version": APP_VERSION,
    }


@app.post("/events/ticks", status_code=status.HTTP_202_ACCEPTED)
def receive_tick(
    event: TickReceivedEvent,
    _: None = Depends(require_bridge_key),
) -> dict[str, str]:
    try:
        was_inserted = save_tick_event(event)
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tick storage is unavailable",
        ) from error

    return {
        "status": "stored" if was_inserted else "duplicate",
        "event_id": event.event_id,
        "event_type": event.event_type,
    }


@app.post("/auth/login")
def login(
    credentials: LoginRequest,
    request: Request,
) -> dict[str, object]:
    client_key = request.client.host if request.client else "unknown"
    return create_session(credentials, client_key)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: None = Depends(revoke_dashboard_session)) -> None:
    return None


@app.post("/status/bridge", status_code=status.HTTP_202_ACCEPTED)
def receive_bridge_status(
    report: BridgeStatusReport,
    _: None = Depends(require_bridge_key),
) -> dict[str, object]:
    stored_report = save_bridge_status(report)

    return {
        "status": "accepted",
        "source": stored_report["source"],
        "symbol": stored_report["symbol"],
        "reported_at": stored_report["reported_at"],
    }


@app.post("/status/loss/acknowledge")
def acknowledge_data_loss(
    request: LossAcknowledgementRequest,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    report = get_bridge_status(request.source, request.symbol)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bridge report was not found",
        )

    rejected_events = int(report["rejected_events"])
    if rejected_events <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no data loss to acknowledge",
        )

    acknowledgement = acknowledge_loss(
        source=request.source,
        symbol=request.symbol,
        rejected_events=rejected_events,
        acknowledged_by=user_code,
    )
    return {
        "status": "acknowledged",
        **acknowledgement,
    }


@app.get("/statistics/ticks")
def tick_statistics(
    _: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    return get_tick_statistics()

@app.get("/status/operational")
def operational_status(
    _: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    return get_operational_status()


@app.get("/internal/replay/{session_id}/quality-report")
def replay_quality_report(
    session_id: str,
    _: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        return asdict(create_replay_quality_report(session_id=session_id))
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    except ReplayTransitionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Replay session is not completed",
        ) from error


@app.get("/api/v2/replay-sessions/{session_id}/quality-report")
def public_replay_quality_report(
    session_id: str,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    if session.created_by != user_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Replay session belongs to another user",
        )
    try:
        report = create_replay_quality_report(session_id=session_id)
    except ReplayTransitionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Replay session is not completed",
        ) from error
    return {
        "data": asdict(report),
        "meta": {"api_version": "2"},
    }


@app.get("/api/v2/replay-sessions/{session_id}/technical-analysis")
def replay_technical_analysis(
    session_id: str,
    timeframe: str = Query(default="M1", pattern="^(M1|M5|M15|H1)$"),
    ema_period: int = Query(default=20, ge=2, le=500),
    rsi_period: int = Query(default=14, ge=2, le=500),
    atr_period: int = Query(default=14, ge=2, le=500),
    bar_limit: int = Query(default=500, ge=1, le=5_000),
    pivot_left: int = Query(default=2, ge=1, le=20),
    pivot_right: int = Query(default=2, ge=1, le=20),
    equality_tolerance_bps: float = Query(default=0.0, ge=0, le=100),
    liquidity_pool_tolerance_bps: float = Query(default=10.0, ge=0, le=500),
    liquidity_minimum_touches: int = Query(default=2, ge=2, le=20),
    liquidity_minimum_sweep_bps: float = Query(default=1.0, ge=0, le=500),
    liquidity_maximum_pool_age_bars: int = Query(default=250, ge=1, le=5_000),
    bos_choch_minimum_close_break_bps: float = Query(default=1.0, ge=0, le=500),
    bos_choch_maximum_pivot_age_bars: int = Query(default=250, ge=1, le=5_000),
    retest_touch_tolerance_bps: float = Query(default=5.0, ge=0, le=500),
    retest_confirmation_close_bps: float = Query(default=0.0, ge=0, le=500),
    retest_invalidation_close_bps: float = Query(default=10.0, ge=0, le=500),
    retest_maximum_age_bars: int = Query(default=100, ge=1, le=5_000),
    fvg_minimum_gap_bps: float = Query(default=1.0, ge=0, le=500),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    if session.created_by != user_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Replay session belongs to another user",
        )
    try:
        analysis = create_replay_technical_analysis(
            session=session,
            timeframe=timeframe,
            ema_period=ema_period,
            rsi_period=rsi_period,
            atr_period=atr_period,
            bar_limit=bar_limit,
            pivot_left=pivot_left,
            pivot_right=pivot_right,
            equality_tolerance_bps=equality_tolerance_bps,
            liquidity_pool_tolerance_bps=liquidity_pool_tolerance_bps,
            liquidity_minimum_touches=liquidity_minimum_touches,
            liquidity_minimum_sweep_bps=liquidity_minimum_sweep_bps,
            liquidity_maximum_pool_age_bars=liquidity_maximum_pool_age_bars,
              bos_choch_minimum_close_break_bps=bos_choch_minimum_close_break_bps,
              bos_choch_maximum_pivot_age_bars=bos_choch_maximum_pivot_age_bars,
              retest_touch_tolerance_bps=retest_touch_tolerance_bps,
              retest_confirmation_close_bps=retest_confirmation_close_bps,
              retest_invalidation_close_bps=retest_invalidation_close_bps,
              retest_maximum_age_bars=retest_maximum_age_bars,
              fvg_minimum_gap_bps=fvg_minimum_gap_bps,
          )
    except ReplayTransitionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Replay session is not completed",
        ) from error
    except ReplayDatasetChangedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Replay dataset no longer matches the session snapshot",
        ) from error
    return {"data": asdict(analysis), "meta": {"api_version": "2"}}


@app.get("/api/v2/replay-sessions/{session_id}/strategy-analysis")
def replay_strategy_analysis(
    session_id: str,
    timeframe: str = Query(default="M5", pattern="^(M1|M5|M15|H1)$"),
    ema_period: int = Query(default=20, ge=2, le=500),
    rsi_period: int = Query(default=14, ge=2, le=500),
    rsi_low: float = Query(default=30, ge=0, le=100),
    rsi_high: float = Query(default=70, ge=0, le=100),
    bar_limit: int = Query(default=500, ge=1, le=5_000),
    outcome_horizon: int = Query(default=3, ge=1, le=100),
    development_ratio: float = Query(default=0.7, ge=0.5, le=0.9),
    walk_forward_windows: int = Query(default=3, ge=2, le=8),
    cost_spread_bps: float = Query(default=2.0, ge=0, le=1_000),
    cost_commission_bps: float = Query(default=1.0, ge=0, le=1_000),
    cost_slippage_bps: float = Query(default=1.0, ge=0, le=1_000),
    cost_latency_bps: float = Query(default=0.5, ge=0, le=1_000),
    adverse_cost_multiplier: float = Query(default=1.5, ge=1, le=10),
    stress_cost_multiplier: float = Query(default=2.5, ge=1, le=10),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Replay session was not found") from error
    if session.created_by != user_code:
        raise HTTPException(status_code=403, detail="Replay session belongs to another user")
    try:
        analysis = create_replay_strategy_analysis(
            session=session, timeframe=timeframe, ema_period=ema_period,
            rsi_period=rsi_period, rsi_low=rsi_low, rsi_high=rsi_high,
            bar_limit=bar_limit, outcome_horizon=outcome_horizon,
            development_ratio=development_ratio,
            walk_forward_windows=walk_forward_windows,
            cost_spread_bps=cost_spread_bps,
            cost_commission_bps=cost_commission_bps,
            cost_slippage_bps=cost_slippage_bps,
            cost_latency_bps=cost_latency_bps,
            adverse_cost_multiplier=adverse_cost_multiplier,
            stress_cost_multiplier=stress_cost_multiplier,
        )
    except ReplayTransitionConflictError as error:
        raise HTTPException(status_code=409, detail="Replay session is not completed") from error
    except ReplayDatasetChangedError as error:
        raise HTTPException(
            status_code=409,
            detail="Replay dataset no longer matches the session snapshot",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"data": asdict(analysis), "meta": {"api_version": "2"}}


@app.get("/api/v2/replay-sessions/{session_id}/pattern-candidates")
def replay_pattern_candidates(
    session_id: str,
    timeframe: str = Query(default="M5", pattern="^(M1|M5|M15|H1)$"),
    bar_limit: int = Query(default=500, ge=1, le=5_000),
    pivot_left: int = Query(default=2, ge=1, le=50),
    pivot_right: int = Query(default=2, ge=1, le=50),
    equality_tolerance_bps: float = Query(default=0.0, ge=0, le=500),
    liquidity_pool_tolerance_bps: float = Query(default=10.0, ge=0, le=500),
    liquidity_minimum_touches: int = Query(default=2, ge=2, le=20),
    liquidity_minimum_sweep_bps: float = Query(default=1.0, ge=0, le=500),
    liquidity_maximum_pool_age_bars: int = Query(default=250, ge=1, le=5_000),
    bos_choch_minimum_close_break_bps: float = Query(default=1.0, ge=0, le=500),
    bos_choch_maximum_pivot_age_bars: int = Query(default=250, ge=1, le=5_000),
    retest_touch_tolerance_bps: float = Query(default=5.0, ge=0, le=500),
    retest_confirmation_close_bps: float = Query(default=0.0, ge=0, le=500),
    retest_invalidation_close_bps: float = Query(default=10.0, ge=0, le=500),
    retest_maximum_age_bars: int = Query(default=100, ge=1, le=5_000),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Replay session was not found") from error
    if session.created_by != user_code:
        raise HTTPException(status_code=403, detail="Replay session belongs to another user")
    try:
        candidates = create_replay_pattern_candidates(
            session=session, timeframe=timeframe, bar_limit=bar_limit,
            pivot_left=pivot_left, pivot_right=pivot_right,
            equality_tolerance_bps=equality_tolerance_bps,
            liquidity_pool_tolerance_bps=liquidity_pool_tolerance_bps,
            liquidity_minimum_touches=liquidity_minimum_touches,
            liquidity_minimum_sweep_bps=liquidity_minimum_sweep_bps,
            liquidity_maximum_pool_age_bars=liquidity_maximum_pool_age_bars,
            bos_choch_minimum_close_break_bps=bos_choch_minimum_close_break_bps,
            bos_choch_maximum_pivot_age_bars=bos_choch_maximum_pivot_age_bars,
            retest_touch_tolerance_bps=retest_touch_tolerance_bps,
            retest_confirmation_close_bps=retest_confirmation_close_bps,
            retest_invalidation_close_bps=retest_invalidation_close_bps,
            retest_maximum_age_bars=retest_maximum_age_bars,
        )
    except ReplayTransitionConflictError as error:
        raise HTTPException(status_code=409, detail="Replay session is not completed") from error
    except ReplayDatasetChangedError as error:
        raise HTTPException(
            status_code=409,
            detail="Replay dataset no longer matches the session snapshot",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"data": asdict(candidates), "meta": {"api_version": "2"}}


@app.post(
    "/api/v2/pattern-candidates",
    status_code=status.HTTP_201_CREATED,
)
def register_pattern_candidate_endpoint(
    register_request: PatternCandidateRegisterRequest,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(register_request.session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Replay session was not found") from error
    if session.created_by != user_code:
        raise HTTPException(status_code=403, detail="Replay session belongs to another user")
    try:
        candidate = register_replay_pattern_candidate(
            session=session, hypothesis_id=register_request.hypothesis_id,
            actor=user_code, actor_role="operator",
            timeframe=register_request.timeframe, bar_limit=register_request.bar_limit,
            pivot_left=register_request.pivot_left, pivot_right=register_request.pivot_right,
            equality_tolerance_bps=register_request.equality_tolerance_bps,
            liquidity_pool_tolerance_bps=register_request.liquidity_pool_tolerance_bps,
            liquidity_minimum_touches=register_request.liquidity_minimum_touches,
            liquidity_minimum_sweep_bps=register_request.liquidity_minimum_sweep_bps,
            liquidity_maximum_pool_age_bars=register_request.liquidity_maximum_pool_age_bars,
            bos_choch_minimum_close_break_bps=register_request.bos_choch_minimum_close_break_bps,
            bos_choch_maximum_pivot_age_bars=register_request.bos_choch_maximum_pivot_age_bars,
            retest_touch_tolerance_bps=register_request.retest_touch_tolerance_bps,
            retest_confirmation_close_bps=register_request.retest_confirmation_close_bps,
            retest_invalidation_close_bps=register_request.retest_invalidation_close_bps,
            retest_maximum_age_bars=register_request.retest_maximum_age_bars,
        )
    except ReplayTransitionConflictError as error:
        raise HTTPException(status_code=409, detail="Replay session is not completed") from error
    except ReplayDatasetChangedError as error:
        raise HTTPException(
            status_code=409,
            detail="Replay dataset no longer matches the session snapshot",
        ) from error
    except PatternCandidateNotConfirmedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PatternCandidateOwnershipError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pattern candidate storage is unavailable",
        ) from error
    return {"data": asdict(candidate), "meta": {"api_version": "2"}}


@app.get("/api/v2/pattern-candidates")
def pattern_candidates_list(
    cursor: str | None = None,
    page_size: int = Query(default=50, ge=1, le=200),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    position = None
    if cursor is not None:
        try:
            created_at, candidate_id = decode_pattern_candidate_cursor(
                cursor, subject=user_code,
            )
            position = PatternCandidateListPosition(created_at, candidate_id)
        except InvalidReplayCursorError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pattern candidate cursor is invalid or expired",
            ) from error

    page = list_pattern_candidates(owner=user_code, page_size=page_size, after=position)
    next_cursor = None
    if page.next_position is not None:
        next_cursor = encode_pattern_candidate_cursor(
            created_at=page.next_position.created_at,
            candidate_id=page.next_position.candidate_id,
            subject=user_code,
        )
    return {
        "data": [asdict(item) for item in page.items],
        "page": {
            "limit": page_size,
            "next_cursor": next_cursor,
            "has_more": page.next_position is not None,
        },
        "meta": {"api_version": "2"},
    }


@app.get("/api/v2/pattern-candidates/{candidate_id}")
def pattern_candidate_detail(
    candidate_id: str,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        candidate = get_pattern_candidate(candidate_id)
    except PatternCandidateNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate was not found") from error
    if candidate.created_by != user_code:
        raise HTTPException(status_code=403, detail="Pattern candidate belongs to another user")
    return {"data": asdict(candidate), "meta": {"api_version": "2"}}


@app.post("/api/v2/pattern-candidates/{candidate_id}/archive")
def pattern_candidate_archive(
    candidate_id: str,
    archive_request: PatternCandidateArchiveRequest,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        candidate = archive_pattern_candidate(
            candidate_id=candidate_id, actor=user_code, actor_role="operator",
            expected_state_version=archive_request.expected_state_version,
        )
    except PatternCandidateNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate was not found") from error
    except PatternCandidateOwnershipError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except PatternCandidateConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"data": asdict(candidate), "meta": {"api_version": "2"}}


@app.post("/api/v2/pattern-candidates/{candidate_id}/backtest")
def pattern_candidate_backtest_endpoint(
    candidate_id: str,
    backtest_request: PatternCandidateBacktestRequest,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        backtest = evaluate_replay_pattern_candidate_backtest(
            candidate_id=candidate_id, actor=user_code, actor_role="operator",
            horizon_bars=backtest_request.horizon_bars, spread_bps=backtest_request.spread_bps,
            commission_bps=backtest_request.commission_bps, slippage_bps=backtest_request.slippage_bps,
            latency_bps=backtest_request.latency_bps,
            adverse_multiplier=backtest_request.adverse_multiplier,
            stress_multiplier=backtest_request.stress_multiplier,
        )
    except PatternCandidateNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate was not found") from error
    except PatternCandidateOwnershipError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except PatternCandidateBacktestUnsupportedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PatternCandidateConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ReplayTransitionConflictError as error:
        raise HTTPException(status_code=409, detail="Replay session is not completed") from error
    except ReplayDatasetChangedError as error:
        raise HTTPException(
            status_code=409,
            detail="Replay dataset no longer matches the session snapshot",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"data": asdict(backtest), "meta": {"api_version": "2"}}


@app.get("/api/v2/pattern-candidates/{candidate_id}/backtest")
def pattern_candidate_backtest_detail(
    candidate_id: str,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        candidate = get_pattern_candidate(candidate_id)
    except PatternCandidateNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate was not found") from error
    if candidate.created_by != user_code:
        raise HTTPException(status_code=403, detail="Pattern candidate belongs to another user")
    try:
        backtest = get_latest_pattern_candidate_backtest(candidate_id)
    except PatternCandidateBacktestNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate has no backtest yet") from error
    return {"data": asdict(backtest), "meta": {"api_version": "2"}}


@app.post("/api/v2/pattern-candidates/{candidate_id}/classify")
def pattern_candidate_classify(
    candidate_id: str,
    classify_request: PatternCandidateClassifyRequest,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        candidate = classify_replay_pattern_candidate(
            candidate_id=candidate_id, actor=user_code, actor_role="operator",
            expected_state_version=classify_request.expected_state_version,
        )
    except PatternCandidateNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate was not found") from error
    except PatternCandidateOwnershipError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except PatternCandidateBacktestNotFoundError as error:
        raise HTTPException(status_code=409, detail="Pattern candidate has no backtest yet") from error
    except PatternCandidateConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"data": asdict(candidate), "meta": {"api_version": "2"}}


@app.post("/api/v2/pattern-candidates/{candidate_id}/backtest-jobs", status_code=202)
def pattern_candidate_backtest_job_create(
    candidate_id: str,
    job_request: PatternCandidateBacktestJobRequest,
    background_tasks: BackgroundTasks,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        candidate = get_pattern_candidate(candidate_id)
    except PatternCandidateNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pattern candidate was not found") from error
    if candidate.created_by != user_code:
        raise HTTPException(status_code=403, detail="Pattern candidate belongs to another user")
    try:
        job = enqueue_job(
            job_type="pattern_candidate_backtest", created_by=user_code,
            payload={
                "candidate_id": candidate_id, "horizon_bars": job_request.horizon_bars,
                "spread_bps": job_request.spread_bps, "commission_bps": job_request.commission_bps,
                "slippage_bps": job_request.slippage_bps, "latency_bps": job_request.latency_bps,
                "adverse_multiplier": job_request.adverse_multiplier,
                "stress_multiplier": job_request.stress_multiplier,
            },
            related_resource_id=candidate_id, idempotency_key=job_request.idempotency_key,
            priority=job_request.priority,
        )
    except AnalysisJobOwnershipError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except AnalysisJobQueueFullError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    background_tasks.add_task(drain_queue, worker_id=f"bg-{job.job_id}", job_type="pattern_candidate_backtest")
    return {"data": asdict(job), "meta": {"api_version": "2"}}


@app.get("/api/v2/pattern-candidates/{candidate_id}/backtest-jobs/{job_id}")
def pattern_candidate_backtest_job_detail(
    candidate_id: str,
    job_id: str,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        job = get_job(job_id)
    except AnalysisJobNotFoundError as error:
        raise HTTPException(status_code=404, detail="Analysis job was not found") from error
    if job.related_resource_id != candidate_id:
        raise HTTPException(status_code=404, detail="Analysis job was not found")
    if job.created_by != user_code:
        raise HTTPException(status_code=403, detail="Analysis job belongs to another user")
    return {"data": asdict(job), "meta": {"api_version": "2"}}


@app.post("/api/v2/pattern-candidates/{candidate_id}/backtest-jobs/{job_id}/cancel")
def pattern_candidate_backtest_job_cancel(
    candidate_id: str,
    job_id: str,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        job = get_job(job_id)
    except AnalysisJobNotFoundError as error:
        raise HTTPException(status_code=404, detail="Analysis job was not found") from error
    if job.related_resource_id != candidate_id:
        raise HTTPException(status_code=404, detail="Analysis job was not found")
    try:
        cancelled = request_cancel(job_id=job_id, actor=user_code)
    except AnalysisJobOwnershipError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except AnalysisJobConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"data": asdict(cancelled), "meta": {"api_version": "2"}}


@app.get("/api/v2/analysis-jobs/metrics")
def analysis_jobs_metrics(
    _: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    return {"data": queue_metrics("pattern_candidate_backtest"), "meta": {"api_version": "2"}}


@app.get("/api/v2/replay-sessions")
def replay_sessions(
    cursor: str | None = None,
    page_size: int = Query(default=50, ge=1, le=200),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    position = None
    if cursor is not None:
        try:
            created_at, session_id = decode_replay_session_cursor(
                cursor,
                subject=user_code,
            )
            position = ReplaySessionListPosition(created_at, session_id)
        except InvalidReplayCursorError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Replay cursor is invalid or expired",
            ) from error

    page = list_replay_sessions(page_size=page_size, after=position, owner=user_code)
    next_cursor = None
    if page.next_position is not None:
        next_cursor = encode_replay_session_cursor(
            created_at=page.next_position.created_at,
            session_id=page.next_position.session_id,
            subject=user_code,
        )
    return {
        "data": [asdict(session) for session in page.items],
        "page": {
            "limit": page_size,
            "next_cursor": next_cursor,
            "has_more": page.next_position is not None,
        },
        "meta": {"api_version": "2"},
    }


@app.post(
    "/api/v2/replay-sessions",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_replay_session_endpoint(
    replay_request: ReplaySessionCreateRequest,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = create_replay_session(
            created_by=user_code,
            actor_role="operator",
            symbol=replay_request.symbol,
            start_at=replay_request.start_at,
            end_at=replay_request.end_at,
            mode=replay_request.mode,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Replay session request is invalid",
        ) from error
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Replay session storage is unavailable",
        ) from error

    return {
        "data": asdict(session),
        "meta": {"api_version": "2"},
    }


@app.post("/api/v2/replay-sessions/{session_id}/commands")
def replay_session_command(
    session_id: str,
    command_request: ReplayCommandRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        result = execute_replay_command(
            session_id=session_id,
            actor=user_code,
            actor_role="operator",
            idempotency_key=idempotency_key,
            command=command_request.command,
            expected_state_version=command_request.expected_state_version,
            requested_ticks=command_request.requested_ticks,
        )
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    except ReplayOwnershipError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Replay session belongs to another user",
        ) from error
    except ReplayTransitionConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Replay command conflicts with current session state",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Replay command request is invalid",
        ) from error
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Replay command could not be stored",
        ) from error

    return {
        "data": asdict(result),
        "meta": {"api_version": "2"},
    }


@app.get("/api/v2/replay-sessions/{session_id}")
def replay_session_detail(
    session_id: str,
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    if session.created_by != user_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Replay session belongs to another user",
        )
    return {
        "data": asdict(session),
        "meta": {"api_version": "2"},
    }


@app.get("/api/v2/replay-sessions/{session_id}/events")
def replay_session_events(
    session_id: str,
    cursor: str | None = None,
    page_size: int = Query(default=250, ge=1, le=1000),
    user_code: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    if session.created_by != user_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Replay session belongs to another user",
        )

    after = None
    if cursor is not None:
        try:
            timestamp, event_id = decode_replay_event_cursor(
                cursor,
                session_id=session_id,
                subject=user_code,
            )
            after = TickPosition(datetime.fromisoformat(timestamp), event_id)
        except (InvalidReplayCursorError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Replay event cursor is invalid or expired",
            ) from error

    page = read_tick_page(
        symbol=session.symbol,
        start_at=datetime.fromisoformat(session.start_at),
        end_at=datetime.fromisoformat(session.end_at),
        page_size=page_size,
        after=after,
        through=session.last_position,
    )
    next_cursor = None
    if page.next_position is not None:
        next_cursor = encode_replay_event_cursor(
            session_id=session_id,
            event_timestamp=page.next_position.event_timestamp.isoformat(
                timespec="microseconds"
            ),
            event_id=page.next_position.event_id,
            subject=user_code,
        )
    return {
        "data": [asdict(item) for item in page.items],
        "page": {
            "limit": page_size,
            "next_cursor": next_cursor,
            "has_more": page.has_more,
        },
        "snapshot": {
            "dataset_tick_count": session.dataset_tick_count,
            "dataset_fingerprint": session.dataset_fingerprint,
            "last_position": asdict(session.last_position)
            if session.last_position is not None
            else None,
        },
        "meta": {"api_version": "2"},
    }
