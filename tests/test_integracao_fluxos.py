"""Testes de integração de fluxo completo por persona.

Cobrem os caminhos ponta-a-ponta exigidos no cronograma (Semana 17/19):
- Admin: catálogo -> publicar etapa -> aparece na listagem
- Aluno: iniciar -> responder -> submeter -> resultado -> histórico
- Anti-cola e RBAC já têm suítes dedicadas (test_anti_cola, test_auth_rbac)
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from src.database import db


def _agora():
    return datetime.now(timezone.utc)


async def _componente_com_questoes(minimo: int = 1):
    questoes = await db.questao.find_many(where={"ativa": True})
    contagem: dict[str, dict[str, int]] = {}
    for q in questoes:
        c = contagem.setdefault(q.componenteId, {"FACIL": 0, "MEDIO": 0, "DIFICIL": 0})
        c[q.dificuldade] += 1
    for componente_id, dif in contagem.items():
        if sum(dif.values()) >= minimo:
            return componente_id, dif
    return None, None


async def _aluno_demo():
    usuario = await db.usuario.find_unique(where={"cpf": "11122233396"})
    return await db.aluno.find_unique(where={"usuarioId": usuario.id})


# ---------------------------------------------------------------------------
# Fluxo ADMIN: publicar etapa via API e vê-la na listagem
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_publica_etapa_e_aparece_na_listagem(client, token_admin, auth):
    componente_id, dif = await _componente_com_questoes(minimo=1)
    assert componente_id, "seed sem questões ativas"

    agora = _agora()
    payload = {
        "titulo": "Integração - Etapa publicada via API",
        "descricao": "Teste E2E de publicação",
        "componenteId": componente_id,
        "qtdFacil": 1 if dif["FACIL"] else 0,
        "qtdMedio": 1 if dif["MEDIO"] else 0,
        "qtdDificil": 0,
        "vagas": 30,
        "duracaoMinutos": 60,
        "janelaInicio": (agora + timedelta(hours=1)).isoformat(),
        "janelaFim": (agora + timedelta(days=2)).isoformat(),
        "turmaIds": [],
        "embaralharAlternativas": True,
    }

    criar = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert criar.status_code == 201, criar.text
    simulado_id = criar.json()["id"]
    assert criar.json()["status"] == "PUBLICADO"
    assert criar.json()["embaralharAlternativas"] is True

    listagem = await client.get("/simulados", headers=auth(token_admin))
    assert listagem.status_code == 200
    ids = [s["id"] for s in listagem.json()]
    assert simulado_id in ids

    detalhe = await client.get(f"/simulados/{simulado_id}", headers=auth(token_admin))
    assert detalhe.status_code == 200
    assert detalhe.json()["titulo"] == payload["titulo"]

    await db.aplicacao.delete_many(where={"simuladoId": simulado_id})
    await db.simulado.delete(where={"id": simulado_id})


@pytest.mark.asyncio
async def test_admin_publicar_sem_questoes_suficientes_falha(client, token_admin, auth):
    componente_id, _ = await _componente_com_questoes(minimo=1)
    agora = _agora()
    payload = {
        "titulo": "Integração - banco insuficiente",
        "componenteId": componente_id,
        "qtdFacil": 9999,
        "qtdMedio": 0,
        "qtdDificil": 0,
        "vagas": 10,
        "duracaoMinutos": 30,
        "janelaInicio": (agora + timedelta(hours=1)).isoformat(),
        "janelaFim": (agora + timedelta(days=1)).isoformat(),
        "turmaIds": [],
        "embaralharAlternativas": False,
    }
    resp = await client.post("/simulados", json=payload, headers=auth(token_admin))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_disponibilidade_retorna_contadores(client, token_admin, auth):
    componente_id, dif = await _componente_com_questoes(minimo=1)
    resp = await client.get(
        f"/simulados/disponibilidade?componenteId={componente_id}",
        headers=auth(token_admin),
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["facil"] == dif["FACIL"]
    assert corpo["medio"] == dif["MEDIO"]
    assert corpo["dificil"] == dif["DIFICIL"]


# ---------------------------------------------------------------------------
# Fluxo ALUNO: iniciar -> responder -> submeter -> resultado -> histórico
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def etapa_aberta_para_aluno(conexao_db):
    """Cria uma etapa PUBLICADA com janela aberta agora (sem passar pela
    validação Pydantic de janelaInicio futura, que impediria o aluno de iniciar)."""
    componente_id, dif = await _componente_com_questoes(minimo=2)
    professor = await db.professor.find_first()
    agora = _agora()

    qtd_facil = min(2, dif["FACIL"])
    qtd_medio = min(1, dif["MEDIO"])
    if qtd_facil + qtd_medio < 1:
        qtd_facil = 1

    simulado = await db.simulado.create(
        data={
            "titulo": "Integração - Etapa do aluno",
            "componente": {"connect": {"id": componente_id}},
            "professor": {"connect": {"id": professor.id}},
            "qtdFacil": qtd_facil,
            "qtdMedio": qtd_medio,
            "qtdDificil": 0,
            "vagas": 10,
            "duracaoMinutos": 60,
            "janelaInicio": agora - timedelta(minutes=10),
            "janelaFim": agora + timedelta(hours=2),
            "status": "PUBLICADO",
            "embaralharAlternativas": False,
        }
    )
    yield simulado.id, qtd_facil + qtd_medio

    aluno = await _aluno_demo()
    resultados = await db.resultadoaluno.find_many(
        where={"simuladoId": simulado.id, "alunoId": aluno.id}
    )
    for r in resultados:
        await db.tentativaquestao.delete_many(where={"resultadoId": r.id})
        await db.violacaoprova.delete_many(where={"resultadoId": r.id})
        await db.resultadoaluno.delete(where={"id": r.id})
    await db.simulado.delete(where={"id": simulado.id})


@pytest.mark.asyncio
async def test_fluxo_completo_aluno_iniciar_responder_submeter_resultado(
    client, token_aluno, auth, etapa_aberta_para_aluno
):
    simulado_id, total_esperado = etapa_aberta_para_aluno

    # 1. etapa aparece em disponíveis
    disp = await client.get("/aluno/etapas-disponiveis", headers=auth(token_aluno))
    assert disp.status_code == 200
    assert any(e["id"] == simulado_id for e in disp.json())

    # 2. iniciar prova -> sorteia questões
    iniciar = await client.post(
        f"/aluno/iniciar-prova/{simulado_id}", headers=auth(token_aluno)
    )
    assert iniciar.status_code == 201, iniciar.text
    dados = iniciar.json()
    resultado_id = dados["resultadoId"]
    questoes = dados["questoes"]
    assert len(questoes) == total_esperado

    # 3. responder (auto-save) marcando "A" em todas
    itens = [{"questaoId": q["questaoId"], "resposta": "A"} for q in questoes]
    salvar = await client.patch(
        f"/aluno/responder/{resultado_id}",
        json={"respostas": itens},
        headers=auth(token_aluno),
    )
    assert salvar.status_code == 200
    assert salvar.json()["totalSalvas"] == len(itens)

    # 4. submeter -> gera nota, gabarito ainda oculto (janela aberta)
    submeter = await client.post(
        f"/aluno/submeter/{resultado_id}", headers=auth(token_aluno)
    )
    assert submeter.status_code == 200
    corpo = submeter.json()
    assert corpo["statusResultado"] == "FINALIZADO"
    assert corpo["total"] == total_esperado
    assert corpo["gabaritoDisponivel"] is False
    assert corpo["gabarito"] is None

    # 5. resultado -> mesma nota, ainda sem gabarito (anti-cola)
    resultado = await client.get(
        f"/aluno/resultado/{resultado_id}", headers=auth(token_aluno)
    )
    assert resultado.status_code == 200
    assert resultado.json()["pontuacao"] == corpo["pontuacao"]

    # 6. histórico contém o resultado finalizado
    historico = await client.get("/aluno/historico", headers=auth(token_aluno))
    assert historico.status_code == 200
    assert any(h["resultadoId"] == resultado_id for h in historico.json())


@pytest.mark.asyncio
async def test_aluno_nao_pode_iniciar_duas_vezes(
    client, token_aluno, auth, etapa_aberta_para_aluno
):
    simulado_id, _ = etapa_aberta_para_aluno

    primeira = await client.post(
        f"/aluno/iniciar-prova/{simulado_id}", headers=auth(token_aluno)
    )
    assert primeira.status_code == 201
    resultado_id = primeira.json()["resultadoId"]

    # finaliza
    await client.post(f"/aluno/submeter/{resultado_id}", headers=auth(token_aluno))

    # tentar iniciar de novo -> 409 (etapa já realizada)
    segunda = await client.post(
        f"/aluno/iniciar-prova/{simulado_id}", headers=auth(token_aluno)
    )
    assert segunda.status_code == 409
    detalhe = segunda.json()["detail"]
    assert detalhe["statusResultado"] == "FINALIZADO"


@pytest.mark.asyncio
async def test_aluno_registra_violacao_durante_prova_e_notifica(
    client, token_aluno, auth, etapa_aberta_para_aluno
):
    simulado_id, _ = etapa_aberta_para_aluno

    iniciar = await client.post(
        f"/aluno/iniciar-prova/{simulado_id}", headers=auth(token_aluno)
    )
    resultado_id = iniciar.json()["resultadoId"]

    viol = await client.post(
        f"/aluno/violacao/{resultado_id}",
        json={"tipo": "trocou_aba"},
        headers=auth(token_aluno),
    )
    assert viol.status_code == 200
    assert viol.json()["totalViolacoes"] == 1

    notifs = await db.notificacao.find_many(
        where={"referenciaId": resultado_id, "tipo": "violacao_prova"}
    )
    assert len(notifs) >= 2  # professor + admin(s)
