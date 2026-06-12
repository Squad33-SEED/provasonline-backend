from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from prisma import Json

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


_ALTERNATIVAS = [
    {"letra": "A", "texto": "Alternativa A"},
    {"letra": "B", "texto": "Alternativa B"},
    {"letra": "C", "texto": "Alternativa C"},
    {"letra": "D", "texto": "Alternativa D"},
]


@pytest_asyncio.fixture
async def etapa_com_resultado(conexao_db):
    u = await db.usuario.find_unique(where={"cpf": "11122233396"})
    aluno = await db.aluno.find_unique(where={"usuarioId": u.id})
    componente = await db.componentecurricular.find_first(where={"ativo": True})
    professor = await db.professor.find_first()
    agora = _agora()

    simulado = await db.simulado.create(
        data={
            "titulo": "Etapa Relatorio TESTE",
            "componente": {"connect": {"id": componente.id}},
            "professor": {"connect": {"id": professor.id}},
            "qtdFacil": 0, "qtdMedio": 0, "qtdDificil": 0,
            "vagas": 5, "duracaoMinutos": 30,
            "janelaInicio": agora - timedelta(hours=1),
            "janelaFim": agora + timedelta(hours=2),
            "status": "PUBLICADO",
            "embaralharAlternativas": False,
        }
    )
    resultado = await db.resultadoaluno.create(
        data={
            "simulado": {"connect": {"id": simulado.id}},
            "aluno": {"connect": {"id": aluno.id}},
            "statusResultado": "FINALIZADO",
            "pontuacao": 5.0,
            "iniciadoEm": agora,
            "finalizadoEm": agora,
        }
    )
    await db.tentativaquestao.create(
        data={
            "resultado": {"connect": {"id": resultado.id}},
            "questaoId": "mock-rel-1",
            "enunciado": "Questao relatorio 1",
            "alternativas": Json(_ALTERNATIVAS),
            "respostaCorreta": "A",
            "ordem": 1,
            "alternativaMarcada": "A",
        }
    )
    await db.tentativaquestao.create(
        data={
            "resultado": {"connect": {"id": resultado.id}},
            "questaoId": "mock-rel-2",
            "enunciado": "Questao relatorio 2",
            "alternativas": Json(_ALTERNATIVAS),
            "respostaCorreta": "A",
            "ordem": 2,
            "alternativaMarcada": "B",
        }
    )

    yield simulado.id

    await db.tentativaquestao.delete_many(where={"resultadoId": resultado.id})
    await db.resultadoaluno.delete(where={"id": resultado.id})
    await db.simulado.delete(where={"id": simulado.id})


@pytest.mark.asyncio
async def test_relatorio_etapa_admin(client, token_admin, auth, etapa_com_resultado):
    r = await client.get(
        f"/simulados/{etapa_com_resultado}/relatorio", headers=auth(token_admin)
    )
    assert r.status_code == 200
    d = r.json()
    assert d["totalAlunos"] >= 1
    assert d["finalizados"] >= 1

    item = next((i for i in d["itens"] if i["acertos"] is not None), None)
    assert item is not None
    assert item["total"] == 2
    assert item["acertos"] == 1


@pytest.mark.asyncio
async def test_relatorio_etapa_requer_admin(client, token_aluno, auth, etapa_com_resultado):
    r = await client.get(
        f"/simulados/{etapa_com_resultado}/relatorio", headers=auth(token_aluno)
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_relatorio_etapa_inexistente_404(client, token_admin, auth):
    r = await client.get("/simulados/nao-existe-123/relatorio", headers=auth(token_admin))
    assert r.status_code == 404
