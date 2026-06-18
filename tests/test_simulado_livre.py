import pytest

from src.database import db


async def _componente_com_questoes(minimo=2):
    # Pós-migração, as questões vêm da API externa (mockada no conftest);
    # basta um componente vinculado a uma matéria (questionsSubjectSlug).
    comp = await db.componentecurricular.find_first(
        where={"ativo": True, "questionsSubjectSlug": {"not": None}}
    )
    return comp.id if comp else None


async def _limpar(simulado_id):
    await db.itemsimuladolivre.delete_many(where={"simuladoLivreId": simulado_id})
    await db.simuladolivre.delete(where={"id": simulado_id})


@pytest.mark.asyncio
async def test_disciplinas_agrega_por_nome(client, token_aluno, auth):
    resp = await client.get("/simulado-livre/disciplinas", headers=auth(token_aluno))
    assert resp.status_code == 200
    disciplinas = resp.json()
    assert len(disciplinas) > 0

    nomes = [d["nome"] for d in disciplinas]
    assert len(nomes) == len(set(nomes)), "nomes de disciplina devem ser únicos (agregados)"

    for d in disciplinas:
        assert d["totalQuestoes"] > 0, "disciplinas sem questões não devem aparecer"
        assert d["totalQuestoes"] == d["facil"] + d["medio"] + d["dificil"]
        assert len(d["componenteIds"]) >= 1


@pytest.mark.asyncio
async def test_sortear_com_disciplina_agregada(client, token_aluno, auth):
    disciplinas = (await client.get("/simulado-livre/disciplinas", headers=auth(token_aluno))).json()
    alvo = max(disciplinas, key=lambda d: d["totalQuestoes"])

    resp = await client.post(
        "/simulado-livre/sortear",
        json={
            "componenteIds": alvo["componenteIds"],
            "qtdFacil": 1,
            "qtdMedio": 0,
            "qtdDificil": 0,
            "duracaoMinutos": 30,
        },
        headers=auth(token_aluno),
    )
    assert resp.status_code == 201
    sid = resp.json()["id"]
    assert resp.json()["totalQuestoes"] == 1
    await _limpar(sid)


@pytest.mark.asyncio
async def test_sortear_cria_simulado(client, token_aluno, auth):
    cid = await _componente_com_questoes()
    resp = await client.post(
        "/simulado-livre/sortear",
        json={"componenteIds": [cid], "qtdFacil": 1, "qtdMedio": 0, "qtdDificil": 0},
        headers=auth(token_aluno),
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["totalQuestoes"] == 1
    assert corpo["status"] == "EM_ANDAMENTO"
    await _limpar(corpo["id"])


@pytest.mark.asyncio
async def test_sortear_banco_insuficiente_falha(client, token_aluno, auth):
    cid = await _componente_com_questoes()
    resp = await client.post(
        "/simulado-livre/sortear",
        json={"componenteIds": [cid], "qtdFacil": 9999, "qtdMedio": 0, "qtdDificil": 0},
        headers=auth(token_aluno),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_banco_lista_e_filtra(client, token_aluno, auth):
    cid = await _componente_com_questoes()
    todas = await client.get(
        f"/simulado-livre/banco?componente_id={cid}", headers=auth(token_aluno)
    )
    assert todas.status_code == 200
    assert len(todas.json()) >= 1

    faceis = await client.get(
        f"/simulado-livre/banco?componente_id={cid}&dificuldade=FACIL",
        headers=auth(token_aluno),
    )
    assert faceis.status_code == 200
    for q in faceis.json():
        assert q["dificuldade"] == "FACIL"


@pytest.mark.asyncio
async def test_selecao_manual_e_submissao_com_gabarito(client, token_aluno, auth):
    cid = await _componente_com_questoes()
    banco = (await client.get(
        f"/simulado-livre/banco?componente_id={cid}", headers=auth(token_aluno)
    )).json()
    questao_ids = [q["id"] for q in banco[:2]]

    criar = await client.post(
        "/simulado-livre/selecionar",
        json={"componenteIds": [cid], "questaoIds": questao_ids, "duracaoMinutos": 20},
        headers=auth(token_aluno),
    )
    assert criar.status_code == 201
    simulado = criar.json()
    assert simulado["totalQuestoes"] == 2

    primeira = simulado["questoes"][0]["questaoId"]
    submeter = await client.post(
        f"/simulado-livre/{simulado['id']}/submeter",
        json={"respostas": [{"questaoId": primeira, "resposta": "A"}]},
        headers=auth(token_aluno),
    )
    assert submeter.status_code == 200
    corpo = submeter.json()
    assert corpo["status"] == "FINALIZADO"
    assert corpo["total"] == 2
    assert len(corpo["gabarito"]) == 2
    assert all("alternativaCorreta" in g for g in corpo["gabarito"])

    await _limpar(simulado["id"])


@pytest.mark.asyncio
async def test_nao_submete_duas_vezes(client, token_aluno, auth):
    cid = await _componente_com_questoes()
    criar = await client.post(
        "/simulado-livre/sortear",
        json={"componenteIds": [cid], "qtdFacil": 1, "qtdMedio": 0, "qtdDificil": 0},
        headers=auth(token_aluno),
    )
    sid = criar.json()["id"]
    await client.post(f"/simulado-livre/{sid}/submeter", json={"respostas": []}, headers=auth(token_aluno))
    segunda = await client.post(
        f"/simulado-livre/{sid}/submeter", json={"respostas": []}, headers=auth(token_aluno)
    )
    assert segunda.status_code == 409
    await _limpar(sid)


@pytest.mark.asyncio
async def test_admin_nao_acessa_simulado_livre(client, token_admin, auth):
    cid = await _componente_com_questoes()
    resp = await client.post(
        "/simulado-livre/sortear",
        json={"componenteIds": [cid], "qtdFacil": 1, "qtdMedio": 0, "qtdDificil": 0},
        headers=auth(token_admin),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_historico_lista_simulados(client, token_aluno, auth):
    cid = await _componente_com_questoes()
    criar = await client.post(
        "/simulado-livre/sortear",
        json={"componenteIds": [cid], "qtdFacil": 1, "qtdMedio": 0, "qtdDificil": 0},
        headers=auth(token_aluno),
    )
    sid = criar.json()["id"]
    hist = await client.get("/simulado-livre", headers=auth(token_aluno))
    assert hist.status_code == 200
    assert any(s["id"] == sid for s in hist.json())
    await _limpar(sid)
