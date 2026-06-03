import pytest
import pytest_asyncio

from src.database import db


async def _professor_ana():
    usuario = await db.usuario.find_unique(where={"cpf": "98765432100"})
    return await db.professor.find_unique(where={"usuarioId": usuario.id})


@pytest_asyncio.fixture
async def turma_temp(conexao_db):
    escola = await db.escola.find_first()
    modalidade = await db.modalidade.find_first()
    turma = await db.turma.create(
        data={
            "nome": "TURMA TESTE VINCULO",
            "anoLetivo": 2026,
            "escola": {"connect": {"id": escola.id}},
            "modalidade": {"connect": {"id": modalidade.id}},
        }
    )
    yield turma.id
    await db.professorturma.delete_many(where={"turmaId": turma.id})
    await db.turma.delete(where={"id": turma.id})


@pytest.mark.asyncio
async def test_listar_professores_requer_admin(client, token_professor, token_aluno, auth):
    assert (await client.get("/professores", headers=auth(token_professor))).status_code == 403
    assert (await client.get("/professores", headers=auth(token_aluno))).status_code == 403


@pytest.mark.asyncio
async def test_listar_professores_admin(client, token_admin, auth):
    resp = await client.get("/professores", headers=auth(token_admin))
    assert resp.status_code == 200
    professores = resp.json()
    assert isinstance(professores, list)
    ana = await _professor_ana()
    assert any(p["id"] == ana.id for p in professores)


@pytest.mark.asyncio
async def test_vincular_listar_e_desvincular(client, token_admin, auth, turma_temp):
    ana = await _professor_ana()

    r_post = await client.post(
        f"/turmas/{turma_temp}/professores",
        json={"professorId": ana.id},
        headers=auth(token_admin),
    )
    assert r_post.status_code == 201
    assert r_post.json()["id"] == ana.id

    r_list = await client.get(
        f"/turmas/{turma_temp}/professores", headers=auth(token_admin)
    )
    assert r_list.status_code == 200
    assert any(p["id"] == ana.id for p in r_list.json())

    r_dup = await client.post(
        f"/turmas/{turma_temp}/professores",
        json={"professorId": ana.id},
        headers=auth(token_admin),
    )
    assert r_dup.status_code == 409

    r_del = await client.delete(
        f"/turmas/{turma_temp}/professores/{ana.id}", headers=auth(token_admin)
    )
    assert r_del.status_code == 204

    r_list2 = await client.get(
        f"/turmas/{turma_temp}/professores", headers=auth(token_admin)
    )
    assert all(p["id"] != ana.id for p in r_list2.json())


@pytest.mark.asyncio
async def test_vincular_requer_admin(client, token_aluno, auth, turma_temp):
    ana = await _professor_ana()
    resp = await client.post(
        f"/turmas/{turma_temp}/professores",
        json={"professorId": ana.id},
        headers=auth(token_aluno),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_vincular_turma_inexistente_404(client, token_admin, auth):
    ana = await _professor_ana()
    resp = await client.post(
        "/turmas/nao-existe-123/professores",
        json={"professorId": ana.id},
        headers=auth(token_admin),
    )
    assert resp.status_code == 404
