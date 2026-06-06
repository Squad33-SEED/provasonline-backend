from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.database import db
from src.services.certificacao import processar_certificacao


def _agora():
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def cenario(conexao_db):
    nivel = await db.nivelensino.create(data={"nome": "Nivel CERT Teste", "ordem": 9})
    modalidade = await db.modalidade.create(
        data={"nivel": {"connect": {"id": nivel.id}}, "nome": "Regular CERT Teste"}
    )
    comp1 = await db.componentecurricular.create(
        data={"modalidade": {"connect": {"id": modalidade.id}}, "nome": "Comp CERT 1", "codigo": "CT1"}
    )
    comp2 = await db.componentecurricular.create(
        data={"modalidade": {"connect": {"id": modalidade.id}}, "nome": "Comp CERT 2", "codigo": "CT2"}
    )
    for c in (comp1, comp2):
        await db.nivelcomponente.create(
            data={
                "nivel": {"connect": {"id": nivel.id}},
                "componente": {"connect": {"id": c.id}},
                "obrigatorio": True,
            }
        )

    usuario = await db.usuario.create(
        data={"nome": "Candidato CERT", "cpf": "10000000077", "senhaHash": "x", "tipo": "ALUNO"}
    )
    aluno = await db.aluno.create(
        data={
            "usuario": {"connect": {"id": usuario.id}},
            "dataNascimento": datetime(2000, 1, 1, tzinfo=timezone.utc),
        }
    )

    professor = await db.professor.find_first()
    agora = _agora()
    sims, resultados = [], []
    for c in (comp1, comp2):
        s = await db.simulado.create(
            data={
                "titulo": f"Etapa CERT {c.codigo}",
                "componente": {"connect": {"id": c.id}},
                "professor": {"connect": {"id": professor.id}},
                "qtdFacil": 0, "qtdMedio": 0, "qtdDificil": 0, "vagas": 5, "duracaoMinutos": 30,
                "janelaInicio": agora - timedelta(hours=1),
                "janelaFim": agora + timedelta(hours=2),
                "status": "PUBLICADO",
                "geraCertificado": True,
                "nivelEnsino": {"connect": {"id": nivel.id}},
                "notaMinimaCertificacao": 6.0,
            }
        )
        r = await db.resultadoaluno.create(
            data={
                "simulado": {"connect": {"id": s.id}},
                "aluno": {"connect": {"id": aluno.id}},
                "statusResultado": "FINALIZADO", "pontuacao": 8.0, "finalizadoEm": agora,
            }
        )
        sims.append(s)
        resultados.append(r)

    yield {"nivel": nivel, "aluno": aluno, "sims": sims, "resultados": resultados}

    await db.certificado.delete_many(where={"alunoId": aluno.id})
    await db.aproveitamentocandidato.delete_many(where={"alunoId": aluno.id})
    for r in resultados:
        await db.resultadoaluno.delete(where={"id": r.id})
    for s in sims:
        await db.simulado.delete(where={"id": s.id})
    await db.nivelcomponente.delete_many(where={"nivelId": nivel.id})
    await db.componentecurricular.delete(where={"id": comp1.id})
    await db.componentecurricular.delete(where={"id": comp2.id})
    await db.modalidade.delete(where={"id": modalidade.id})
    await db.aluno.delete(where={"id": aluno.id})
    await db.usuario.delete(where={"id": usuario.id})
    await db.nivelensino.delete(where={"id": nivel.id})


@pytest.mark.asyncio
async def test_parcial_depois_conclusao(cenario):
    ag = _agora()
    await processar_certificacao(cenario["sims"][0], cenario["resultados"][0].id, cenario["aluno"].id, 8.0, ag)
    parcial = await db.certificado.find_first(where={"alunoId": cenario["aluno"].id})
    assert parcial is not None
    assert parcial.tipo == "PROFICIENCIA_PARCIAL"

    await processar_certificacao(cenario["sims"][1], cenario["resultados"][1].id, cenario["aluno"].id, 8.0, ag)
    certs = await db.certificado.find_many(where={"alunoId": cenario["aluno"].id})
    assert len(certs) == 1
    assert certs[0].tipo == "CONCLUSAO"
    assert certs[0].codigoVerificacao


@pytest.mark.asyncio
async def test_reprovado_nao_acumula(cenario):
    ag = _agora()
    await processar_certificacao(cenario["sims"][0], cenario["resultados"][0].id, cenario["aluno"].id, 5.0, ag)
    aprov = await db.aproveitamentocandidato.find_many(where={"alunoId": cenario["aluno"].id})
    assert len(aprov) == 0


@pytest.mark.asyncio
async def test_verificacao_publica(client, cenario):
    ag = _agora()
    await processar_certificacao(cenario["sims"][0], cenario["resultados"][0].id, cenario["aluno"].id, 8.0, ag)
    await processar_certificacao(cenario["sims"][1], cenario["resultados"][1].id, cenario["aluno"].id, 8.0, ag)
    cert = await db.certificado.find_first(where={"alunoId": cenario["aluno"].id})

    r = await client.get(f"/certificados/verificar/{cert.codigoVerificacao}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "VALIDO"
    assert body["nome"] == "Candidato CERT"

    r2 = await client.get("/certificados/verificar/codigo-que-nao-existe")
    assert r2.json()["status"] == "NAO_ENCONTRADO"


@pytest.mark.asyncio
async def test_simulado_certificador_exige_nivel(client, token_admin, auth):
    ji = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    jf = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    r = await client.post(
        "/simulados",
        headers=auth(token_admin),
        json={
            "titulo": "Etapa Cert sem nivel",
            "componenteId": "qualquer-id",
            "qtdFacil": 1, "qtdMedio": 0, "qtdDificil": 0,
            "vagas": 5, "duracaoMinutos": 30,
            "janelaInicio": ji, "janelaFim": jf,
            "geraCertificado": True,
        },
    )
    assert r.status_code == 422
