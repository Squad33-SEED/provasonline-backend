import pytest
import pytest_asyncio

from src.database import db


CPFS = ["52998224725", "16899535009"]

CSV_OK = (
    "nome,email,cpf,data_nascimento,turma_id\n"
    "Aluno Import Um,,52998224725,2008-03-15,\n"
    "Aluno Import Dois,,16899535009,2007-11-02,\n"
    ",,00000000000,2007-01-01,\n"
    "Aluno Ruim,,123,2007-01-01,\n"
)


async def _limpar():
    for cpf in CPFS:
        u = await db.usuario.find_unique(where={"cpf": cpf})
        if u:
            al = await db.aluno.find_unique(where={"usuarioId": u.id})
            if al:
                await db.turmaaluno.delete_many(where={"alunoId": al.id})
                await db.aluno.delete(where={"id": al.id})
            await db.tokenacesso.delete_many(where={"usuarioId": u.id})
            await db.usuario.delete(where={"id": u.id})


@pytest_asyncio.fixture
async def limpeza(conexao_db):
    await _limpar()
    yield
    await _limpar()


@pytest.mark.asyncio
async def test_criar_importacao_retorna_job_pendente(client, token_admin, auth, limpeza):
    files = {"arquivo": ("alunos.csv", CSV_OK.encode("utf-8"), "text/csv")}
    resp = await client.post("/alunos/importar", files=files, headers=auth(token_admin))
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["status"] == "PENDENTE"
    assert corpo["totalLinhas"] == 4
    assert "id" in corpo
    await db.importacaoalunos.delete(where={"id": corpo["id"]})


@pytest.mark.asyncio
async def test_importacao_aluno_sem_permissao_admin(client, token_aluno, auth):
    files = {"arquivo": ("alunos.csv", CSV_OK.encode("utf-8"), "text/csv")}
    resp = await client.post("/alunos/importar", files=files, headers=auth(token_aluno))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_importacao_rejeita_nao_csv(client, token_admin, auth):
    files = {"arquivo": ("dados.txt", b"qualquer", "text/plain")}
    resp = await client.post("/alunos/importar", files=files, headers=auth(token_admin))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_fluxo_completo_processa_em_lotes(client, token_admin, auth, limpeza):
    files = {"arquivo": ("alunos.csv", CSV_OK.encode("utf-8"), "text/csv")}
    criar = await client.post("/alunos/importar", files=files, headers=auth(token_admin))
    job = criar.json()["id"]

    concluida = False
    rodadas = 0
    while not concluida and rodadas < 20:
        rodadas += 1
        proc = await client.post(
            f"/alunos/importar/{job}/processar", headers=auth(token_admin)
        )
        assert proc.status_code == 200
        concluida = proc.json()["concluida"]

    status = await client.get(f"/alunos/importar/{job}", headers=auth(token_admin))
    corpo = status.json()
    assert corpo["status"] == "CONCLUIDA"
    assert corpo["importados"] == 2
    assert corpo["ignorados"] == 2
    assert len(corpo["erros"]) == 2

    await db.importacaoalunos.delete(where={"id": job})


@pytest.mark.asyncio
async def test_status_de_importacao_inexistente_404(client, token_admin, auth):
    resp = await client.get(
        "/alunos/importar/nao-existe-123", headers=auth(token_admin)
    )
    assert resp.status_code == 404
