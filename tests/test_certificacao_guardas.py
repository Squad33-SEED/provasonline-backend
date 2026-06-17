from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def cenario_contador(conexao_db):
    nivel = await db.nivelensino.create(data={"nome": "Nivel Contador Teste", "ordem": 8})
    modalidade = await db.modalidade.create(
        data={"nivel": {"connect": {"id": nivel.id}}, "nome": "Reg Contador"}
    )
    comp = await db.componentecurricular.create(
        data={"modalidade": {"connect": {"id": modalidade.id}}, "nome": "Comp Contador", "codigo": "CTC"}
    )
    professor = await db.professor.find_first()
    agora = _agora()
    sims = []
    for i in range(4):
        s = await db.simulado.create(
            data={
                "titulo": f"Etapa Contador {i}",
                "componente": {"connect": {"id": comp.id}},
                "professor": {"connect": {"id": professor.id}},
                "qtdFacil": 0, "qtdMedio": 0, "qtdDificil": 0, "vagas": 5, "duracaoMinutos": 60,
                "janelaInicio": agora - timedelta(hours=1),
                "janelaFim": agora + timedelta(hours=3),
                "status": "PUBLICADO",
                "geraCertificado": True,
                "nivelEnsino": {"connect": {"id": nivel.id}},
                "notaMinimaCertificacao": 6.0,
            }
        )
        sims.append(s)

    u = await db.usuario.find_unique(where={"cpf": "11122233396"})
    aluno = await db.aluno.find_unique(where={"usuarioId": u.id})

    yield {"sims": sims, "alunoId": aluno.id}

    await db.resultadoaluno.delete_many(
        where={"alunoId": aluno.id, "simuladoId": {"in": [s.id for s in sims]}}
    )
    for s in sims:
        await db.simulado.delete(where={"id": s.id})
    await db.componentecurricular.delete(where={"id": comp.id})
    await db.modalidade.delete(where={"id": modalidade.id})
    await db.nivelensino.delete(where={"id": nivel.id})


@pytest.mark.asyncio
async def test_contador_bloqueia_quarta_tentativa(client, token_aluno, auth, cenario_contador):
    sims = cenario_contador["sims"]
    for i in range(3):
        r = await client.post(f"/aluno/iniciar-prova/{sims[i].id}", headers=auth(token_aluno))
        assert r.status_code == 201, r.text

    r4 = await client.post(f"/aluno/iniciar-prova/{sims[3].id}", headers=auth(token_aluno))
    assert r4.status_code == 403


@pytest.mark.asyncio
async def test_cadastro_candidato_externo(client, token_admin, auth):
    cpf = "52998224725"
    r = await client.post(
        "/alunos",
        headers=auth(token_admin),
        json={
            "nome": "Candidato Externo Teste",
            "cpf": cpf,
            "dataNascimento": "2000-01-01",
            "tipoCandidato": "EXTERNO",
            "prereqValidado": True,
            "prereqDocumento": "HIST-2019-001",
        },
    )
    assert r.status_code == 201, r.text

    u = await db.usuario.find_unique(where={"cpf": cpf})
    assert u.tipoCandidato == "EXTERNO"
    assert u.prereqValidado is True
    assert u.prereqDocumento == "HIST-2019-001"
    assert u.prereqValidadoPorId is not None
    assert u.prereqValidadoEm is not None

    aluno = await db.aluno.find_unique(where={"usuarioId": u.id})
    await db.aluno.delete(where={"id": aluno.id})
    await db.usuario.delete(where={"id": u.id})
