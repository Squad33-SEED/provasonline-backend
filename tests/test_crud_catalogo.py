import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app


async def _token(client: AsyncClient, cpf: str, senha: str) -> str:
    r = await client.post("/auth/login", json={"cpf": cpf, "senha": senha})
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(client, conexao_db):
    return await _token(client, "12345678909", "admin123")


@pytest_asyncio.fixture
async def prof_token(client, conexao_db):
    return await _token(client, "98765432100", "admin123")


async def _get_nivel(client, admin_token) -> str:
    r = await client.get(
        "/catalogo/niveis", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 200
    niveis = r.json()
    assert len(niveis) > 0, "Precisa de pelo menos 1 nível no banco"
    return niveis[0]["id"]


@pytest.mark.asyncio
async def test_criar_nivel(client, admin_token):
    r = await client.post(
        "/catalogo/niveis",
        json={"nome": "Nível Teste CRUD", "ordem": 99},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["nome"] == "Nível Teste CRUD"
    assert body["ativo"] is True


@pytest.mark.asyncio
async def test_criar_nivel_403_nao_admin(client, prof_token):
    r = await client.post(
        "/catalogo/niveis",
        json={"nome": "X", "ordem": 0},
        headers={"Authorization": f"Bearer {prof_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_crud_modalidade(client, admin_token):
    nivel_id = await _get_nivel(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modalidade Teste", "supletivo": False},
        headers=headers,
    )
    assert r.status_code == 201
    modal_id = r.json()["id"]

    r = await client.put(
        f"/catalogo/modalidades/{modal_id}",
        json={"nome": "Modalidade Editada", "supletivo": True},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["nome"] == "Modalidade Editada"

    r = await client.patch(
        f"/catalogo/modalidades/{modal_id}/toggle", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is False

    r = await client.patch(
        f"/catalogo/modalidades/{modal_id}/toggle", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is True


@pytest.mark.asyncio
async def test_criar_modalidade_403(client, prof_token):
    r = await client.post(
        "/catalogo/modalidades",
        json={"nivelId": "qualquer", "nome": "X", "supletivo": False},
        headers={"Authorization": f"Bearer {prof_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_crud_componente(client, admin_token):
    nivel_id = await _get_nivel(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modal Aux Comp", "supletivo": False},
        headers=headers,
    )
    modal_id = r.json()["id"]

    r = await client.post(
        "/catalogo/componentes",
        json={"modalidadeId": modal_id, "nome": "Comp Teste", "codigo": "CT001"},
        headers=headers,
    )
    assert r.status_code == 201
    comp_id = r.json()["id"]

    r = await client.put(
        f"/catalogo/componentes/{comp_id}",
        json={"nome": "Comp Editado", "codigo": "CT002"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["nome"] == "Comp Editado"

    r = await client.patch(
        f"/catalogo/componentes/{comp_id}/toggle", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is False


@pytest.mark.asyncio
async def test_componente_persiste_questions_subject_slug(client, admin_token):
    nivel_id = await _get_nivel(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modal Slug", "supletivo": False},
        headers=headers,
    )
    modal_id = r.json()["id"]

    r = await client.post(
        "/catalogo/componentes",
        json={
            "modalidadeId": modal_id,
            "nome": "Comp Slug",
            "codigo": "CS001",
            "questionsSubjectSlug": "matematica",
        },
        headers=headers,
    )
    assert r.status_code == 201
    comp = r.json()
    comp_id = comp["id"]
    assert comp["questionsSubjectSlug"] == "matematica"

    r = await client.get("/catalogo/componentes/admin", headers=headers)
    achado = next(c for c in r.json() if c["id"] == comp_id)
    assert achado["questionsSubjectSlug"] == "matematica"

    r = await client.put(
        f"/catalogo/componentes/{comp_id}",
        json={
            "nome": "Comp Slug",
            "codigo": "CS001",
            "questionsSubjectSlug": "portugues",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["questionsSubjectSlug"] == "portugues"


@pytest.mark.asyncio
async def test_criar_componente_403(client, prof_token):
    r = await client.post(
        "/catalogo/componentes",
        json={"modalidadeId": "x", "nome": "X", "codigo": "X"},
        headers={"Authorization": f"Bearer {prof_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_crud_assunto(client, admin_token):
    nivel_id = await _get_nivel(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modal Aux Assunto", "supletivo": False},
        headers=headers,
    )
    modal_id = r.json()["id"]

    r = await client.post(
        "/catalogo/componentes",
        json={"modalidadeId": modal_id, "nome": "Comp p/ Assunto", "codigo": "CPA"},
        headers=headers,
    )
    comp_id = r.json()["id"]

    r = await client.post(
        f"/catalogo/componentes/{comp_id}/assuntos",
        json={"nome": "Assunto Teste"},
        headers=headers,
    )
    assert r.status_code == 201
    assunto_id = r.json()["id"]

    r = await client.patch(
        f"/catalogo/assuntos/{assunto_id}/toggle", headers=headers
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is False


@pytest.mark.asyncio
async def test_toggle_nivel_desativa_em_cascata(client, admin_token):
    """Desativar um nível agora cascateia: modalidade -> componente são
    desativados juntos (sem bloqueio 422). Reativar não reativa os filhos."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # nível isolado próprio (não tocar em níveis semeados)
    nivel_id = (await client.post(
        "/catalogo/niveis",
        json={"nome": "Nível Cascata Teste", "ordem": 96},
        headers=headers,
    )).json()["id"]
    modal_id = (await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modal Cascata", "supletivo": False},
        headers=headers,
    )).json()["id"]
    comp_id = (await client.post(
        "/catalogo/componentes",
        json={"modalidadeId": modal_id, "nome": "Comp Cascata", "codigo": "CASC1"},
        headers=headers,
    )).json()["id"]

    # desativa o nível -> 200, sem bloqueio
    r = await client.patch(f"/catalogo/niveis/{nivel_id}/toggle", headers=headers)
    assert r.status_code == 200
    assert r.json()["ativo"] is False

    # modalidade e componente foram desativados em cascata
    mods = (await client.get("/catalogo/modalidades/admin", headers=headers)).json()
    assert next(m for m in mods if m["id"] == modal_id)["ativo"] is False
    comps = (await client.get("/catalogo/componentes/admin", headers=headers)).json()
    assert next(c for c in comps if c["id"] == comp_id)["ativo"] is False

    # reativar o nível NÃO reativa os filhos
    r2 = await client.patch(f"/catalogo/niveis/{nivel_id}/toggle", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["ativo"] is True
    mods2 = (await client.get("/catalogo/modalidades/admin", headers=headers)).json()
    assert next(m for m in mods2 if m["id"] == modal_id)["ativo"] is False


@pytest.mark.asyncio
async def test_toggle_componente_desativa_assuntos_em_cascata(client, admin_token):
    """Desativar um componente desativa seus assuntos em cascata."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    nivel_id = (await client.post(
        "/catalogo/niveis",
        json={"nome": "Nível Casc Comp", "ordem": 95},
        headers=headers,
    )).json()["id"]
    modal_id = (await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modal CC", "supletivo": False},
        headers=headers,
    )).json()["id"]
    comp_id = (await client.post(
        "/catalogo/componentes",
        json={"modalidadeId": modal_id, "nome": "Comp CC", "codigo": "CCASC"},
        headers=headers,
    )).json()["id"]
    assunto_id = (await client.post(
        f"/catalogo/componentes/{comp_id}/assuntos",
        json={"nome": "Assunto CC"},
        headers=headers,
    )).json()["id"]

    r = await client.patch(f"/catalogo/componentes/{comp_id}/toggle", headers=headers)
    assert r.status_code == 200
    assert r.json()["ativo"] is False

    # o assunto saiu da lista de ativos do componente (foi desativado)
    assuntos = (await client.get(f"/catalogo/assuntos/{comp_id}", headers=headers)).json()
    assert all(a["id"] != assunto_id for a in assuntos)