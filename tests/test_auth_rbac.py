import pytest

from src.security import decode_token


@pytest.mark.asyncio
async def test_login_admin_retorna_token_com_role_no_jwt(client):
    resp = await client.post(
        "/auth/login", json={"cpf": "12345678909", "senha": "admin123"}
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert "access_token" in corpo
    payload = decode_token(corpo["access_token"])
    assert payload["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_login_senha_errada_retorna_401(client):
    resp = await client.post(
        "/auth/login", json={"cpf": "12345678909", "senha": "senhaErrada"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_cpf_inexistente_retorna_401(client):
    resp = await client.post(
        "/auth/login", json={"cpf": "00000000272", "senha": "qualquer"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rota_protegida_sem_token_retorna_403(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rota_protegida_com_token_invalido_retorna_401(client):
    resp = await client.get(
        "/auth/me", headers={"Authorization": "Bearer token.falso.aqui"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_retorna_usuario_autenticado(client, token_aluno, auth):
    resp = await client.get("/auth/me", headers=auth(token_aluno))
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "ALUNO"


@pytest.mark.asyncio
async def test_rbac_aluno_nao_cria_simulado(client, token_aluno, auth):
    payload = {
        "titulo": "Tentativa indevida",
        "componenteId": "qualquer",
        "qtdFacil": 1,
        "qtdMedio": 1,
        "qtdDificil": 1,
        "vagas": 10,
        "duracaoMinutos": 30,
        "janelaInicio": "2026-01-01T00:00:00Z",
        "janelaFim": "2026-12-31T00:00:00Z",
        "turmaIds": [],
        "embaralharAlternativas": False,
    }
    resp = await client.post("/simulados", json=payload, headers=auth(token_aluno))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rbac_admin_nao_acessa_etapas_de_aluno(client, token_admin, auth):
    resp = await client.get("/aluno/etapas-disponiveis", headers=auth(token_admin))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_logout_revoga_token(client, auth):
    login = await client.post(
        "/auth/login", json={"cpf": "11122233396", "senha": "admin123"}
    )
    token = login.json()["access_token"]

    antes = await client.get("/auth/me", headers=auth(token))
    assert antes.status_code == 200

    logout = await client.post("/auth/logout", headers=auth(token))
    assert logout.status_code == 204

    depois = await client.get("/auth/me", headers=auth(token))
    assert depois.status_code == 401
