import asyncio
import random

from fastapi import HTTPException

from src.database import db
from src.services import questions_api

DIFICULDADES = ["FACIL", "MEDIO", "DIFICIL"]


async def _subject_slug(componente_id: str) -> str:
    componente = await db.componentecurricular.find_unique(
        where={"id": componente_id}
    )
    if not componente:
        raise HTTPException(status_code=422, detail="Componente curricular não encontrado")
    slug = getattr(componente, "questionsSubjectSlug", None)
    if not slug:
        raise HTTPException(
            status_code=422,
            detail="Componente não está vinculado a uma matéria da API de questões",
        )
    return slug


async def contar_disponiveis(componente_id: str) -> dict[str, int]:
    slug = await _subject_slug(componente_id)

    facil, medio, dificil = await asyncio.gather(
        questions_api.contar_questoes(slug, "FACIL"),
        questions_api.contar_questoes(slug, "MEDIO"),
        questions_api.contar_questoes(slug, "DIFICIL"),
    )

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


def _serializar_questao(questao_api: dict, ordem: int) -> dict:
    alternativas, letra_correta = questions_api.montar_alternativas(questao_api)
    return {
        "ordem": ordem,
        "questaoId": questao_api.get("id"),
        "enunciado": questao_api.get("title", ""),
        "urlImagem": questao_api.get("imageUrl"),
        "alternativas": alternativas,
        "respostaCorreta": letra_correta,
    }


async def montar_questoes_selecionadas(
    componente_id: str,
    questao_ids: list[str],
) -> list[dict]:
    slug = await _subject_slug(componente_id)
    questoes = await questions_api.buscar_questoes_por_ids(slug, questao_ids)
    random.shuffle(questoes)
    return [_serializar_questao(q, ordem) for ordem, q in enumerate(questoes, start=1)]


async def sortear_questoes_para_prova(
    componente_id: str,
    qtd_facil: int,
    qtd_medio: int,
    qtd_dificil: int,
) -> list[dict]:
    slug = await _subject_slug(componente_id)

    faceis, medias, dificeis = await asyncio.gather(
        questions_api.listar_questoes(slug, "FACIL"),
        questions_api.listar_questoes(slug, "MEDIO"),
        questions_api.listar_questoes(slug, "DIFICIL"),
    )

    if qtd_facil > len(faceis) or qtd_medio > len(medias) or qtd_dificil > len(dificeis):
        raise HTTPException(
            status_code=422,
            detail="Banco de questões insuficiente para a composição solicitada",
        )

    selecionadas = (
        random.sample(faceis, qtd_facil)
        + random.sample(medias, qtd_medio)
        + random.sample(dificeis, qtd_dificil)
    )

    random.shuffle(selecionadas)

    return [_serializar_questao(q, ordem) for ordem, q in enumerate(selecionadas, start=1)]


# --- Versões multi-componente (etapa estilo ENEM com vários componentes) ---


async def _subject_slugs(componente_ids: list[str]) -> list[str]:
    """Resolve os slugs da API de questões de todos os componentes da etapa."""
    componentes = await db.componentecurricular.find_many(
        where={"id": {"in": componente_ids}}
    )
    slugs: list[str] = []
    for componente in componentes:
        slug = getattr(componente, "questionsSubjectSlug", None)
        if slug and slug not in slugs:
            slugs.append(slug)
    if not slugs:
        raise HTTPException(
            status_code=422,
            detail="Nenhum componente da etapa está vinculado a uma matéria da API de questões",
        )
    return slugs


def _dedup_por_id(questoes: list[dict]) -> list[dict]:
    vistos: dict[str, dict] = {}
    for q in questoes:
        qid = q.get("id")
        if qid is not None and qid not in vistos:
            vistos[qid] = q
    return list(vistos.values())


async def _pools_por_dificuldade(
    slugs: list[str],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Junta as questões de todos os slugs por dificuldade, sem duplicar por id."""
    faceis: list[dict] = []
    medias: list[dict] = []
    dificeis: list[dict] = []
    for slug in slugs:
        f, m, d = await asyncio.gather(
            questions_api.listar_questoes(slug, "FACIL"),
            questions_api.listar_questoes(slug, "MEDIO"),
            questions_api.listar_questoes(slug, "DIFICIL"),
        )
        faceis += f
        medias += m
        dificeis += d
    return _dedup_por_id(faceis), _dedup_por_id(medias), _dedup_por_id(dificeis)


async def verificar_disponibilidade_multi(
    componente_ids: list[str],
    qtd_facil: int,
    qtd_medio: int,
    qtd_dificil: int,
) -> tuple[bool, list[str]]:
    slugs = await _subject_slugs(componente_ids)
    faceis, medias, dificeis = await _pools_por_dificuldade(slugs)

    faltas: list[str] = []
    if qtd_facil > len(faceis):
        faltas.append(
            f"Faltam questões fáceis no banco "
            f"(pediu {qtd_facil}, há {len(faceis)} disponíveis)"
        )
    if qtd_medio > len(medias):
        faltas.append(
            f"Faltam questões médias no banco "
            f"(pediu {qtd_medio}, há {len(medias)} disponíveis)"
        )
    if qtd_dificil > len(dificeis):
        faltas.append(
            f"Faltam questões difíceis no banco "
            f"(pediu {qtd_dificil}, há {len(dificeis)} disponíveis)"
        )
    return (len(faltas) == 0, faltas)


async def sortear_questoes_para_prova_multi(
    componente_ids: list[str],
    qtd_facil: int,
    qtd_medio: int,
    qtd_dificil: int,
) -> list[dict]:
    slugs = await _subject_slugs(componente_ids)
    faceis, medias, dificeis = await _pools_por_dificuldade(slugs)

    if qtd_facil > len(faceis) or qtd_medio > len(medias) or qtd_dificil > len(dificeis):
        raise HTTPException(
            status_code=422,
            detail="Banco de questões insuficiente para a composição solicitada",
        )

    selecionadas = (
        random.sample(faceis, qtd_facil)
        + random.sample(medias, qtd_medio)
        + random.sample(dificeis, qtd_dificil)
    )
    random.shuffle(selecionadas)
    return [_serializar_questao(q, ordem) for ordem, q in enumerate(selecionadas, start=1)]


async def montar_questoes_selecionadas_multi(
    componente_ids: list[str],
    questao_ids: list[str],
) -> list[dict]:
    slugs = await _subject_slugs(componente_ids)
    encontradas: dict[str, dict] = {}
    for slug in slugs:
        for q in await questions_api.buscar_questoes_por_ids(slug, questao_ids):
            qid = q.get("id")
            if qid is not None:
                encontradas.setdefault(qid, q)
    # respeita a seleção do admin; ignora ids que não voltaram da API
    questoes = [encontradas[qid] for qid in questao_ids if qid in encontradas]
    random.shuffle(questoes)
    return [_serializar_questao(q, ordem) for ordem, q in enumerate(questoes, start=1)]
