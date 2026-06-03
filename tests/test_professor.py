from datetime import datetime, timedelta, timezone

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


@pytest_asyncio.fixture
async def violacao_de_aluno_da_ana(conexao_db):
    u_ana = await db.usuario.find_unique(where={"cpf": "98765432100"})
    ana = await db.professor.find_unique(where={"usuarioId": u_ana.id})
    u_lucas = await db.usuario.find_unique(where={"cpf": "11122233396"})
    lucas = await db.aluno.find_unique(where={"usuarioId": u_lucas.id})

    escola = await db.escola.find_first()
    modalidade = await db.modalidade.find_first()
    agora = datetime.now(timezone.utc)

    turma = await db.turma.create(
        data={
            "nome": "TURMA VIOL TESTE",
            "anoLetivo": 2026,
            "escola": {"connect": {"id": escola.id}},
            "modalidade": {"connect": {"id": modalidade.id}},
        }
    )
    await db.professorturma.create(
        data={"professor": {"connect": {"id": ana.id}}, "turma": {"connect": {"id": turma.id}}}
    )
    await db.turmaaluno.create(
        data={
            "turma": {"connect": {"id": turma.id}},
            "aluno": {"connect": {"id": lucas.id}},
            "entrouEm": agora,
        }
    )

    comp = (await db.questao.find_first(where={"ativa": True})).componenteId
    prof_qualquer = await db.professor.find_first()
    simulado = await db.simulado.create(
        data={
            "titulo": "Etapa Viol TESTE",
            "componente": {"connect": {"id": comp}},
            "professor": {"connect": {"id": prof_qualquer.id}},
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
            "aluno": {"connect": {"id": lucas.id}},
            "statusResultado": "EM_ANDAMENTO",
            "iniciadoEm": agora,
        }
    )
    await db.violacaoprova.create(
        data={
            "resultado": {"connect": {"id": resultado.id}},
            "tipo": "trocou_aba",
            "detalhe": "trocou de aba",
        }
    )

    yield resultado.id

    await db.violacaoprova.delete_many(where={"resultadoId": resultado.id})
    await db.resultadoaluno.delete(where={"id": resultado.id})
    await db.simulado.delete(where={"id": simulado.id})
    await db.turmaaluno.delete_many(where={"turmaId": turma.id})
    await db.professorturma.delete_many(where={"turmaId": turma.id})
    await db.turma.delete(where={"id": turma.id})


@pytest.mark.asyncio
async def test_professor_violacoes_dos_seus_alunos(
    client, token_professor, auth, violacao_de_aluno_da_ana
):
    resp = await client.get("/professor/violacoes", headers=auth(token_professor))
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["total"] >= 1
    assert any(
        o["resultadoId"] == violacao_de_aluno_da_ana for o in corpo["ocorrencias"]
    )
    assert any(e["etapaTitulo"] == "Etapa Viol TESTE" for e in corpo["porEtapa"])


@pytest.mark.asyncio
async def test_professor_violacoes_requer_professor(
    client, token_admin, token_aluno, auth
):
    assert (await client.get("/professor/violacoes", headers=auth(token_admin))).status_code == 403
    assert (await client.get("/professor/violacoes", headers=auth(token_aluno))).status_code == 403
