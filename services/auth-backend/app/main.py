from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Azref auth-backend",
    version=settings.service_version,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
    }
