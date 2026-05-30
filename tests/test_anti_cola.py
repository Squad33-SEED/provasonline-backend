from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


async def _componente_id():
    questoes = await db.questao.find_many(where={"ativa": True})
    return questoes[0].componenteId if questoes else None


async def _aluno_demo():
    usuario = await db.usuario.find_unique(where={"cpf": "11122233396"})
    return await db.aluno.find_unique(where={"usuarioId": usuario.id})


async def _criar_simulado_com_resultado(janela_inicio, janela_fim):
    componente_id = await _componente_id()
    professor = await db.professor.find_first()
    agora = _agora()
    simulado = await db.simulado.create(
        data={
            "titulo": "TESTE anti-cola",
            "componente": {"connect": {"id": componente_id}},
            "professor": {"connect": {"id": professor.id}},
            "qtdFacil": 0,
            "qtdMedio": 0,
            "qtdDificil": 0,
            "vagas": 5,
            "duracaoMinutos": 30,
            "janelaInicio": janela_inicio,
            "janelaFim": janela_fim,
            "status": "PUBLICADO",
            "embaralharAlternativas": False,
        }
    )
    aluno = await _aluno_demo()
    resultado = await db.resultadoaluno.create(
        data={
            "aluno": {"connect": {"id": aluno.id}},
            "simulado": {"connect": {"id": simulado.id}},
            "statusResultado": "FINALIZADO",
            "pontuacao": 8.0,
            "iniciadoEm": agora - timedelta(minutes=30),
            "finalizadoEm": agora - timedelta(minutes=10),
        }
    )
    return simulado.id, resultado.id


@pytest_asyncio.fixture
async def resultado_janela_aberta(conexao_db):
    agora = _agora()
    simulado_id, resultado_id = await _criar_simulado_com_resultado(
        agora - timedelta(hours=1), agora + timedelta(hours=2)
    )
    yield resultado_id
    await db.resultadoaluno.delete(where={"id": resultado_id})
    await db.simulado.delete(where={"id": simulado_id})


@pytest_asyncio.fixture
async def resultado_janela_encerrada(conexao_db):
    agora = _agora()
    simulado_id, resultado_id = await _criar_simulado_com_resultado(
        agora - timedelta(days=2), agora - timedelta(hours=1)
    )
    yield resultado_id
    await db.resultadoaluno.delete(where={"id": resultado_id})
    await db.simulado.delete(where={"id": simulado_id})


@pytest.mark.asyncio
async def test_gabarito_oculto_antes_da_janela_fim(
    client, token_aluno, auth, resultado_janela_aberta
):
    resp = await client.get(
        f"/aluno/resultado/{resultado_janela_aberta}", headers=auth(token_aluno)
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["gabaritoDisponivel"] is False
    assert corpo["gabarito"] is None
    assert corpo["gabaritoDisponivelEm"] is not None


@pytest.mark.asyncio
async def test_gabarito_liberado_apos_janela_fim(
    client, token_aluno, auth, resultado_janela_encerrada
):
    resp = await client.get(
        f"/aluno/resultado/{resultado_janela_encerrada}", headers=auth(token_aluno)
    )
    assert resp.status_code == 200
    assert resp.json()["gabaritoDisponivel"] is True


@pytest.mark.asyncio
async def test_admin_ve_gabarito_mesmo_com_janela_aberta(
    client, token_admin, auth, resultado_janela_aberta
):
    resp = await client.get(
        f"/aluno/resultado/{resultado_janela_aberta}", headers=auth(token_admin)
    )
    assert resp.status_code == 200
    assert resp.json()["gabaritoDisponivel"] is True
