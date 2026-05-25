import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.kafka_client import close_producer, init_producer
from app.routers import me as me_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_producer()
    logging.info("Kafka producer initialized")
    yield
    await close_producer()
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
