import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma

from src.security import verify_password


EXPECTED_NIVEIS = 2
EXPECTED_MODALIDADES = 4
EXPECTED_COMPONENTES_MIN = 10
EXPECTED_ASSUNTOS_MIN = 25
EXPECTED_ESCOLAS = 3
EXPECTED_CONTAS_DEMO = 3


async def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = "✓" if condition else "✗"
    color_open = "\033[32m" if condition else "\033[31m"
    color_close = "\033[0m"
    print(f"  {color_open}{icon}{color_close} {label}{(' — ' + detail) if detail else ''}")
    return condition


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SMOKE TEST — Lote 0 (Cards 0 e 1) ===\n")

    failed = 0

    print("→ Catálogo")
    n_niveis = await db.nivelensino.count()
    if not await check(f"{EXPECTED_NIVEIS} níveis de ensino", n_niveis == EXPECTED_NIVEIS, f"encontrados: {n_niveis}"):
        failed += 1

    n_mod = await db.modalidade.count()
    if not await check(f"{EXPECTED_MODALIDADES} modalidades", n_mod == EXPECTED_MODALIDADES, f"encontradas: {n_mod}"):
        failed += 1

    n_comp = await db.componentecurricular.count()
    if not await check(f"≥{EXPECTED_COMPONENTES_MIN} componentes curriculares", n_comp >= EXPECTED_COMPONENTES_MIN, f"encontrados: {n_comp}"):
        failed += 1

    n_assuntos = await db.assunto.count()
    if not await check(f"≥{EXPECTED_ASSUNTOS_MIN} assuntos", n_assuntos >= EXPECTED_ASSUNTOS_MIN, f"encontrados: {n_assuntos}"):
        failed += 1

    n_escolas = await db.escola.count()
    if not await check(f"{EXPECTED_ESCOLAS} escolas reais de Sergipe", n_escolas == EXPECTED_ESCOLAS, f"encontradas: {n_escolas}"):
        failed += 1

    print()
    print("→ Contas demo")
    cpfs_demo = ["12345678909", "98765432100", "11122233396"]
    for cpf in cpfs_demo:
        usuario = await db.usuario.find_unique(where={"cpf": cpf})
        if not await check(f"usuário CPF {cpf} existe", usuario is not None):
            failed += 1
            continue
        if not await check(
            f"  └─ {usuario.tipo:<9} {usuario.nome} | senhaProvisoria=False",
            usuario.senhaProvisoria is False,
            f"valor atual: {usuario.senhaProvisoria}",
        ):
            failed += 1
        if not await check(
            f"  └─ senha 'admin123' valida",
            verify_password("admin123", usuario.senhaHash),
        ):
            failed += 1

    print()
    print("→ Schema (Card 1)")

    sample_simulado_fields = await db.query_raw(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'simulados'"
    )
    cols = {row["column_name"] for row in sample_simulado_fields}

    expected_new_cols = {"qtd_facil", "qtd_medio", "qtd_dificil", "vagas", "duracao_minutos", "janela_inicio", "janela_fim", "id_componente"}
    missing = expected_new_cols - cols
    if not await check("simulados tem todos os campos novos", not missing, f"faltam: {missing}" if missing else "ok"):
        failed += 1

    if not await check("coluna 'tempo_limite' foi removida de simulados", "tempo_limite" not in cols):
        failed += 1

    tabela_sq = await db.query_raw(
        "SELECT to_regclass('public.simulado_questoes')::text AS exists"
    )
    sq_exists = tabela_sq[0]["exists"] is not None
    if not await check("tabela simulado_questoes foi removida", not sq_exists):
        failed += 1

    tabela_tq = await db.query_raw(
        "SELECT to_regclass('public.tentativa_questoes')::text AS exists"
    )
    tq_exists = tabela_tq[0]["exists"] is not None
    if not await check("tabela tentativa_questoes foi criada", tq_exists):
        failed += 1

    cols_resultados = await db.query_raw(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'resultados_alunos'"
    )
    resultados_cols = {row["column_name"] for row in cols_resultados}
    if not await check("coluna 'respostas' foi removida de resultados_alunos", "respostas" not in resultados_cols):
        failed += 1

    cols_usuarios = await db.query_raw(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'usuarios'"
    )
    usuarios_cols = {row["column_name"] for row in cols_usuarios}
    if not await check("coluna 'senha_provisoria' foi adicionada a usuarios", "senha_provisoria" in usuarios_cols):
        failed += 1

    cols_turmas = await db.query_raw(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'turmas'"
    )
    turmas_cols = {row["column_name"] for row in cols_turmas}
    if not await check("coluna 'id_modalidade' foi adicionada a turmas", "id_modalidade" in turmas_cols):
        failed += 1

    print()
    if failed == 0:
        print("\033[32m=== TODOS OS CHECKS PASSARAM ✓ ===\033[0m\n")
    else:
        print(f"\033[31m=== {failed} CHECK(S) FALHARAM ✗ ===\033[0m\n")

    await db.disconnect()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))