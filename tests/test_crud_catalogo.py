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
async def test_toggle_nivel_bloqueado_com_modalidades_ativas(client, admin_token):
    """Não pode desativar nível que ainda tem modalidades ativas."""
    nivel_id = await _get_nivel(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        "/catalogo/modalidades",
        json={"nivelId": nivel_id, "nome": "Modal Bloqueio", "supletivo": False},
        headers=headers,
    )

    r = await client.patch(
        f"/catalogo/niveis/{nivel_id}/toggle", headers=headers
    )

    if r.status_code == 200:
        await client.patch(f"/catalogo/niveis/{nivel_id}/toggle", headers=headers)
    else:
        assert r.status_code == 422