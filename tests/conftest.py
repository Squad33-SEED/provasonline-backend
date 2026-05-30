import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app
from src.database import db
from src.routers.auth import limiter


CONTAS = {
    "ADMIN": {"cpf": "12345678909", "senha": "admin123"},
    "PROFESSOR": {"cpf": "98765432100", "senha": "admin123"},
    "ALUNO": {"cpf": "11122233396", "senha": "admin123"},
}


def _resetar_rate_limit():
    try:
        limiter.reset()
    except Exception:
        pass
    for attr in ("_storage", "storage"):
        store = getattr(limiter, attr, None)
        if store is not None:
            for metodo in ("reset", "clear", "flush"):
                fn = getattr(store, metodo, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass


@pytest_asyncio.fixture(scope="session")
async def conexao_db():
    if not db.is_connected():
        await db.connect()
    yield db
    if db.is_connected():
        await db.disconnect()


@pytest_asyncio.fixture
async def client(conexao_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(role: str) -> str:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json=CONTAS[role])
        assert resp.status_code == 200, f"login {role} falhou: {resp.text}"
        return resp.json()["access_token"]


@pytest_asyncio.fixture(scope="session")
async def token_admin(conexao_db):
    return await _login("ADMIN")


@pytest_asyncio.fixture(scope="session")
async def token_professor(conexao_db):
    return await _login("PROFESSOR")


@pytest_asyncio.fixture(scope="session")
async def token_aluno(conexao_db):
    return await _login("ALUNO")


@pytest.fixture
def auth():
    return lambda token: {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def limpar_rate_limit():
    _resetar_rate_limit()
    yield
    _resetar_rate_limit()
