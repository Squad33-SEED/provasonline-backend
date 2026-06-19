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

    pools_por_componente: list[dict[str, list[dict]]] = []

    for slug in slugs:
        faceis, medias, dificeis = await _pools_por_dificuldade([slug])

        random.shuffle(faceis)
        random.shuffle(medias)
        random.shuffle(dificeis)

        pools_por_componente.append(
            {
                "FACIL": faceis,
                "MEDIO": medias,
                "DIFICIL": dificeis,
            }
        )

    todas_faceis = _dedup_por_id(
        [q for pools in pools_por_componente for q in pools["FACIL"]]
    )
    todas_medias = _dedup_por_id(
        [q for pools in pools_por_componente for q in pools["MEDIO"]]
    )
    todas_dificeis = _dedup_por_id(
        [q for pools in pools_por_componente for q in pools["DIFICIL"]]
    )

    if (
        qtd_facil > len(todas_faceis)
        or qtd_medio > len(todas_medias)
        or qtd_dificil > len(todas_dificeis)
    ):
        raise HTTPException(
            status_code=422,
            detail="Banco de questões insuficiente para a composição solicitada",
        )

    def sortear_por_rodizio(dificuldade: str, quantidade: int) -> list[dict]:
        if quantidade <= 0:
            return []

        selecionadas: list[dict] = []
        ids_usados: set[str] = set()

        while len(selecionadas) < quantidade:
            adicionou_na_rodada = False

            for pools in pools_por_componente:
                if len(selecionadas) >= quantidade:
                    break

                pool = pools[dificuldade]

                while pool:
                    questao = pool.pop(0)
                    qid = str(questao.get("id"))

                    if qid not in ids_usados:
                        selecionadas.append(questao)
                        ids_usados.add(qid)
                        adicionou_na_rodada = True
                        break

            if not adicionou_na_rodada:
                break

        return selecionadas

    selecionadas = (
        sortear_por_rodizio("FACIL", qtd_facil)
        + sortear_por_rodizio("MEDIO", qtd_medio)
        + sortear_por_rodizio("DIFICIL", qtd_dificil)
    )

    random.shuffle(selecionadas)

    return [
        _serializar_questao(q, ordem)
        for ordem, q in enumerate(selecionadas, start=1)
    ]

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


# --- Composição POR componente (cotas F/M/D específicas de cada componente) ---


async def _slug_e_nome_por_componente(
    componente_ids: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    componentes = await db.componentecurricular.find_many(
        where={"id": {"in": componente_ids}}
    )
    slug_map: dict[str, str] = {}
    nome_map: dict[str, str] = {}
    for c in componentes:
        slug = getattr(c, "questionsSubjectSlug", None)
        if not slug:
            raise HTTPException(
                status_code=422,
                detail=f"O componente '{c.nome}' não está vinculado a uma matéria da API de questões",
            )
        slug_map[c.id] = slug
        nome_map[c.id] = c.nome
    if any(cid not in slug_map for cid in componente_ids):
        raise HTTPException(status_code=422, detail="Componente curricular não encontrado")
    return slug_map, nome_map


def _agregar_por_slug(
    composicao: dict[str, dict], slug_map: dict[str, str]
) -> dict[str, dict[str, int]]:
    """Soma as cotas por slug (componentes que mapeiam à mesma disciplina dividem o pool)."""
    agg: dict[str, dict[str, int]] = {}
    for cid, q in composicao.items():
        slug = slug_map[cid]
        a = agg.setdefault(slug, {"FACIL": 0, "MEDIO": 0, "DIFICIL": 0})
        a["FACIL"] += int(q.get("facil", 0))
        a["MEDIO"] += int(q.get("medio", 0))
        a["DIFICIL"] += int(q.get("dificil", 0))
    return agg


async def verificar_disponibilidade_composicao(
    composicao: dict[str, dict],
) -> tuple[bool, list[str]]:
    componente_ids = list(composicao.keys())
    slug_map, nome_map = await _slug_e_nome_por_componente(componente_ids)
    agg = _agregar_por_slug(composicao, slug_map)

    faltas: list[str] = []
    for slug, q in agg.items():
        f, m, d = await asyncio.gather(
            questions_api.contar_questoes(slug, "FACIL"),
            questions_api.contar_questoes(slug, "MEDIO"),
            questions_api.contar_questoes(slug, "DIFICIL"),
        )
        nomes = ", ".join(
            sorted({nome_map[cid] for cid in componente_ids if slug_map[cid] == slug})
        )
        if q["FACIL"] > f:
            faltas.append(f"{nomes}: faltam fáceis (pediu {q['FACIL']}, há {f})")
        if q["MEDIO"] > m:
            faltas.append(f"{nomes}: faltam médias (pediu {q['MEDIO']}, há {m})")
        if q["DIFICIL"] > d:
            faltas.append(f"{nomes}: faltam difíceis (pediu {q['DIFICIL']}, há {d})")
    return (len(faltas) == 0, faltas)


async def sortear_por_componente(composicao: dict[str, dict]) -> list[dict]:
    componente_ids = list(composicao.keys())
    slug_map, _ = await _slug_e_nome_por_componente(componente_ids)
    agg = _agregar_por_slug(composicao, slug_map)

    selecionadas: list[dict] = []
    for slug, q in agg.items():
        faceis, medias, dificeis = await asyncio.gather(
            questions_api.listar_questoes(slug, "FACIL"),
            questions_api.listar_questoes(slug, "MEDIO"),
            questions_api.listar_questoes(slug, "DIFICIL"),
        )
        faceis = _dedup_por_id(faceis)
        medias = _dedup_por_id(medias)
        dificeis = _dedup_por_id(dificeis)
        if q["FACIL"] > len(faceis) or q["MEDIO"] > len(medias) or q["DIFICIL"] > len(dificeis):
            raise HTTPException(
                status_code=422,
                detail="Banco de questões insuficiente para a composição solicitada",
            )
        selecionadas += random.sample(faceis, q["FACIL"])
        selecionadas += random.sample(medias, q["MEDIO"])
        selecionadas += random.sample(dificeis, q["DIFICIL"])

    selecionadas = _dedup_por_id(selecionadas)
    random.shuffle(selecionadas)
    return [_serializar_questao(q, ordem) for ordem, q in enumerate(selecionadas, start=1)]
