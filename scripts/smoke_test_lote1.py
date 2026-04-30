import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

from src.security import hash_password


BACKEND_URL = "http://localhost:3333"
CPF_TESTE = "55544433322"
SENHA_PROVISORIA = "15032005"
SENHA_NOVA = "Senha@2026"
SENHA_FRACA = "12345"


async def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = "✓" if condition else "✗"
    color_open = "\033[32m" if condition else "\033[31m"
    color_close = "\033[0m"
    print(f"  {color_open}{icon}{color_close} {label}{(' — ' + detail) if detail else ''}")
    return condition


async def setup_usuario_teste(db: Prisma) -> str:
    existing = await db.usuario.find_unique(where={"cpf": CPF_TESTE})
    if existing:
        await db.usuario.update(
            where={"id": existing.id},
            data={
                "senhaHash": hash_password(SENHA_PROVISORIA),
                "senhaProvisoria": True,
                "ativo": True,
            },
        )
        return existing.id

    usuario = await db.usuario.create(
        data={
            "nome": "Aluno Teste Lote 1",
            "cpf": CPF_TESTE,
            "email": None,
            "senhaHash": hash_password(SENHA_PROVISORIA),
            "senhaProvisoria": True,
            "tipo": "ALUNO",
            "ativo": True,
        },
    )
    return usuario.id


async def cleanup_usuario_teste(db: Prisma, usuario_id: str) -> None:
    await db.tokenacesso.delete_many(where={"usuarioId": usuario_id})
    await db.logacesso.delete_many(where={"usuarioId": usuario_id})
    await db.usuario.delete(where={"id": usuario_id})


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SMOKE TEST — Lote 1 (Cards 2 e 6 — Backend) ===\n")
    failed = 0
    usuario_id = None

    try:
        usuario_id = await setup_usuario_teste(db)
        print(f"→ Usuário de teste criado (id={usuario_id[:8]}…)")

        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:
            print("\n→ POST /auth/login com senha provisória")
            res = await client.post(
                "/auth/login",
                json={"cpf": CPF_TESTE, "senha": SENHA_PROVISORIA},
            )
            login_ok = res.status_code == 200
            if not await check(f"status 200 (recebido: {res.status_code})", login_ok):
                failed += 1
                return 1

            data = res.json()
            token_provisorio = data.get("access_token", "")

            if not await check(
                "response inclui 'requer_troca_senha=true'",
                data.get("requer_troca_senha") is True,
                f"valor: {data.get('requer_troca_senha')}",
            ):
                failed += 1
            if not await check("response inclui access_token", bool(token_provisorio)):
                failed += 1

            print("\n→ POST /auth/trocar-senha com senha fraca (deve rejeitar)")
            res = await client.post(
                "/auth/trocar-senha",
                json={"senha_atual": SENHA_PROVISORIA, "senha_nova": SENHA_FRACA},
                headers={"Authorization": f"Bearer {token_provisorio}"},
            )
            if not await check(
                "rejeita senha fraca com 422",
                res.status_code == 422,
                f"status recebido: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /auth/trocar-senha com senha igual à atual (deve rejeitar)")
            res = await client.post(
                "/auth/trocar-senha",
                json={"senha_atual": SENHA_PROVISORIA, "senha_nova": SENHA_PROVISORIA},
                headers={"Authorization": f"Bearer {token_provisorio}"},
            )
            if not await check(
                "rejeita senha igual à atual com 422",
                res.status_code == 422,
                f"status recebido: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /auth/trocar-senha com senha forte válida")
            res = await client.post(
                "/auth/trocar-senha",
                json={"senha_atual": SENHA_PROVISORIA, "senha_nova": SENHA_NOVA},
                headers={"Authorization": f"Bearer {token_provisorio}"},
            )
            if not await check(
                "troca de senha retorna 200",
                res.status_code == 200,
                f"status recebido: {res.status_code}",
            ):
                failed += 1

            usuario = await db.usuario.find_unique(where={"id": usuario_id})
            if not await check(
                "senhaProvisoria virou false no banco",
                usuario.senhaProvisoria is False,
            ):
                failed += 1

            print("\n→ Token antigo deve estar revogado")
            res = await client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token_provisorio}"},
            )
            if not await check(
                "token antigo retorna 401 após troca",
                res.status_code == 401,
                f"status recebido: {res.status_code}",
            ):
                failed += 1

            print("\n→ Login com senha nova")
            res = await client.post(
                "/auth/login",
                json={"cpf": CPF_TESTE, "senha": SENHA_NOVA},
            )

            if res.status_code == 429:
                print("  ⚠ Rate-limit ativo do slowapi — reinicie o backend (Ctrl+C + uvicorn) e rode de novo")
                failed += 1
            elif res.status_code != 200:
                body_preview = res.text[:200] if res.text else "(body vazio)"
                print(f"  ✗ login com senha nova retornou {res.status_code} — body: {body_preview}")
                failed += 1
            else:
                await check("login com senha nova retorna 200", True)
                try:
                    data = res.json()
                    if not await check(
                        "novo login tem requer_troca_senha=false",
                        data.get("requer_troca_senha") is False,
                        f"valor: {data.get('requer_troca_senha')}",
                    ):
                        failed += 1
                except Exception as e:
                    print(f"  ✗ falha ao parsear response: {e}")
                    failed += 1

            print("\n→ Senha errada repetida (rate-limit deve disparar em até 5 tentativas)")
            ultimo_status = 0
            for tentativa in range(1, 8):
                res = await client.post(
                    "/auth/login",
                    json={"cpf": CPF_TESTE, "senha": "senha_errada_x"},
                )
                ultimo_status = res.status_code
                if res.status_code == 429:
                    break
            if not await check(
                "rate-limit dispara com 429 após várias tentativas",
                ultimo_status == 429,
                f"último status: {ultimo_status}",
            ):
                failed += 1

        print()
        if failed == 0:
            print("\033[32m=== TODOS OS CHECKS PASSARAM ✓ ===\033[0m\n")
        else:
            print(f"\033[31m=== {failed} CHECK(S) FALHARAM ✗ ===\033[0m\n")

        return 0 if failed == 0 else 1

    finally:
        if usuario_id:
            try:
                await cleanup_usuario_teste(db, usuario_id)
                print(f"→ Usuário de teste removido")
            except Exception as e:
                print(f"⚠ Falha ao limpar usuário teste: {e}")
        await db.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))