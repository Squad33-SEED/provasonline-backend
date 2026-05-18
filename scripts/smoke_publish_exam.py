import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


BACKEND_URL = "http://localhost:3333"

ADMIN_CPF = "12345678909"
ADMIN_SENHA = "admin123"
ALUNO_DEMO_CPF = "11122233396"

TITULO_TESTE = "Smoke Test — Diagnóstica Mat. 2026"


async def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = "✓" if condition else "✗"
    color_open = "\033[32m" if condition else "\033[31m"
    color_close = "\033[0m"
    print(f"  {color_open}{icon}{color_close} {label}{(' — ' + detail) if detail else ''}")
    return condition


async def login(client: httpx.AsyncClient, cpf: str, senha: str) -> str:
    res = await client.post("/auth/login", json={"cpf": cpf, "senha": senha})
    if res.status_code != 200:
        raise RuntimeError(
            f"Falha no login (cpf={cpf}, status={res.status_code}). "
            f"Reinicie o backend para zerar rate-limit."
        )
    return res.json()["access_token"]


async def cleanup(db: Prisma) -> None:
    simulados = await db.simulado.find_many(where={"titulo": {"contains": "Smoke Test"}})
    for s in simulados:
        await db.simulado.delete(where={"id": s.id})


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SMOKE TEST — Lote 3A (Card 5 — Backend) ===\n")
    failed = 0
    simulado_id = None

    try:
        await cleanup(db)

        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15.0) as client:
            print("→ Login do admin (Ricardo)")
            token_admin = await login(client, ADMIN_CPF, ADMIN_SENHA)
            await check("token de admin obtido", bool(token_admin))
            headers_admin = {"Authorization": f"Bearer {token_admin}"}

            print("\n→ GET /catalogo/componentes")
            res = await client.get("/catalogo/componentes", headers=headers_admin)
            if not await check(
                "listagem de componentes retorna 200",
                res.status_code == 200,
                f"status: {res.status_code}",
            ):
                failed += 1
                return failed

            componentes = res.json()
            await check(
                "lista de componentes não está vazia",
                len(componentes) > 0,
                f"total: {len(componentes)}",
            )

            componente_matematica = next(
                (
                    c for c in componentes
                    if c["nome"] == "Matemática"
                    and "Médio" in c["modalidade"]["nome"]
                    and "Regular" in c["modalidade"]["nome"]
                ),
                None,
            )
            if not componente_matematica:
                print("   ✗ Componente 'Matemática' não encontrado. Rode seed_catalogo.py antes.")
                return failed + 1

            componente_id = componente_matematica["id"]
            await check(
                "componente tem modalidade aninhada",
                "modalidade" in componente_matematica
                and "nome" in componente_matematica["modalidade"],
            )

            print(f"\n→ GET /simulados/disponibilidade?componenteId={componente_id[:12]}…")
            res = await client.get(
                "/simulados/disponibilidade",
                params={"componenteId": componente_id},
                headers=headers_admin,
            )
            if not await check("disponibilidade retorna 200", res.status_code == 200):
                failed += 1

            disp = res.json()
            await check(
                "response inclui contadores facil/medio/dificil",
                all(k in disp for k in ["facil", "medio", "dificil"]),
                f"recebido: {disp}",
            )
            await check(
                "todas as 3 dificuldades têm pelo menos 3 questões",
                disp["facil"] >= 3 and disp["medio"] >= 3 and disp["dificil"] >= 3,
                f"F:{disp['facil']} M:{disp['medio']} D:{disp['dificil']} "
                "(rode seed_questoes_demo.py se faltar)",
            )

            print("\n→ GET /simulados/disponibilidade com componenteId inválido")
            res = await client.get(
                "/simulados/disponibilidade",
                params={"componenteId": "id-que-nao-existe"},
                headers=headers_admin,
            )
            if not await check(
                "rejeita componenteId inválido com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /simulados com configuração válida")
            agora = datetime.now(timezone.utc)
            inicio = (agora + timedelta(days=7)).replace(microsecond=0)
            fim = (agora + timedelta(days=14)).replace(microsecond=0)

            payload_valido = {
                "titulo": TITULO_TESTE,
                "descricao": "Avaliação de smoke test",
                "componenteId": componente_id,
                "qtdFacil": 3,
                "qtdMedio": 3,
                "qtdDificil": 2,
                "vagas": 50,
                "duracaoMinutos": 90,
                "janelaInicio": inicio.isoformat(),
                "janelaFim": fim.isoformat(),
            }

            res = await client.post(
                "/simulados", json=payload_valido, headers=headers_admin
            )
            if not await check(
                "criação retorna 201",
                res.status_code == 201,
                f"status: {res.status_code} body: {res.text[:200]}",
            ):
                failed += 1
                return failed

            simulado = res.json()
            simulado_id = simulado["id"]
            await check(
                "response inclui status='PUBLICADO'",
                simulado.get("status") == "PUBLICADO",
                f"status recebido: {simulado.get('status')}",
            )
            await check(
                "response tem componente aninhado com modalidade",
                "componente" in simulado and "modalidade" in simulado["componente"],
            )
            await check(
                "totalQuestoes calculado corretamente",
                simulado.get("totalQuestoes") == 8,
                f"recebido: {simulado.get('totalQuestoes')} (esperado 8)",
            )

            print("\n→ POST /simulados pedindo mais questões do que existe")
            payload_inviavel = {**payload_valido, "qtdFacil": 999}
            payload_inviavel["titulo"] = "Smoke Test — Inviável"
            res = await client.post(
                "/simulados", json=payload_inviavel, headers=headers_admin
            )
            if not await check(
                "rejeita config inviável com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1
            else:
                detail = res.json().get("detail", "")
                await check(
                    "mensagem indica quantas questões faltam",
                    "Faltam" in str(detail) and "fáceis" in str(detail).lower(),
                    f"detail: {str(detail)[:150]}",
                )

            print("\n→ POST /simulados com janelaInicio no passado")
            payload_passado = {
                **payload_valido,
                "janelaInicio": (agora - timedelta(days=1)).isoformat(),
                "janelaFim": (agora + timedelta(days=7)).isoformat(),
                "titulo": "Smoke Test — Passado",
            }
            res = await client.post(
                "/simulados", json=payload_passado, headers=headers_admin
            )
            if not await check(
                "rejeita janela no passado com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /simulados com janelaInicio >= janelaFim")
            payload_invertido = {
                **payload_valido,
                "janelaInicio": fim.isoformat(),
                "janelaFim": inicio.isoformat(),
                "titulo": "Smoke Test — Invertida",
            }
            res = await client.post(
                "/simulados", json=payload_invertido, headers=headers_admin
            )
            if not await check(
                "rejeita janela invertida com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /simulados com componenteId inválido")
            payload_componente = {
                **payload_valido,
                "componenteId": "id-que-nao-existe",
                "titulo": "Smoke Test — Componente Falso",
            }
            res = await client.post(
                "/simulados", json=payload_componente, headers=headers_admin
            )
            if not await check(
                "rejeita componenteId inválido com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /simulados com duracao=5 (menor que mínimo de 15)")
            payload_curto = {
                **payload_valido,
                "duracaoMinutos": 5,
                "titulo": "Smoke Test — Duração Curta",
            }
            res = await client.post(
                "/simulados", json=payload_curto, headers=headers_admin
            )
            if not await check(
                "rejeita duração < 15min com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /simulados com qtdFacil=0, qtdMedio=0, qtdDificil=0")
            payload_zerado = {
                **payload_valido,
                "qtdFacil": 0,
                "qtdMedio": 0,
                "qtdDificil": 0,
                "titulo": "Smoke Test — Zerado",
            }
            res = await client.post(
                "/simulados", json=payload_zerado, headers=headers_admin
            )
            if not await check(
                "rejeita configuração zerada com 422",
                res.status_code == 422,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ POST /simulados sem ser ADMIN (deve retornar 403)")
            token_aluno = await login(client, ALUNO_DEMO_CPF, ADMIN_SENHA)
            res = await client.post(
                "/simulados",
                json=payload_valido,
                headers={"Authorization": f"Bearer {token_aluno}"},
            )
            if not await check(
                "ALUNO recebe 403 ao tentar publicar",
                res.status_code == 403,
                f"status: {res.status_code}",
            ):
                failed += 1

            print("\n→ GET /simulados — etapa criada deve aparecer")
            res = await client.get("/simulados", headers=headers_admin)
            if not await check("listagem retorna 200", res.status_code == 200):
                failed += 1
            else:
                lista = res.json()
                criada = next((s for s in lista if s["id"] == simulado_id), None)
                await check(
                    "etapa de teste aparece na listagem",
                    criada is not None,
                    f"total na lista: {len(lista)}",
                )

        print()
        if failed == 0:
            print("\033[32m=== TODOS OS CHECKS PASSARAM ✓ ===\033[0m\n")
        else:
            print(f"\033[31m=== {failed} CHECK(S) FALHARAM ✗ ===\033[0m\n")

        return 0 if failed == 0 else 1

    finally:
        try:
            await cleanup(db)
            print("→ Artefatos de teste removidos")
        except Exception as e:
            print(f"⚠ Falha ao limpar: {e}")
        await db.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))