import random

import httpx
from fastapi import HTTPException

from src.security import settings

DIFICULDADE_PROVAS_PARA_API = {
    "FACIL": "easy",
    "MEDIO": "medium",
    "DIFICIL": "hard",
}

LETRAS = ["A", "B", "C", "D", "E"]

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _base_url() -> str:
    return settings.QUESTIONS_API_BASE_URL.rstrip("/")


async def _get(path: str, params: dict) -> dict:
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resposta = await client.get(url, params=params)
            resposta.raise_for_status()
            return resposta.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao consultar a API de questões: {exc}",
        )


async def contar_questoes(subject_slug: str, dificuldade: str) -> int:
    dificuldade_api = DIFICULDADE_PROVAS_PARA_API[dificuldade]
    dados = await _get(
        "/questions",
        {"subject": subject_slug, "difficulty": dificuldade_api, "limit": 1, "page": 1},
    )
    return int(dados.get("total", 0))


async def listar_questoes(subject_slug: str, dificuldade: str) -> list[dict]:
    dificuldade_api = DIFICULDADE_PROVAS_PARA_API[dificuldade]
    dados = await _get(
        "/questions",
        {"subject": subject_slug, "difficulty": dificuldade_api},
    )
    return dados.get("data", [])


async def buscar_questoes_por_ids(subject_slug: str, ids: list[str]) -> list[dict]:
    desejados = set(ids)
    encontradas: list[dict] = []
    for dificuldade in DIFICULDADE_PROVAS_PARA_API:
        if not desejados:
            break
        pool = await listar_questoes(subject_slug, dificuldade)
        for questao in pool:
            if questao.get("id") in desejados:
                encontradas.append(questao)
                desejados.discard(questao.get("id"))
    return encontradas


def montar_alternativas(questao_api: dict) -> tuple[list[dict], str]:
    correta = (questao_api.get("correctAnswer") or "").strip()
    incorretas = [str(a).strip() for a in (questao_api.get("incorrectAnswers") or [])]

    textos = [correta, *incorretas]
    random.shuffle(textos)

    alternativas: list[dict] = []
    letra_correta = "A"
    for i, texto in enumerate(textos):
        if i >= len(LETRAS):
            break
        letra = LETRAS[i]
        alternativas.append({"letra": letra, "texto": texto})
        if texto == correta:
            letra_correta = letra

    return alternativas, letra_correta
