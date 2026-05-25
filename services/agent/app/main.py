import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cache_semantic import close_redis, get_redis

from app.api.routes import router
from app.config import settings
from app.db.client import close_pool, get_pool

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

ALLOWED_ORIGINS = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    logging.info("Database pool initialized")
    get_redis()
    logging.info("Redis client initialized")
    yield
    await close_redis()
    logging.info("Redis client closed")
    await close_pool()
    logging.info("Database pool closed")


app = FastAPI(
    title="Azref agent service",
    description="AI agent for Moroccan law — answers legal questions with citations.",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

if settings.is_production:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
else:
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


app.include_router(router)
