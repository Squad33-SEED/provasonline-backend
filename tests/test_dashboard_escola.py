from datetime import datetime, timezone

import pytest
import pytest_asyncio

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def escola_com_desempenho(conexao_db):
    modalidade = await db.modalidade.find_first()
    agora = _agora()

    escola = await db.escola.create(
        data={
            "nome": "Escola Teste Desempenho ZZZ",
            "municipio": "Aracaju",
            "inep": "90000091",
        }
    )
    turma = await db.turma.create(
        data={
            "escola": {"connect": {"id": escola.id}},
            "modalidade": {"connect": {"id": modalidade.id}},
            "nome": "Turma Desempenho ZZZ",
            "anoLetivo": 2026,
        }
    )
    usuario = await db.usuario.create(
        data={
            "nome": "Aluno Desempenho ZZZ",
            "cpf": "10000000091",
            "senhaHash": "x",
            "tipo": "ALUNO",
        }
    )
    aluno = await db.aluno.create(
        data={
            "usuario": {"connect": {"id": usuario.id}},
            "dataNascimento": datetime(2005, 1, 1, tzinfo=timezone.utc),
        }
    )
    await db.turmaaluno.create(
        data={
            "turma": {"connect": {"id": turma.id}},
            "aluno": {"connect": {"id": aluno.id}},
            "entrouEm": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    )
    resultado = await db.resultadoaluno.create(
        data={
            "aluno": {"connect": {"id": aluno.id}},
            "statusResultado": "FINALIZADO",
            "pontuacao": 8.0,
            "finalizadoEm": agora,
        }
    )

    yield escola.nome

    await db.resultadoaluno.delete(where={"id": resultado.id})
    await db.turmaaluno.delete(
        where={"turmaId_alunoId": {"turmaId": turma.id, "alunoId": aluno.id}}
    )
    await db.aluno.delete(where={"id": aluno.id})
    await db.usuario.delete(where={"id": usuario.id})
    await db.turma.delete(where={"id": turma.id})
    await db.escola.delete(where={"id": escola.id})


@pytest.mark.asyncio
async def test_dashboard_desempenho_por_escola(client, token_admin, auth, escola_com_desempenho):
    r = await client.get("/simulados/dashboard", headers=auth(token_admin))
    assert r.status_code == 200

    desempenho = r.json()["desempenhoPorEscola"]
    item = next((i for i in desempenho if i["escola"] == escola_com_desempenho), None)
    assert item is not None
    assert item["media"] == 8.0
    assert item["alunos"] == 1


@pytest.mark.asyncio
async def test_dashboard_requer_admin(client, token_aluno, auth):
    r = await client.get("/simulados/dashboard", headers=auth(token_aluno))
    assert r.status_code == 403
