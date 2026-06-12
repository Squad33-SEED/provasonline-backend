import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app
from src.database import db
from src.routers.auth import limiter
from src.services import questions_api


def _mock_bank() -> dict[str, list[dict]]:
    bank: dict[str, list[dict]] = {}
    for dif in ("FACIL", "MEDIO", "DIFICIL"):
        itens = []
        for i in range(10):
            itens.append({
                "id": f"mock-{dif}-{i}",
                "title": f"Questao mock {dif} {i}",
                "correctAnswer": "Alternativa correta",
                "incorrectAnswers": [
                    "Errada 1", "Errada 2", "Errada 3", "Errada 4",
                ],
                "difficulty": questions_api.DIFICULDADE_PROVAS_PARA_API[dif],
                "imageUrl": None,
                "topic": {
                    "name": "Topico Mock",
                    "slug": "topico-mock",
                    "subject": {"name": "Materia Mock", "slug": "materia-mock"},
                },
            })
        bank[dif] = itens
    return bank


MOCK_BANK = _mock_bank()
MOCK_IDS = {dif: [q["id"] for q in itens] for dif, itens in MOCK_BANK.items()}


@pytest.fixture(autouse=True)
def mock_questions_api(monkeypatch):
    async def fake_listar(subject_slug, dificuldade):
        return [dict(q) for q in MOCK_BANK[dificuldade]]

    async def fake_contar(subject_slug, dificuldade):
        return len(MOCK_BANK[dificuldade])

    async def fake_por_ids(subject_slug, ids):
        desejados = set(ids)
        out = []
        for itens in MOCK_BANK.values():
            for q in itens:
                if q["id"] in desejados:
                    out.append(dict(q))
        return out

    monkeypatch.setattr(questions_api, "listar_questoes", fake_listar)
    monkeypatch.setattr(questions_api, "contar_questoes", fake_contar)
    monkeypatch.setattr(questions_api, "buscar_questoes_por_ids", fake_por_ids)
    yield


@pytest_asyncio.fixture(autouse=True)
async def garantir_subject_slug(conexao_db):
    await db.componentecurricular.update_many(
        where={"questionsSubjectSlug": None},
        data={"questionsSubjectSlug": "materia-mock"},
    )
    yield


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


@pytest_asyncio.fixture
async def token_admin(conexao_db):
    return await _login("ADMIN")


@pytest_asyncio.fixture
async def token_professor(conexao_db):
    return await _login("PROFESSOR")


@pytest_asyncio.fixture
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
