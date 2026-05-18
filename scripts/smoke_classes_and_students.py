import asyncio
import sys
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

from src.security import hash_password


BACKEND_URL = "http://localhost:3333"

ADMIN_CPF = "12345678909"
ADMIN_SENHA = "admin123"
ALUNO_DEMO_CPF = "11122233396"

CPF_TURMA_TESTE_NOME = "Turma Smoke Test 2A"
CPF_ALUNO_TESTE = "39053344705"
CPF_ALUNO_INVALIDO = "11111111111"
DATA_NASC_TESTE = date(2008, 4, 15)


async def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = "✓" if condition else "✗"
    color_open = "\033[32m" if condition else "\033[31m"
    color_close = "\033[0m"
    print(f"  {color_open}{icon}{color_close} {label}{(' — ' + detail) if detail else ''}")
    return condition


async def login_admin(client: httpx.AsyncClient) -> str:
    res = await client.post(
        "/auth/login",
        json={"cpf": ADMIN_CPF, "senha": ADMIN_SENHA},
    )
    if res.status_code != 200:
        raise RuntimeError(
            f"Falha no login do admin (status {res.status_code}). "
            f"Reinicie o backend para zerar rate-limit."
        )
    return res.json()["access_token"]


async def login_aluno_demo(client: httpx.AsyncClient) -> str:
    res = await client.post(
        "/auth/login",
        json={"cpf": ALUNO_DEMO_CPF, "senha": ADMIN_SENHA},
    )
    if res.status_code != 200:
        raise RuntimeError(
            f"Falha no login do aluno demo (status {res.status_code})."
        )
    return res.json()["access_token"]


async def cleanup_artefatos_teste(db: Prisma) -> None:
    aluno_existente = await db.usuario.find_unique(where={"cpf": CPF_ALUNO_TESTE})
    if aluno_existente:
        registro_aluno = await db.aluno.find_unique(
            where={"usuarioId": aluno_existente.id}
        )
        if registro_aluno:
            await db.turmaaluno.delete_many(where={"alunoId": registro_aluno.id})
            await db.aluno.delete(where={"id": registro_aluno.id})
        await db.tokenacesso.delete_many(where={"usuarioId": aluno_existente.id})
        await db.logacesso.delete_many(where={"usuarioId": aluno_existente.id})
        await db.usuario.delete(where={"id": aluno_existente.id})

    turma = await db.turma.find_first(where={"nome": CPF_TURMA_TESTE_NOME})
    if turma:
        await db.turmaaluno.delete_many(where={"turmaId": turma.id})
        await db.turma.delete(where={"id": turma.id})


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SMOKE TEST — Lote 2A (Cards 3 e 4 — Backend) ===\n")
    failed = 0
    turma_id = None

    try:
        await cleanup_artefatos_teste(db)

        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15.0) as client:
            print("→ Login do admin (Ricardo)")
            token_admin = await login_admin(client)
            await check("token de admin obtido", bool(token_admin))
            headers_admin = {"Authorization": f"Bearer {token_admin}"}

            escola = await db.escola.find_first()
            if not escola:
                print("✗ Nenhuma escola no banco. Rode 'python seed_catalogo.py' antes.")
                return 1

            modalidade = await db.modalidade.find_first(where={"ativo": True})
            if not modalidade:
                print("✗ Nenhuma modalidade no banco.")
                return 1

            print(f"\n→ POST /turmas (Card 3)")
            res = await client.post(
                "/turmas",
                json={
                    "nome": CPF_TURMA_TESTE_NOME,
                    "anoLetivo": 2026,
                    "escolaId": escola.id,
                    "modalidadeId": modalidade.id,
                },
                headers=headers_admin,
            )
            if not await check(
                "criação retorna 201",
                res.status_code == 201,
                f"status: {res.status_code} body: {res.text[:200]}",
            ):
                failed += 1
                return failed

            turma_data = res.json()
            turma_id = turma_data["id"]
            await check("turma tem totalAlunos=0", turma_data["totalAlunos"] == 0)
            await check(
                "turma retorna escola e modalidade aninhadas",
                "escola" in turma_data and "modalidade" in turma_data,
            )

            print("\n→ POST /turmas duplicada (deve retornar 409)")
            res = await client.post(
                "/turmas",
                json={
                    "nome": CPF_TURMA_TESTE_NOME,
                    "anoLetivo": 2026,
                    "escolaId": escola.id,
                    "modalidadeId": modalidade.id,
                },
                headers=headers_admin,
            )
            if not await check(
                "rejeita duplicata com 409",
                res.status_code == 409,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /turmas com escolaId inválido (deve retornar 422)")
            res = await client.post(
                "/turmas",
                json={
                    "nome": "Turma Inexistente",
                    "anoLetivo": 2026,
                    "escolaId": "id-que-nao-existe",
                    "modalidadeId": modalidade.id,
                },
                headers=headers_admin,
            )
            if not await check(
                "rejeita escolaId inválido com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /turmas sem ser ADMIN (deve retornar 403)")
            token_aluno = await login_aluno_demo(client)
            res = await client.post(
                "/turmas",
                json={
                    "nome": "Turma Sem Permissao",
                    "anoLetivo": 2026,
                    "escolaId": escola.id,
                    "modalidadeId": modalidade.id,
                },
                headers={"Authorization": f"Bearer {token_aluno}"},
            )
            if not await check(
                "ALUNO recebe 403 ao tentar criar turma",
                res.status_code == 403,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /alunos com CPF inválido (deve retornar 422)")
            res = await client.post(
                "/alunos",
                json={
                    "nome": "Aluno CPF Falso",
                    "cpf": CPF_ALUNO_INVALIDO,
                    "dataNascimento": "2008-04-15",
                    "necessidadeEspecial": False,
                },
                headers=headers_admin,
            )
            if not await check(
                "rejeita CPF inválido com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /alunos com data futura (deve retornar 422)")
            res = await client.post(
                "/alunos",
                json={
                    "nome": "Aluno Do Futuro",
                    "cpf": CPF_ALUNO_TESTE,
                    "dataNascimento": "2099-01-01",
                    "necessidadeEspecial": False,
                },
                headers=headers_admin,
            )
            if not await check(
                "rejeita data de nascimento futura com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /alunos com turmaId inválida (deve retornar 422 sem criar usuário)")
            res = await client.post(
                "/alunos",
                json={
                    "nome": "Aluno Turma Falsa",
                    "cpf": CPF_ALUNO_TESTE,
                    "dataNascimento": "2008-04-15",
                    "necessidadeEspecial": False,
                    "turmaId": "id-de-turma-que-nao-existe",
                },
                headers=headers_admin,
            )
            if not await check(
                "rejeita turmaId inválida com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            usuario_orfao = await db.usuario.find_unique(where={"cpf": CPF_ALUNO_TESTE})
            if not await check(
                "rollback funcionou — nenhum Usuario foi criado",
                usuario_orfao is None,
                f"usuário órfão encontrado: {usuario_orfao.id if usuario_orfao else 'nenhum'}",
            ):
                failed += 1

            print("\n→ POST /alunos válido com vínculo de turma (Card 4)")
            res = await client.post(
                "/alunos",
                json={
                    "nome": "Aluno Smoke Test",
                    "cpf": CPF_ALUNO_TESTE,
                    "dataNascimento": DATA_NASC_TESTE.isoformat(),
                    "necessidadeEspecial": False,
                    "turmaId": turma_id,
                },
                headers=headers_admin,
            )
            if not await check(
                "criação retorna 201",
                res.status_code == 201,
                f"status: {res.status_code} body: {res.text[:200]}",
            ):
                failed += 1
                return failed

            aluno_data = res.json()
            senha_esperada = DATA_NASC_TESTE.strftime("%d%m%Y")
            await check(
                "senha provisória retornada é ddmmaaaa da data de nascimento",
                aluno_data["senhaProvisoria"] == senha_esperada,
                f"esperado: {senha_esperada} | recebido: {aluno_data.get('senhaProvisoria')}",
            )

            usuario_criado = await db.usuario.find_unique(where={"cpf": CPF_ALUNO_TESTE})
            await check(
                "Usuario criado tem senhaProvisoria=true",
                usuario_criado.senhaProvisoria is True,
            )

            vinculos = await db.turmaaluno.count(
                where={"turmaId": turma_id, "saiuEm": None}
            )
            await check(
                "TurmaAluno vinculado (totalAlunos=1)",
                vinculos == 1,
                f"vinculos: {vinculos}",
            )

            print("\n→ Login do aluno recém-cadastrado com a senha provisória")
            res = await client.post(
                "/auth/login",
                json={"cpf": CPF_ALUNO_TESTE, "senha": senha_esperada},
            )
            if not await check(
                "aluno consegue logar com ddmmaaaa",
                res.status_code == 200,
                f"status: {res.status_code}",
            ):
                failed += 1
            else:
                login_data = res.json()
                await check(
                    "login retorna requer_troca_senha=true",
                    login_data.get("requer_troca_senha") is True,
                )

            print("\n→ POST /alunos com CPF duplicado (deve retornar 409)")
            res = await client.post(
                "/alunos",
                json={
                    "nome": "Aluno Duplicado",
                    "cpf": CPF_ALUNO_TESTE,
                    "dataNascimento": "2008-04-15",
                    "necessidadeEspecial": False,
                },
                headers=headers_admin,
            )
            if not await check(
                "rejeita CPF duplicado com 409",
                res.status_code == 409,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ GET /turmas — turma criada deve aparecer com totalAlunos=1")
            res = await client.get("/turmas", headers=headers_admin)
            if not await check("listagem retorna 200", res.status_code == 200):
                failed += 1
            else:
                turmas = res.json()
                turma_listada = next(
                    (t for t in turmas if t["id"] == turma_id), None
                )
                await check(
                    "turma de teste aparece na lista com totalAlunos=1",
                    turma_listada is not None and turma_listada.get("totalAlunos") == 1,
                    f"totalAlunos: {turma_listada.get('totalAlunos') if turma_listada else 'turma ausente'}",
                )

            print("\n→ GET /alunos?turma_id=...")
            res = await client.get(
                "/alunos",
                params={"turma_id": turma_id},
                headers=headers_admin,
            )
            if not await check("listagem por turma retorna 200", res.status_code == 200):
                failed += 1
            else:
                alunos = res.json()
                await check(
                    "filtro por turma retorna o aluno cadastrado",
                    len(alunos) == 1 and alunos[0]["cpf"] == CPF_ALUNO_TESTE,
                    f"alunos retornados: {len(alunos)}",
                )

        print()
        if failed == 0:
            print("\033[32m=== TODOS OS CHECKS PASSARAM ✓ ===\033[0m\n")
        else:
            print(f"\033[31m=== {failed} CHECK(S) FALHARAM ✗ ===\033[0m\n")

        return 0 if failed == 0 else 1

    finally:
        try:
            await cleanup_artefatos_teste(db)
            print("→ Artefatos de teste removidos")
        except Exception as e:
            print(f"⚠ Falha ao limpar artefatos: {e}")
        await db.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))