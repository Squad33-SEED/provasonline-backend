import pytest
import pytest_asyncio

from src.database import db


@pytest_asyncio.fixture
async def limpar_ips(conexao_db):
    ids: list[str] = []
    yield ids
    for ip_id in ids:
        await db.ipautorizado.delete(where={"id": ip_id})


@pytest.mark.asyncio
async def test_admin_cria_lista_edita_e_alterna_ip(
    client,
    token_admin,
    auth,
    limpar_ips,
):
    payload = {
        "ip": "192.168.0.10",
        "descricao": "Laboratório CRUD TESTE",
    }

    criar = await client.post(
        "/ips",
        json=payload,
        headers=auth(token_admin),
    )

    assert criar.status_code == 201, criar.text

    criado = criar.json()
    limpar_ips.append(criado["id"])

    assert criado["ip"] == "192.168.0.10"
    assert criado["descricao"] == "Laboratório CRUD TESTE"
    assert criado["ativo"] is True
    assert "criadoEm" in criado

    listar = await client.get("/ips", headers=auth(token_admin))

    assert listar.status_code == 200, listar.text
    assert any(item["id"] == criado["id"] for item in listar.json())

    editar = await client.put(
        f"/ips/{criado['id']}",
        json={
            "ip": "10.0.0.20",
            "descricao": "Sala atualizada CRUD TESTE",
        },
        headers=auth(token_admin),
    )

    assert editar.status_code == 200, editar.text

    editado = editar.json()

    assert editado["id"] == criado["id"]
    assert editado["ip"] == "10.0.0.20"
    assert editado["descricao"] == "Sala atualizada CRUD TESTE"
    assert editado["ativo"] is True

    toggle = await client.patch(
        f"/ips/{criado['id']}/toggle",
        headers=auth(token_admin),
    )

    assert toggle.status_code == 200, toggle.text

    alternado = toggle.json()

    assert alternado["id"] == criado["id"]
    assert alternado["ativo"] is False

    listar_ativos = await client.get("/ips?ativo=true", headers=auth(token_admin))

    assert listar_ativos.status_code == 200, listar_ativos.text
    assert all(item["ativo"] is True for item in listar_ativos.json())


@pytest.mark.asyncio
async def test_professor_nao_pode_criar_ip(
    client,
    token_professor,
    auth,
):
    resposta = await client.post(
        "/ips",
        json={
            "ip": "172.16.0.55",
            "descricao": "Bloqueado CRUD TESTE",
        },
        headers=auth(token_professor),
    )

    assert resposta.status_code == 403