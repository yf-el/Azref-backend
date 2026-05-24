from fastapi import FastAPI, CORSMiddleware

from app.config import settings

app = FastAPI(
    title="Azref auth-backend",
    version=settings.service_version,
)
cors = settings.cors

if cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors.allow_origins,
        allow_methods=cors.allow_methods,
        allow_headers=cors.allow_headers,
        allow_credentials=cors.allow_credentials,
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
