import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kafka_events import producer as kafka_producer

from app.config import settings
from app.routers import me as me_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kafka producer is lazy-initialized on first publish — no init step here.
    # On shutdown we still flush pending sends and close the broker socket.
    yield
    await kafka_producer.stop()
    logging.info("Kafka producer closed")


app = FastAPI(
    title="Azref users service",
    version=settings.service_version,
    lifespan=lifespan,
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


app.include_router(me_router.router)
