from fastapi import FastAPI

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