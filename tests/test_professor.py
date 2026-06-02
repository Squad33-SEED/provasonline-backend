import pytest
import pytest_asyncio
from prisma import Json

from src.database import db

ENDPOINTS = ["/professor/turmas", "/professor/questoes", "/professor/resultados"]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_professor_endpoints_bloqueiam_nao_professor(
    client, token_admin, token_aluno, auth, endpoint
):
    r_admin = await client.get(endpoint, headers=auth(token_admin))
    assert r_admin.status_code == 403

    r_aluno = await client.get(endpoint, headers=auth(token_aluno))
    assert r_aluno.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_professor_endpoints_respondem_lista(
    client, token_professor, auth, endpoint
):
    resp = await client.get(endpoint, headers=auth(token_professor))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest_asyncio.fixture
async def questao_de_outro_professor(conexao_db):
    assunto = await db.assunto.find_first()
    usuario = await db.usuario.create(
        data={
            "nome": "Professor Externo TESTE",
            "cpf": "90000000001",
            "senhaHash": "x",
            "tipo": "PROFESSOR",
            "ativo": True,
        }
    )
    professor = await db.professor.create(
        data={"usuario": {"connect": {"id": usuario.id}}}
    )
    questao = await db.questao.create(
        data={
            "professor": {"connect": {"id": professor.id}},
            "componente": {"connect": {"id": assunto.componenteId}},
            "assunto": {"connect": {"id": assunto.id}},
            "tipo": "MULTIPLA_ESCOLHA",
            "dificuldade": "FACIL",
            "enunciado": "Questao de outro professor TESTE",
            "alternativas": Json(
                [{"letra": "A", "texto": "1"}, {"letra": "B", "texto": "2"}]
            ),
            "respostaCorreta": "A",
        }
    )
    yield questao.id
    await db.questao.delete(where={"id": questao.id})
    await db.professor.delete(where={"id": professor.id})
    await db.usuario.delete(where={"id": usuario.id})


@pytest.mark.asyncio
async def test_professor_so_ve_proprias_questoes(
    client, token_professor, auth, questao_de_outro_professor
):
    resp = await client.get("/professor/questoes", headers=auth(token_professor))
    assert resp.status_code == 200
    ids = [q["id"] for q in resp.json()]
    assert questao_de_outro_professor not in ids
