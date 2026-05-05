import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prisma import Prisma


async def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = "✓" if condition else "✗"
    color_open = "\033[32m" if condition else "\033[31m"
    color_close = "\033[0m"
    print(f"  {color_open}{icon}{color_close} {label}{(' — ' + detail) if detail else ''}")
    return condition


async def verificar_model(db: Prisma, nome_model: str, attr_name: str) -> bool:
    try:
        accessor = getattr(db, attr_name, None)
        if accessor is None:
            return await check(
                f"model {nome_model} acessível como db.{attr_name}",
                False,
                "atributo não encontrado no client",
            )
        await accessor.find_first()
        return await check(f"model {nome_model} acessível como db.{attr_name}", True)
    except Exception as e:
        return await check(
            f"model {nome_model} acessível como db.{attr_name}",
            False,
            f"erro: {type(e).__name__}",
        )


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SMOKE TEST — Validação do Schema ===\n")
    failed = 0

    print("→ Models esperados pelos serviços do projeto")
    models_esperados = [
        ("Usuario", "usuario"),
        ("Aluno", "aluno"),
        ("Professor", "professor"),
        ("Escola", "escola"),
        ("Modalidade", "modalidade"),
        ("NivelEnsino", "nivelensino"),
        ("ComponenteCurricular", "componentecurricular"),
        ("Assunto", "assunto"),
        ("Turma", "turma"),
        ("TurmaAluno", "turmaaluno"),
        ("Simulado", "simulado"),
        ("Questao", "questao"),
        ("ResultadoAluno", "resultadoaluno"),
        ("TentativaQuestao", "tentativaquestao"),
        ("TokenAcesso", "tokenacesso"),
        ("LogAcesso", "logacesso"),
    ]

    for nome, attr in models_esperados:
        ok = await verificar_model(db, nome, attr)
        if not ok:
            failed += 1

    print("\n→ Dados base (rodar 'python seed_catalogo.py' se faltar)")

    admin = await db.usuario.find_unique(where={"cpf": "12345678909"})
    if not await check("admin demo (Ricardo, CPF 12345678909) existe", admin is not None):
        failed += 1
    else:
        await check(
            "admin tem tipo='ADMIN'",
            admin.tipo == "ADMIN",
            f"tipo recebido: {admin.tipo}",
        )

    professor_user = await db.usuario.find_unique(where={"cpf": "98765432100"})
    if not await check(
        "professor demo (Ana Paula, CPF 98765432100) existe",
        professor_user is not None,
    ):
        failed += 1
    else:
        await check(
            "professor tem tipo='PROFESSOR'",
            professor_user.tipo == "PROFESSOR",
            f"tipo recebido: {professor_user.tipo}",
        )

        try:
            professor_record = await db.professor.find_unique(
                where={"usuarioId": professor_user.id}
            )
            ok = await check(
                "registro Professor vinculado ao Usuario existe",
                professor_record is not None,
                f"professor_id: {professor_record.id if professor_record else 'nenhum'}",
            )
            if not ok:
                failed += 1
        except Exception as e:
            await check(
                "registro Professor vinculado ao Usuario existe",
                False,
                f"erro ao buscar Professor: {type(e).__name__} — verificar campo de relação",
            )
            failed += 1

    aluno_user = await db.usuario.find_unique(where={"cpf": "11122233396"})
    if not await check(
        "aluno demo (Lucas, CPF 11122233396) existe", aluno_user is not None
    ):
        failed += 1

    print("\n→ Catálogo populado")

    total_escolas = await db.escola.count(where={"ativo": True})
    await check(
        "ao menos 1 escola ativa cadastrada",
        total_escolas >= 1,
        f"total: {total_escolas}",
    )

    total_componentes = await db.componentecurricular.count(where={"ativo": True})
    await check(
        "ao menos 1 componente curricular ativo",
        total_componentes >= 1,
        f"total: {total_componentes}",
    )

    total_modalidades = await db.modalidade.count(where={"ativo": True})
    await check(
        "ao menos 1 modalidade ativa",
        total_modalidades >= 1,
        f"total: {total_modalidades}",
    )

    total_assuntos = await db.assunto.count()
    await check(
        "ao menos 1 assunto cadastrado",
        total_assuntos >= 1,
        f"total: {total_assuntos}",
    )

    print("\n→ Estado das questões (afeta o Card 5)")

    total_questoes = await db.questao.count()
    if total_questoes == 0:
        print(
            "  ⚠ Banco sem questões — rodar 'python seed_questoes_demo.py' "
            "para popular antes de testar /simulados"
        )
    else:
        await check(
            "questões populadas no banco",
            total_questoes > 0,
            f"total: {total_questoes}",
        )

        try:
            primeiro = await db.questao.find_first(
                include={"professor": True, "componente": True, "assunto": True}
            )
            if primeiro:
                await check(
                    "questao tem professor vinculado",
                    primeiro.professor is not None,
                )
                await check(
                    "questao tem componente vinculado",
                    primeiro.componente is not None,
                )
                await check(
                    "questao tem assunto vinculado",
                    primeiro.assunto is not None,
                )
                await check(
                    "questao tem dificuldade definida",
                    primeiro.dificuldade in ["FACIL", "MEDIO", "DIFICIL"],
                    f"valor: {primeiro.dificuldade}",
                )
                await check(
                    "questao tem alternativas (JSON)",
                    primeiro.alternativas is not None,
                )
                await check(
                    "questao tem respostaCorreta",
                    bool(primeiro.respostaCorreta)
                    and primeiro.respostaCorreta in ["A", "B", "C", "D", "E"],
                    f"valor: {primeiro.respostaCorreta}",
                )
        except Exception as e:
            await check(
                "questao com relações completas",
                False,
                f"erro ao incluir relações: {type(e).__name__}",
            )
            failed += 1

    print()
    if failed == 0:
        print("\033[32m=== SCHEMA VÁLIDO E DADOS BASE OK ✓ ===\033[0m\n")
    else:
        print(f"\033[31m=== {failed} CHECK(S) FALHARAM ✗ ===\033[0m")
        print("Resolva os problemas acima antes de rodar outros smoke tests.\n")

    await db.disconnect()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))