import pytest


@pytest.mark.asyncio
async def test_rate_limit_bloqueia_apos_cinco_tentativas(client):
    credenciais = {"cpf": "98765432100", "senha": "senhaIncorreta"}

    codigos = []
    for _ in range(6):
        resp = await client.post("/auth/login", json=credenciais)
        codigos.append(resp.status_code)

    assert codigos[:5] == [401, 401, 401, 401, 401]
    assert codigos[5] == 429


@pytest.mark.asyncio
async def test_rate_limit_mensagem_orienta_espera(client):
    credenciais = {"cpf": "98765432100", "senha": "senhaIncorreta"}

    ultimo = None
    for _ in range(6):
        ultimo = await client.post("/auth/login", json=credenciais)

    assert ultimo.status_code == 429
    assert "tentativas" in ultimo.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limit_isolado_por_cpf(client):
    for _ in range(5):
        await client.post("/auth/login", json={"cpf": "98765432100", "senha": "x"})

    outro = await client.post(
        "/auth/login", json={"cpf": "11122233396", "senha": "admin123"}
    )
    assert outro.status_code == 200
