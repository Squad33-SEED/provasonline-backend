import pytest

from src.database import db


@pytest.mark.asyncio
async def test_componentes_incluem_assuntos(client, token_admin, auth):
    resp = await client.get("/catalogo/componentes", headers=auth(token_admin))
    assert resp.status_code == 200
    componentes = resp.json()
    assert len(componentes) > 0
    for c in componentes:
        assert "assuntos" in c
        assert isinstance(c["assuntos"], list)


@pytest.mark.asyncio
async def test_assuntos_por_componente(client, token_admin, auth):
    componentes = (await client.get("/catalogo/componentes", headers=auth(token_admin))).json()
    componente_id = componentes[0]["id"]

    resp = await client.get(f"/catalogo/assuntos/{componente_id}", headers=auth(token_admin))
    assert resp.status_code == 200
    assuntos = resp.json()
    assert isinstance(assuntos, list)
    for a in assuntos:
        assert "id" in a and "nome" in a


@pytest.mark.asyncio
async def test_assuntos_componente_inexistente_retorna_lista_vazia(client, token_admin, auth):
    resp = await client.get("/catalogo/assuntos/nao-existe-123", headers=auth(token_admin))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_catalogo_exige_autenticacao(client):
    resp = await client.get("/catalogo/componentes")
    assert resp.status_code == 403
