from datetime import datetime, timedelta, timezone

import pytest

from src.database import db


def _janela(minutos_inicio=5, horas_fim=3):
    inicio = datetime.now(timezone.utc) + timedelta(minutes=minutos_inicio)
    fim = datetime.now(timezone.utc) + timedelta(hours=horas_fim)
    return inicio.isoformat(), fim.isoformat()


@pytest.mark.asyncio
async def test_criar_etapa_composicao_persiste_e_soma(client, token_admin, auth):
    comps = await db.componentecurricular.find_many(where={"ativo": True})
    assert len(comps) >= 2
    c1, c2 = comps[0], comps[1]
    inicio, fim = _janela()

    payload = {
        "titulo": "Etapa Composicao Teste",
        "composicao": [
            {"componenteId": c1.id, "qtdFacil": 2, "qtdMedio": 1, "qtdDificil": 0},
            {"componenteId": c2.id, "qtdFacil": 1, "qtdMedio": 0, "qtdDificil": 1},
        ],
        "vagas": 30,
        "duracaoMinutos": 60,
        "janelaInicio": inicio,
        "janelaFim": fim,
    }
    r = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert r.status_code == 201, r.text
    body = r.json()

    # totais viram a soma das cotas
    assert body["qtdFacil"] == 3
    assert body["qtdMedio"] == 1
    assert body["qtdDificil"] == 1

    # persistiu a composição por componente
    sim = await db.simulado.find_unique(where={"id": body["id"]})
    comp = sim.composicaoPorComponente
    assert isinstance(comp, dict)
    assert comp[c1.id] == {"facil": 2, "medio": 1, "dificil": 0}
    assert comp[c2.id] == {"facil": 1, "medio": 0, "dificil": 1}


@pytest.mark.asyncio
async def test_composicao_alem_do_disponivel_retorna_422(client, token_admin, auth):
    comps = await db.componentecurricular.find_many(where={"ativo": True})
    c1 = comps[0]
    inicio, fim = _janela()
    payload = {
        "titulo": "Etapa Composicao Excesso",
        "composicao": [{"componenteId": c1.id, "qtdFacil": 999, "qtdMedio": 0, "qtdDificil": 0}],
        "vagas": 10,
        "duracaoMinutos": 60,
        "janelaInicio": inicio,
        "janelaFim": fim,
    }
    r = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_iniciar_prova_usa_composicao_total(client, token_admin, token_aluno, auth):
    comps = await db.componentecurricular.find_many(where={"ativo": True})
    c1, c2 = comps[0], comps[1]
    inicio, fim = _janela()
    payload = {
        "titulo": "Etapa Composicao Iniciar",
        "composicao": [
            {"componenteId": c1.id, "qtdFacil": 2, "qtdMedio": 1, "qtdDificil": 0},
            {"componenteId": c2.id, "qtdFacil": 1, "qtdMedio": 1, "qtdDificil": 1},
        ],
        "vagas": 10,
        "duracaoMinutos": 60,
        "janelaInicio": inicio,
        "janelaFim": fim,
    }
    r = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    # abre a janela retroativamente para poder iniciar agora
    await db.simulado.update(
        where={"id": sid},
        data={"janelaInicio": datetime.now(timezone.utc) - timedelta(minutes=1)},
    )

    r2 = await client.post(f"/aluno/iniciar-prova/{sid}", headers=auth(token_aluno))
    assert r2.status_code == 201, r2.text
    # soma das cotas: 3 fáceis + 2 médias + 1 difícil = 6
    assert r2.json()["totalQuestoes"] == 6
