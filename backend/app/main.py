from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Request, status
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
from backend.app.auth import (
    LoginRequest,
    create_session,
    require_bridge_key,
    require_dashboard_session,
    revoke_dashboard_session,
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
