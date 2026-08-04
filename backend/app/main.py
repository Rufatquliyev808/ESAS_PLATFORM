from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import sqlite3
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
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
from backend.app.quality.report import create_replay_quality_report
from backend.app.replay.cursor import (
    InvalidReplayCursorError,
    decode_replay_session_cursor,
    encode_replay_session_cursor,
)


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

    page = list_replay_sessions(page_size=page_size, after=position)
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


@app.get("/api/v2/replay-sessions/{session_id}")
def replay_session_detail(
    session_id: str,
    _: str = Depends(require_dashboard_session),
) -> dict[str, object]:
    try:
        session = get_replay_session(session_id)
    except ReplaySessionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Replay session was not found",
        ) from error
    return {
        "data": asdict(session),
        "meta": {"api_version": "2"},
    }
