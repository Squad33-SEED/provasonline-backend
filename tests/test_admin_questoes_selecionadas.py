from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from prisma import Json

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


async def _selecao(qtd=3):
    questoes = await db.questao.find_many(where={"ativa": True})
    por_comp = defaultdict(list)
    for q in questoes:
        por_comp[q.componenteId].append(q.id)
    comp = max(por_comp, key=lambda c: len(por_comp[c]))
    return comp, por_comp[comp][:qtd]


@pytest.mark.asyncio
async def test_criar_prova_manual(client, token_admin, auth):
    comp, ids = await _selecao(3)
    agora = _agora()
    payload = {
        "titulo": "Prova Manual TESTE",
        "componenteId": comp,
        "qtdFacil": 0, "qtdMedio": 0, "qtdDificil": 0,
        "vagas": 30, "duracaoMinutos": 60,
        "janelaInicio": (agora + timedelta(minutes=10)).isoformat(),
        "janelaFim": (agora + timedelta(days=1)).isoformat(),
        "questaoIds": ids,
        "embaralharAlternativas": True,
    }
    r = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert r.status_code == 201, r.text
    assert r.json()["totalQuestoes"] == len(ids)
    await db.simulado.delete(where={"id": r.json()["id"]})


@pytest.mark.asyncio
async def test_criar_prova_manual_rejeita_questao_de_outro_componente(
    client, token_admin, auth
):
    comp, ids = await _selecao(2)
    outra = await db.questao.find_first(
        where={"componenteId": {"not": comp}, "ativa": True}
    )
    agora = _agora()
    payload = {
        "titulo": "Prova Manual Invalida TESTE",
        "componenteId": comp,
        "qtdFacil": 0, "qtdMedio": 0, "qtdDificil": 0,
        "vagas": 30, "duracaoMinutos": 60,
        "janelaInicio": (agora + timedelta(minutes=10)).isoformat(),
        "janelaFim": (agora + timedelta(days=1)).isoformat(),
        "questaoIds": ids + [outra.id],
        "embaralharAlternativas": True,
    }
    r = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert r.status_code == 422


@pytest_asyncio.fixture
async def simulado_manual(conexao_db):
    comp, ids = await _selecao(3)
    professor = await db.professor.find_first()
    agora = _agora()
    s = await db.simulado.create(
        data={
            "titulo": "Manual iniciar TESTE",
            "componente": {"connect": {"id": comp}},
            "professor": {"connect": {"id": professor.id}},
            "qtdFacil": 0, "qtdMedio": 0, "qtdDificil": 0,
            "vagas": 30, "duracaoMinutos": 60,
            "janelaInicio": agora - timedelta(hours=1),
            "janelaFim": agora + timedelta(hours=2),
            "status": "PUBLICADO",
            "embaralharAlternativas": True,
            "questoesSelecionadas": Json(ids),
        }
    )
    yield s.id, set(ids)
    resultados = await db.resultadoaluno.find_many(where={"simuladoId": s.id})
    for r in resultados:
        await db.tentativaquestao.delete_many(where={"resultadoId": r.id})
    await db.resultadoaluno.delete_many(where={"simuladoId": s.id})
    await db.simulado.delete(where={"id": s.id})


@pytest.mark.asyncio
async def test_iniciar_usa_questoes_selecionadas(
    client, token_aluno, auth, simulado_manual
):
    sid, ids = simulado_manual
    r = await client.post(f"/aluno/iniciar-prova/{sid}", headers=auth(token_aluno))
    assert r.status_code == 201, r.text
    questoes = r.json()["questoes"]
    assert len(questoes) == len(ids)
    assert {q["questaoId"] for q in questoes} == ids


@pytest.mark.asyncio
async def test_banco_questoes_admin(client, token_admin, auth):
    comp, ids = await _selecao(3)
    r = await client.get(
        f"/simulados/banco?componenteId={comp}", headers=auth(token_admin)
    )
    assert r.status_code == 200
    questoes = r.json()
    assert isinstance(questoes, list) and len(questoes) >= len(ids)
    assert all(q["componenteId"] == comp for q in questoes)


@pytest.mark.asyncio
async def test_banco_questoes_requer_admin(client, token_aluno, auth):
    comp, _ = await _selecao(1)
    r = await client.get(
        f"/simulados/banco?componenteId={comp}", headers=auth(token_aluno)
    )
    assert r.status_code == 403
