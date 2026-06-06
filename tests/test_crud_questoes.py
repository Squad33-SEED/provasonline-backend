from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from prisma import Json

from src.database import db


@pytest_asyncio.fixture
async def comp_assunto(conexao_db):
    componente = await db.componentecurricular.find_first(where={"ativo": True})
    assunto = await db.assunto.find_first(where={"componenteId": componente.id})
    return {"componenteId": componente.id, "assuntoId": assunto.id}


def _payload(comp_assunto, **over):
    base = {
        "componenteId": comp_assunto["componenteId"],
        "assuntoId": comp_assunto["assuntoId"],
        "tipo": "MULTIPLA_ESCOLHA",
        "dificuldade": "FACIL",
        "enunciado": "Quanto é 2 + 2? TESTE",
        "alternativas": [
            {"letra": "A", "texto": "3"},
            {"letra": "B", "texto": "4"},
            {"letra": "C", "texto": "5"},
            {"letra": "D", "texto": "6"},
        ],
        "respostaCorreta": "B",
        "urlImagem": None,
    }
    base.update(over)
    return base


@pytest_asyncio.fixture
async def limpar_questoes(conexao_db):
    ids: list[str] = []
    yield ids
    for qid in ids:
        await db.tentativaquestao.delete_many(where={"questaoId": qid})
        await db.questao.delete(where={"id": qid})


@pytest_asyncio.fixture
async def questao_de_outro(conexao_db, comp_assunto):
    usuario = await db.usuario.create(
        data={
            "nome": "Prof Externo CRUD TESTE",
            "cpf": "90000000002",
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
            "componente": {"connect": {"id": comp_assunto["componenteId"]}},
            "assunto": {"connect": {"id": comp_assunto["assuntoId"]}},
            "tipo": "MULTIPLA_ESCOLHA",
            "dificuldade": "FACIL",
            "enunciado": "De outro professor CRUD TESTE",
            "alternativas": Json([{"letra": "A", "texto": "1"}, {"letra": "B", "texto": "2"}]),
            "respostaCorreta": "A",
        }
    )
    yield questao.id
    await db.questao.delete(where={"id": questao.id})
    await db.professor.delete(where={"id": professor.id})
    await db.usuario.delete(where={"id": usuario.id})


@pytest_asyncio.fixture
async def questao_em_etapa_andamento(conexao_db, comp_assunto):
    u_ana = await db.usuario.find_unique(where={"cpf": "98765432100"})
    ana = await db.professor.find_unique(where={"usuarioId": u_ana.id})
    u_aluno = await db.usuario.find_unique(where={"cpf": "11122233396"})
    aluno = await db.aluno.find_unique(where={"usuarioId": u_aluno.id})
    agora = datetime.now(timezone.utc)

    questao = await db.questao.create(
        data={
            "professor": {"connect": {"id": ana.id}},
            "componente": {"connect": {"id": comp_assunto["componenteId"]}},
            "assunto": {"connect": {"id": comp_assunto["assuntoId"]}},
            "tipo": "MULTIPLA_ESCOLHA",
            "dificuldade": "FACIL",
            "enunciado": "Questao em andamento CRUD TESTE",
            "alternativas": Json([{"letra": "A", "texto": "1"}, {"letra": "B", "texto": "2"}]),
            "respostaCorreta": "A",
        }
    )
    simulado = await db.simulado.create(
        data={
            "titulo": "Etapa CRUD Andamento TESTE",
            "componente": {"connect": {"id": comp_assunto["componenteId"]}},
            "professor": {"connect": {"id": ana.id}},
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
    resultado = await db.resultadoaluno.create(
        data={
            "simulado": {"connect": {"id": simulado.id}},
            "aluno": {"connect": {"id": aluno.id}},
            "statusResultado": "EM_ANDAMENTO",
            "iniciadoEm": agora,
        }
    )
    await db.tentativaquestao.create(
        data={
            "resultado": {"connect": {"id": resultado.id}},
            "questao": {"connect": {"id": questao.id}},
            "ordem": 1,
        }
    )
    yield questao.id
    await db.resultadoaluno.delete(where={"id": resultado.id})
    await db.simulado.delete(where={"id": simulado.id})
    await db.questao.delete(where={"id": questao.id})


@pytest.mark.asyncio
async def test_criar_questao_201(client, token_professor, auth, comp_assunto, limpar_questoes):
    resp = await client.post("/questoes", headers=auth(token_professor), json=_payload(comp_assunto))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["respostaCorreta"] == "B"
    assert len(body["alternativas"]) == 4
    assert body["ativa"] is True
    limpar_questoes.append(body["id"])


@pytest.mark.asyncio
async def test_criar_bloqueia_nao_professor(client, token_admin, token_aluno, auth, comp_assunto):
    for token in (token_admin, token_aluno):
        resp = await client.post("/questoes", headers=auth(token), json=_payload(comp_assunto))
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_criar_minimo_de_alternativas(client, token_professor, auth, comp_assunto):
    payload = _payload(comp_assunto, alternativas=[{"letra": "A", "texto": "única"}], respostaCorreta="A")
    resp = await client.post("/questoes", headers=auth(token_professor), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_criar_resposta_correta_invalida(client, token_professor, auth, comp_assunto):
    payload = _payload(comp_assunto, respostaCorreta="E")
    resp = await client.post("/questoes", headers=auth(token_professor), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_criar_assunto_de_outro_componente(client, token_professor, auth, comp_assunto):
    outro = await db.assunto.find_first(where={"componenteId": {"not": comp_assunto["componenteId"]}})
    if outro is None:
        pytest.skip("Banco não tem assunto de outro componente")
    payload = _payload(comp_assunto, assuntoId=outro.id)
    resp = await client.post("/questoes", headers=auth(token_professor), json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_listar_e_filtrar_por_componente(client, token_professor, auth, comp_assunto, limpar_questoes):
    criada = await client.post("/questoes", headers=auth(token_professor), json=_payload(comp_assunto))
    qid = criada.json()["id"]
    limpar_questoes.append(qid)

    resp = await client.get(
        "/questoes",
        headers=auth(token_professor),
        params={"componenteId": comp_assunto["componenteId"]},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(q["id"] == qid for q in resp.json())


@pytest.mark.asyncio
async def test_buscar_inexistente_404(client, token_professor, auth):
    resp = await client.get("/questoes/nao-existe-xyz", headers=auth(token_professor))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_editar_questao_propria(client, token_professor, auth, comp_assunto, limpar_questoes):
    criada = await client.post("/questoes", headers=auth(token_professor), json=_payload(comp_assunto))
    qid = criada.json()["id"]
    limpar_questoes.append(qid)

    resp = await client.put(
        f"/questoes/{qid}",
        headers=auth(token_professor),
        json=_payload(comp_assunto, enunciado="Enunciado editado CRUD TESTE"),
    )
    assert resp.status_code == 200
    assert resp.json()["enunciado"] == "Enunciado editado CRUD TESTE"


@pytest.mark.asyncio
async def test_professor_nao_edita_de_outro_403(client, token_professor, auth, comp_assunto, questao_de_outro):
    resp = await client.put(
        f"/questoes/{questao_de_outro}",
        headers=auth(token_professor),
        json=_payload(comp_assunto),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_toggle_desativa_e_reativa(client, token_professor, auth, comp_assunto, limpar_questoes):
    criada = await client.post("/questoes", headers=auth(token_professor), json=_payload(comp_assunto))
    qid = criada.json()["id"]
    limpar_questoes.append(qid)

    r1 = await client.patch(f"/questoes/{qid}/toggle", headers=auth(token_professor))
    assert r1.status_code == 200
    assert r1.json()["ativa"] is False

    r2 = await client.patch(f"/questoes/{qid}/toggle", headers=auth(token_professor))
    assert r2.status_code == 200
    assert r2.json()["ativa"] is True


@pytest.mark.asyncio
async def test_admin_desativa_qualquer(client, token_admin, auth, questao_de_outro):
    resp = await client.patch(f"/questoes/{questao_de_outro}/toggle", headers=auth(token_admin))
    assert resp.status_code == 200
    assert resp.json()["ativa"] is False


@pytest.mark.asyncio
async def test_nao_desativa_questao_em_andamento(client, token_professor, auth, questao_em_etapa_andamento):
    resp = await client.patch(
        f"/questoes/{questao_em_etapa_andamento}/toggle",
        headers=auth(token_professor),
    )
    assert resp.status_code == 422
