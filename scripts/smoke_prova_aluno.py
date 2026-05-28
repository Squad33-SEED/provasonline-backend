import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

BACKEND_URL = "http://localhost:3333"
CPF_ALUNO = "11122233396"
CPF_ADMIN = "12345678909"
SENHA = "admin123"

passed = 0
failed = 0


async def check(label: str, condition: bool, detail: str = "") -> bool:
    global passed, failed
    icon = "✓" if condition else "✗"
    color_open = "\033[32m" if condition else "\033[31m"
    color_close = "\033[0m"
    print(f"  {color_open}{icon}{color_close} {label}{(' — ' + detail) if detail else ''}")
    if condition:
        passed += 1
    else:
        failed += 1
    return condition


async def login(client: httpx.AsyncClient, cpf: str, senha: str) -> str:
    r = await client.post("/auth/login", json={"cpf": cpf, "senha": senha})
    if r.status_code != 200:
        print(f"\033[31mFalha no login ({cpf}): {r.status_code} — reinicie o backend para zerar rate-limit\033[0m")
        sys.exit(1)
    return r.json()["access_token"]


async def cleanup(db: Prisma, aluno_id: str) -> None:
    resultados = await db.resultadoaluno.find_many(where={"alunoId": aluno_id})
    for r in resultados:
        await db.tentativaquestao.delete_many(where={"resultadoId": r.id})
        await db.resultadoaluno.delete(where={"id": r.id})


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SMOKE TEST — Lote 4 (Realização de Prova pelo Aluno) ===\n")

    aluno_usuario = await db.usuario.find_unique(where={"cpf": CPF_ALUNO})
    if not aluno_usuario:
        print("✗ Aluno demo não encontrado. Rode seed_catalogo.py antes.")
        await db.disconnect()
        return 1

    aluno = await db.aluno.find_unique(where={"usuarioId": aluno_usuario.id})
    if not aluno:
        print("✗ Registro Aluno não encontrado para o usuário demo.")
        await db.disconnect()
        return 1

    await cleanup(db, aluno.id)

    simulado_ativo = await db.simulado.find_first(
        where={"status": "PUBLICADO"},
        include={"componente": True},
    )
    if not simulado_ativo:
        print("✗ Nenhum simulado PUBLICADO encontrado.")
        print("  Publique uma etapa pelo wizard antes de rodar este smoke test.")
        await db.disconnect()
        return 1

    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc)
    janela_inicio = simulado_ativo.janelaInicio
    janela_fim = simulado_ativo.janelaFim
    if janela_inicio.tzinfo is None:
        janela_inicio = janela_inicio.replace(tzinfo=timezone.utc)
    if janela_fim.tzinfo is None:
        janela_fim = janela_fim.replace(tzinfo=timezone.utc)

    if not (janela_inicio <= agora <= janela_fim):
        print(f"✗ O simulado '{simulado_ativo.titulo}' não está na janela ativa agora.")
        print(f"  Janela: {janela_inicio} → {janela_fim}")
        print("  Publique uma etapa com janelaInicio no passado próximo e janelaFim no futuro.")
        await db.disconnect()
        return 1

    simulado_id = simulado_ativo.id
    total_questoes_esperado = simulado_ativo.qtdFacil + simulado_ativo.qtdMedio + simulado_ativo.qtdDificil

    resultado_id = None

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15.0) as client:
        token_aluno = await login(client, CPF_ALUNO, SENHA)
        token_admin = await login(client, CPF_ADMIN, SENHA)
        h_aluno = {"Authorization": f"Bearer {token_aluno}"}
        h_admin = {"Authorization": f"Bearer {token_admin}"}

        print(f"→ Simulado: '{simulado_ativo.titulo}' (id: {simulado_id[:8]}…)")
        print(f"  Questões esperadas: {total_questoes_esperado}\n")

        print("→ check 1 — POST /aluno/iniciar-prova/{id}")
        r = await client.post(f"/aluno/iniciar-prova/{simulado_id}", headers=h_aluno)
        if not await check(
            "retorna 201",
            r.status_code == 201,
            f"status: {r.status_code} body: {r.text[:200]}",
        ):
            await db.disconnect()
            return 1

        prova = r.json()
        resultado_id = prova.get("resultadoId")
        questoes = prova.get("questoes", [])

        print("\n→ check 2 — campos obrigatórios no response")
        await check(
            "resultadoId presente",
            bool(resultado_id),
        )
        await check(
            "expiraEm presente",
            bool(prova.get("expiraEm")),
        )
        await check(
            "duracaoMinutos presente",
            isinstance(prova.get("duracaoMinutos"), int),
        )

        print("\n→ check 3 — gabarito não exposto ao aluno")
        sem_gabarito = all("respostaCorreta" not in q for q in questoes)
        await check(
            "respostaCorreta ausente em todas as questões",
            sem_gabarito,
            "vazamento de gabarito detectado" if not sem_gabarito else "",
        )

        print("\n→ check 4 — total de questões sorteadas")
        await check(
            f"total={total_questoes_esperado} questões sorteadas",
            len(questoes) == total_questoes_esperado,
            f"recebido: {len(questoes)}",
        )

        print("\n→ check 5 — TentativaQuestao criada no banco")
        tentativas = await db.tentativaquestao.count(where={"resultadoId": resultado_id})
        await check(
            f"{total_questoes_esperado} TentativaQuestao inseridas",
            tentativas == total_questoes_esperado,
            f"encontradas: {tentativas}",
        )

        if not questoes:
            print("✗ Sem questões para continuar os checks de PATCH /responder")
            await db.disconnect()
            return 1

        primeira_questao_id = questoes[0]["questaoId"]

        print("\n→ check 6 — PATCH /responder salva resposta 'A'")
        r = await client.patch(
            f"/aluno/responder/{resultado_id}",
            headers=h_aluno,
            json={"respostas": [{"questaoId": primeira_questao_id, "resposta": "A"}]},
        )
        await check(
            "retorna 200 com salvo=true",
            r.status_code == 200 and r.json().get("salvo") is True,
            r.text[:150] if r.status_code != 200 else "",
        )

        print("\n→ check 7 — PATCH /responder sobrescreve para 'B'")
        r = await client.patch(
            f"/aluno/responder/{resultado_id}",
            headers=h_aluno,
            json={"respostas": [{"questaoId": primeira_questao_id, "resposta": "B"}]},
        )
        await check(
            "retorna 200 e totalSalvas >= 1",
            r.status_code == 200 and r.json().get("totalSalvas", 0) >= 1,
            r.text[:150] if r.status_code != 200 else "",
        )

        tq = await db.tentativaquestao.find_unique(
            where={"resultadoId_questaoId": {"resultadoId": resultado_id, "questaoId": primeira_questao_id}}
        )
        await check(
            "alternativaMarcada='B' persistida em TentativaQuestao",
            tq is not None and tq.alternativaMarcada == "B",
            f"valor no banco: {tq.alternativaMarcada if tq else 'registro ausente'}",
        )

        print("\n→ check 8 — retomada (segundo POST /iniciar-prova)")
        r2 = await client.post(f"/aluno/iniciar-prova/{simulado_id}", headers=h_aluno)
        retomada_ok = (
            r2.status_code in (200, 201)
            and r2.json().get("resultadoId") == resultado_id
        )
        await check(
            "retorna resultado existente com mesmas questões",
            retomada_ok,
            f"status: {r2.status_code}",
        )
        if retomada_ok:
            questoes_retomada = r2.json().get("questoes", [])
            await check(
                "respostaSalva='B' preservada na retomada",
                any(
                    q["questaoId"] == primeira_questao_id and q.get("respostaSalva") == "B"
                    for q in questoes_retomada
                ),
            )

        print("\n→ check 9 — auto-save em lote (todas as questões)")
        todas = [{"questaoId": q["questaoId"], "resposta": "A"} for q in questoes]
        r = await client.patch(
            f"/aluno/responder/{resultado_id}",
            headers=h_aluno,
            json={"respostas": todas},
        )
        await check(
            f"salva {len(todas)} respostas em lote",
            r.status_code == 200 and r.json().get("totalSalvas") == len(todas),
            f"totalSalvas: {r.json().get('totalSalvas') if r.status_code == 200 else r.text[:100]}",
        )

        print("\n→ check 10 — POST /submeter")
        r = await client.post(f"/aluno/submeter/{resultado_id}", headers=h_aluno)
        if not await check("retorna 200", r.status_code == 200, r.text[:200]):
            await db.disconnect()
            return 1

        resultado = r.json()

        print("\n→ check 11 — campos do resultado pós-submissão")
        pontuacao = resultado.get("pontuacao", -1)
        await check(
            f"pontuação entre 0 e 10 (recebido: {pontuacao})",
            0 <= pontuacao <= 10,
        )
        await check(
            "acertos + erros = total",
            resultado.get("acertos", -1) + (resultado.get("total", 0) - resultado.get("acertos", 0)) == resultado.get("total"),
        )
        await check(
            "gabaritoDisponivel=false antes da janelaFim",
            resultado.get("gabaritoDisponivel") is False,
            f"recebido: {resultado.get('gabaritoDisponivel')}",
        )
        await check(
            "gabaritoDisponivelEm presente no response",
            bool(resultado.get("gabaritoDisponivelEm")),
            f"recebido: {resultado.get('gabaritoDisponivelEm')}",
        )
        await check(
            "gabarito=null antes da janelaFim (anti-cola)",
            resultado.get("gabarito") is None,
            f"recebido: {type(resultado.get('gabarito')).__name__}",
        )

        print("\n→ check 12 — StatusResultado=FINALIZADO no banco")
        resultado_db = await db.resultadoaluno.find_unique(where={"id": resultado_id})
        await check(
            "statusResultado='FINALIZADO' persistido",
            resultado_db is not None and resultado_db.statusResultado == "FINALIZADO",
            f"valor: {resultado_db.statusResultado if resultado_db else 'ausente'}",
        )

        print("\n→ check 13 — segundo POST /submeter retorna 409")
        r = await client.post(f"/aluno/submeter/{resultado_id}", headers=h_aluno)
        await check(
            "409 ao submeter prova já finalizada",
            r.status_code == 409,
            f"status: {r.status_code}",
        )

        print("\n→ check 14 — GET /resultado por ADMIN (gabarito sempre disponível)")
        r = await client.get(f"/aluno/resultado/{resultado_id}", headers=h_admin)
        await check(
            "ADMIN lê resultado com simulado.titulo",
            r.status_code == 200 and bool(r.json().get("simulado", {}).get("titulo")),
            r.text[:150] if r.status_code != 200 else "",
        )
        if r.status_code == 200:
            resp_admin = r.json()
            await check(
                "ADMIN recebe gabaritoDisponivel=true",
                resp_admin.get("gabaritoDisponivel") is True,
                f"recebido: {resp_admin.get('gabaritoDisponivel')}",
            )
            gabarito_admin = resp_admin.get("gabarito") or []
            await check(
                f"ADMIN recebe gabarito com {total_questoes_esperado} itens detalhados",
                len(gabarito_admin) == total_questoes_esperado
                and all("enunciado" in g and "alternativaCorreta" in g for g in gabarito_admin),
                f"itens: {len(gabarito_admin)}",
            )

        print("\n→ check 15 — GET /aluno/historico")
        r = await client.get("/aluno/historico", headers=h_aluno)
        await check(
            "retorna 200 com lista de histórico",
            r.status_code == 200 and isinstance(r.json(), list),
            r.text[:150] if r.status_code != 200 else "",
        )
        if r.status_code == 200:
            historico = r.json()
            await check(
                "histórico contém o resultado recém-finalizado",
                any(h.get("resultadoId") == resultado_id for h in historico),
                f"itens no histórico: {len(historico)}",
            )
            if historico:
                item = next((h for h in historico if h.get("resultadoId") == resultado_id), historico[0])
                await check(
                    "histórico contém gabaritoDisponivelEm",
                    bool(item.get("gabaritoDisponivelEm")),
                    f"recebido: {item.get('gabaritoDisponivelEm')}",
                )

    await cleanup(db, aluno.id)
    print("\n→ Artefatos de teste removidos")

    total = passed + failed
    print(f"\n{'─' * 45}")
    if failed == 0:
        print(f"\033[32m=== {passed}/{total} CHECKS PASSARAM — Lote 4 backend OK ✓ ===\033[0m\n")
    else:
        print(f"\033[31m=== {failed}/{total} CHECKS FALHARAM ✗ ===\033[0m\n")

    await db.disconnect()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))