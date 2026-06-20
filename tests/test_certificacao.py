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
async def test_so_conclusao_sem_parcial(cenario):
    ag = _agora()
    # Aprovou só 1 dos componentes obrigatórios: NÃO emite certificado
    # (decisão de produto: não existe certificado parcial).
    await processar_certificacao(cenario["sims"][0], cenario["resultados"][0].id, cenario["aluno"].id, 8.0, ag)
    nenhum = await db.certificado.find_first(where={"alunoId": cenario["aluno"].id})
    assert nenhum is None

    # Completou todos os obrigatórios: emite o de CONCLUSÃO.
    await processar_certificacao(cenario["sims"][1], cenario["resultados"][1].id, cenario["aluno"].id, 8.0, ag)
    certs = await db.certificado.find_many(where={"alunoId": cenario["aluno"].id})
    assert len(certs) == 1
    assert certs[0].tipo == "CONCLUSAO"
    assert certs[0].codigoVerificacao


@pytest.mark.asyncio
async def test_etapa_multi_componente_credita_todos_de_uma_vez(cenario):
    # Cerne da correção: uma ÚNICA etapa multi-componente, ao trazer a nota de
    # cada componente, credita todos os obrigatórios e emite o CONCLUSAO —
    # antes só o componente principal era creditado e o certificado nunca saía.
    ag = _agora()
    comp1_id = cenario["sims"][0].componenteId
    comp2_id = cenario["sims"][1].componenteId

    await processar_certificacao(
        cenario["sims"][0],
        cenario["resultados"][0].id,
        cenario["aluno"].id,
        8.0,
        ag,
        notas_por_componente={comp1_id: 8.0, comp2_id: 7.0},
    )

    aprov = await db.aproveitamentocandidato.find_many(where={"alunoId": cenario["aluno"].id})
    assert {a.componenteId for a in aprov} == {comp1_id, comp2_id}

    certs = await db.certificado.find_many(where={"alunoId": cenario["aluno"].id})
    assert len(certs) == 1
    assert certs[0].tipo == "CONCLUSAO"


@pytest.mark.asyncio
async def test_multi_componente_credita_so_quem_passou(cenario):
    # Componente abaixo da nota mínima não é creditado; sem todos os
    # obrigatórios aprovados, nenhum certificado é emitido (sem parcial).
    ag = _agora()
    comp1_id = cenario["sims"][0].componenteId
    comp2_id = cenario["sims"][1].componenteId

    await processar_certificacao(
        cenario["sims"][0],
        cenario["resultados"][0].id,
        cenario["aluno"].id,
        6.5,
        ag,
        notas_por_componente={comp1_id: 8.0, comp2_id: 5.0},
    )

    aprov = await db.aproveitamentocandidato.find_many(where={"alunoId": cenario["aluno"].id})
    assert {a.componenteId for a in aprov} == {comp1_id}

    nenhum = await db.certificado.find_first(where={"alunoId": cenario["aluno"].id})
    assert nenhum is None


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
    # nome mascarado: 1ª letra de cada parte; CPF parcial (esconde 3 primeiros e 2 últimos)
    assert body["nome"] == "C******** C***"
    assert body["cpf"] == "***.000.000-**"

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
