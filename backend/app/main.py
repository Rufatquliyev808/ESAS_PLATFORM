from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database.tick_repository import save_tick_event
from backend.app.database.tick_statistics import get_tick_statistics
from backend.app.database.operational_status import get_operational_status
from backend.app.operational.bridge_status import save_bridge_status

from backend.app.database.connection import (
    initialize_database,
    verify_database_writable,
)
from backend.app.models.tick_event import TickReceivedEvent
from backend.app.models.bridge_status import BridgeStatusReport
from backend.app.auth import LoginRequest, create_session, require_dashboard_session


APP_VERSION = "0.2.0"


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
def receive_tick(event: TickReceivedEvent) -> dict[str, str]:
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
def login(credentials: LoginRequest) -> dict[str, object]:
    return create_session(credentials)


@app.post("/status/bridge", status_code=status.HTTP_202_ACCEPTED)
def receive_bridge_status(report: BridgeStatusReport) -> dict[str, object]:
    stored_report = save_bridge_status(report)

    return {
        "status": "accepted",
        "source": stored_report["source"],
        "symbol": stored_report["symbol"],
        "reported_at": stored_report["reported_at"],
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
