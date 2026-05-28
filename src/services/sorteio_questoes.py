import asyncio
import random
from src.database import db

async def gerar_questoes_simulado(componente_id: str, qtd_facil: int, qtd_medio: int, qtd_dificil: int, componente_ids: list[str] = None):
    ids = componente_ids if componente_ids else [componente_id]
    
    todas_questoes = await db.questao.find_many(
        where={"componenteId": {"in": ids}, "ativa": True},
        include={"assunto": True}
    )
    
    faceis = [q for q in todas_questoes if q.dificuldade == "FACIL"]
    medias = [q for q in todas_questoes if q.dificuldade == "MEDIO"]
    dificeis = [q for q in todas_questoes if q.dificuldade == "DIFICIL"]
    
    sorteadas = (
        random.sample(faceis, min(len(faceis), qtd_facil)) +
        random.sample(medias, min(len(medias), qtd_medio)) +
        random.sample(dificeis, min(len(dificeis), qtd_dificil))
    )
    random.shuffle(sorteadas)
    
    return [
        {
            "id": q.id,
            "enunciado": q.enunciado,
            "dificuldade": q.dificuldade,
            "assunto": q.assunto.nome if q.assunto else "",
            "alternativas": q.alternativas,
        }
        for q in sorteadas
    ]


async def contar_disponiveis(componente_id: str) -> dict[str, int]:
    return await contar_disponiveis_multiplos([componente_id])


async def contar_disponiveis_multiplos(componente_ids: list[str]) -> dict[str, int]:
    facil_task = db.questao.count(
        where={"componenteId": {"in": componente_ids}, "dificuldade": "FACIL", "ativa": True}
    )
    medio_task = db.questao.count(
        where={"componenteId": {"in": componente_ids}, "dificuldade": "MEDIO", "ativa": True}
    )
    dificil_task = db.questao.count(
        where={"componenteId": {"in": componente_ids}, "dificuldade": "DIFICIL", "ativa": True}
    )

    facil, medio, dificil = await asyncio.gather(facil_task, medio_task, dificil_task)
    return {"facil": facil, "medio": medio, "dificil": dificil}


async def verificar_disponibilidade(
    componente_id: str, qtd_facil: int, qtd_medio: int, qtd_dificil: int,
    componente_ids: list[str] = None
) -> tuple[bool, list[str]]:
    ids = componente_ids if componente_ids else [componente_id]
    disponiveis = await contar_disponiveis_multiplos(ids)
    faltas: list[str] = []

    if qtd_facil > disponiveis["facil"]:
        faltas.append(f"Faltam {qtd_facil - disponiveis['facil']} questões fáceis no banco (pediu {qtd_facil}, há {disponiveis['facil']} disponíveis)")
    if qtd_medio > disponiveis["medio"]:
        faltas.append(f"Faltam {qtd_medio - disponiveis['medio']} questões médias no banco (pediu {qtd_medio}, há {disponiveis['medio']} disponíveis)")
    if qtd_dificil > disponiveis["dificil"]:
        faltas.append(f"Faltam {qtd_dificil - disponiveis['dificil']} questões difíceis no banco (pediu {qtd_dificil}, há {disponiveis['dificil']} disponíveis)")

    return (len(faltas) == 0, faltas)