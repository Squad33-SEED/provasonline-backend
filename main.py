from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.database import connect, disconnect
from src.routers.auth import limiter as auth_limiter
from src.routers.auth import router as auth_router
from src.routers.usuarios import router as usuarios_router


def rate_limit_exceeded_handler(request, exc: RateLimitExceeded):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Muitas tentativas de login. Aguarde 15 minutos antes de tentar novamente.",
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await connect()
    yield
    await disconnect()


app = FastAPI(
    title="Seed Backend — Residência de Software II",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = auth_limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(usuarios_router)


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {"status": "ok"}