from fastapi import FastAPI, status

from backend.app.models.tick_event import TickReceivedEvent

APP_VERSION = "0.1.0"

app = FastAPI(
    title="ESAS Platform Backend",
    version=APP_VERSION,
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
    return {
        "status": "accepted",
        "event_id": event.event_id,
        "event_type": event.event_type,
    }