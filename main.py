from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.database import connect, disconnect
from src.routers.alunos import router as alunos_router
from src.routers.auth import limiter as auth_limiter
from src.routers.auth import router as auth_router
from src.routers.catalogo import router as catalogo_router
from src.routers.simulados import router as simulados_router
from src.routers.simulado_livre import router as simulado_livre_router
from src.routers.turmas import router as turmas_router
from src.routers.usuarios import router as usuarios_router
from src.routers.aluno import router as aluno_router
from src.routers.violacoes import router as violacoes_router
from src.routers.professor import router as professor_router
from src.routers.professores import router as professores_router
from src.routers.certificados import router as certificados_router
from src.routers.ips import router as ips_router


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
    version="1.6.0",
    lifespan=lifespan,
)

app.state.limiter = auth_limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(usuarios_router)
app.include_router(turmas_router)
app.include_router(alunos_router)
app.include_router(catalogo_router)
app.include_router(simulados_router)
app.include_router(simulado_livre_router)
app.include_router(aluno_router)
app.include_router(violacoes_router)
app.include_router(professor_router)
app.include_router(professores_router)
app.include_router(certificados_router)
app.include_router(ips_router)


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {"status": "ok", "version": "1.6.0"}