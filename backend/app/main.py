from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status

from backend.app.database.tick_repository import save_tick_event
from backend.app.database.tick_statistics import get_tick_statistics
from backend.app.database.operational_status import get_operational_status
from backend.app.operational.bridge_status import save_bridge_status

from backend.app.database.connection import initialize_database
from backend.app.models.tick_event import TickReceivedEvent
from backend.app.models.bridge_status import BridgeStatusReport


APP_VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(
    title="ESAS Platform Backend",
    version=APP_VERSION,
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "esas-platform-backend",
        "version": APP_VERSION,
    }


@app.post("/events/ticks", status_code=status.HTTP_202_ACCEPTED)
def receive_tick(event: TickReceivedEvent) -> dict[str, str]:
    was_inserted = save_tick_event(event)

    return {
        "status": "stored" if was_inserted else "duplicate",
        "event_id": event.event_id,
        "event_type": event.event_type,
    }


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
def tick_statistics() -> dict[str, object]:
    return get_tick_statistics()

@app.get("/status/operational")
def operational_status() -> dict[str, object]:
    return get_operational_status()
