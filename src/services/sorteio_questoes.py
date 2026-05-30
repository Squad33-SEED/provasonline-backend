import asyncio
import random

from src.database import db


async def contar_disponiveis(componente_id: str) -> dict[str, int]:
    facil_task = db.questao.count(
        where={"componenteId": componente_id, "dificuldade": "FACIL", "ativa": True}
    )
    medio_task = db.questao.count(
        where={"componenteId": componente_id, "dificuldade": "MEDIO", "ativa": True}
    )
    dificil_task = db.questao.count(
        where={"componenteId": componente_id, "dificuldade": "DIFICIL", "ativa": True}
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


def embaralhar_alternativas_questao(
    alternativas: list[dict],
    resposta_correta: str,
) -> tuple[list[dict], str]:
    letras = ["A", "B", "C", "D", "E"]
    copia = [dict(a) for a in alternativas]
    random.shuffle(copia)

    resultado: list[dict] = []
    nova_correta = resposta_correta

    for i, alt in enumerate(copia):
        nova_letra = letras[i]
        letra_original = alt.get("letra", "")

        resultado.append({
            "letra": nova_letra,
            "texto": alt.get("texto", ""),
            "letraOriginal": letra_original,
        })

        if letra_original.upper() == resposta_correta.upper():
            nova_correta = nova_letra

    return resultado, nova_correta


async def sortear_questoes_para_prova(
    componente_id: str,
    qtd_facil: int,
    qtd_medio: int,
    qtd_dificil: int,
) -> list[dict]:
    faceis, medias, dificeis = await asyncio.gather(
        db.questao.find_many(
            where={"componenteId": componente_id, "dificuldade": "FACIL", "ativa": True}
        ),
        db.questao.find_many(
            where={"componenteId": componente_id, "dificuldade": "MEDIO", "ativa": True}
        ),
        db.questao.find_many(
            where={"componenteId": componente_id, "dificuldade": "DIFICIL", "ativa": True}
        ),
    )

    selecionadas = (
        random.sample(faceis, qtd_facil)
        + random.sample(medias, qtd_medio)
        + random.sample(dificeis, qtd_dificil)
    )

    random.shuffle(selecionadas)

    resultado = []
    for ordem, questao in enumerate(selecionadas, start=1):
        alternativas_raw = questao.alternativas
        alternativas = (
            [{"letra": a.get("letra", ""), "texto": a.get("texto", "")} for a in alternativas_raw]
            if isinstance(alternativas_raw, list)
            else []
        )
        resultado.append({
            "ordem": ordem,
            "questaoId": questao.id,
            "enunciado": questao.enunciado,
            "alternativas": alternativas,
        })

    return resultado