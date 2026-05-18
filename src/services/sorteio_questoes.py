import asyncio

from src.database import db


async def contar_disponiveis(componente_id: str) -> dict[str, int]:
    facil_task = db.questao.count(
        where={
            "componenteId": componente_id,
            "dificuldade": "FACIL",
            "ativa": True,
        }
    )
    medio_task = db.questao.count(
        where={
            "componenteId": componente_id,
            "dificuldade": "MEDIO",
            "ativa": True,
        }
    )
    dificil_task = db.questao.count(
        where={
            "componenteId": componente_id,
            "dificuldade": "DIFICIL",
            "ativa": True,
        }
    )

    facil, medio, dificil = await asyncio.gather(facil_task, medio_task, dificil_task)

    return {"facil": facil, "medio": medio, "dificil": dificil}


async def verificar_disponibilidade(
    componente_id: str,
    qtd_facil: int,
    qtd_medio: int,
    qtd_dificil: int,
) -> tuple[bool, list[str]]:
    disponiveis = await contar_disponiveis(componente_id)

    faltas: list[str] = []

    if qtd_facil > disponiveis["facil"]:
        faltam = qtd_facil - disponiveis["facil"]
        faltas.append(
            f"Faltam {faltam} questões fáceis no banco "
            f"(pediu {qtd_facil}, há {disponiveis['facil']} disponíveis)"
        )

    if qtd_medio > disponiveis["medio"]:
        faltam = qtd_medio - disponiveis["medio"]
        faltas.append(
            f"Faltam {faltam} questões médias no banco "
            f"(pediu {qtd_medio}, há {disponiveis['medio']} disponíveis)"
        )

    if qtd_dificil > disponiveis["dificil"]:
        faltam = qtd_dificil - disponiveis["dificil"]
        faltas.append(
            f"Faltam {faltam} questões difíceis no banco "
            f"(pediu {qtd_dificil}, há {disponiveis['dificil']} disponíveis)"
        )

    return (len(faltas) == 0, faltas)