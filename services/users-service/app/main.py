from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(
    title="Azref users service",
    version=settings.service_version,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
    }
