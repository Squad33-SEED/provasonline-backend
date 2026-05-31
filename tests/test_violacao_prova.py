from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


async def _aluno_demo():
    usuario = await db.usuario.find_unique(where={"cpf": "11122233396"})
    return await db.aluno.find_unique(where={"usuarioId": usuario.id})


@pytest_asyncio.fixture
async def resultado_em_andamento(conexao_db):
    professor = await db.professor.find_first()
    questoes = await db.questao.find_many(where={"ativa": True})
    componente_id = questoes[0].componenteId
    agora = _agora()
    simulado = await db.simulado.create(
        data={
            "titulo": "TESTE violacao",
            "componente": {"connect": {"id": componente_id}},
            "professor": {"connect": {"id": professor.id}},
            "qtdFacil": 0,
            "qtdMedio": 0,
            "qtdDificil": 0,
            "vagas": 5,
            "duracaoMinutos": 30,
            "janelaInicio": agora - timedelta(hours=1),
            "janelaFim": agora + timedelta(hours=2),
            "status": "PUBLICADO",
            "embaralharAlternativas": False,
        }
    )
    aluno = await _aluno_demo()
    resultado = await db.resultadoaluno.create(
        data={
            "aluno": {"connect": {"id": aluno.id}},
            "simulado": {"connect": {"id": simulado.id}},
            "statusResultado": "EM_ANDAMENTO",
            "iniciadoEm": agora,
        }
    )
    yield resultado.id
    await db.violacaoprova.delete_many(where={"resultadoId": resultado.id})
    await db.notificacao.delete_many(where={"referenciaId": resultado.id})
    await db.resultadoaluno.delete(where={"id": resultado.id})
    await db.simulado.delete(where={"id": simulado.id})


@pytest.mark.asyncio
async def test_registrar_violacao_incrementa_contador(
    client, token_aluno, auth, resultado_em_andamento
):
    r1 = await client.post(
        f"/aluno/violacao/{resultado_em_andamento}",
        json={"tipo": "trocou_aba"},
        headers=auth(token_aluno),
    )
    assert r1.status_code == 200
    assert r1.json()["registrada"] is True
    assert r1.json()["totalViolacoes"] == 1

    r2 = await client.post(
        f"/aluno/violacao/{resultado_em_andamento}",
        json={"tipo": "saiu_tela_cheia"},
        headers=auth(token_aluno),
    )
    assert r2.json()["totalViolacoes"] == 2


@pytest.mark.asyncio
async def test_violacao_notifica_professor_e_admin(
    client, token_aluno, auth, resultado_em_andamento
):
    await client.post(
        f"/aluno/violacao/{resultado_em_andamento}",
        json={"tipo": "trocou_aba"},
        headers=auth(token_aluno),
    )

    notificacoes = await db.notificacao.find_many(
        where={"referenciaId": resultado_em_andamento, "tipo": "violacao_prova"}
    )
    assert len(notificacoes) >= 2

    destinatarios = set()
    for n in notificacoes:
        usuario = await db.usuario.find_unique(where={"id": n.usuarioDestId})
        destinatarios.add(usuario.tipo)
    assert "ADMIN" in destinatarios
    assert "PROFESSOR" in destinatarios


@pytest.mark.asyncio
async def test_violacao_resultado_inexistente_404(client, token_aluno, auth):
    resp = await client.post(
        "/aluno/violacao/nao-existe-123",
        json={"tipo": "trocou_aba"},
        headers=auth(token_aluno),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_violacao_requer_aluno(client, token_admin, auth, resultado_em_andamento):
    resp = await client.post(
        f"/aluno/violacao/{resultado_em_andamento}",
        json={"tipo": "trocou_aba"},
        headers=auth(token_admin),
    )
    assert resp.status_code == 403
