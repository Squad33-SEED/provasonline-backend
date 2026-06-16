import asyncio
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Json

from src.database import db
from src.dependencies import get_current_user
from src.services import questions_api
from src.services.sorteio_questoes import _pools_por_dificuldade, _subject_slugs
from src.schemas import (
    AlternativaParaAluno,
    DisciplinaSimulado,
    GabaritoSimuladoLivreItem,
    QuestaoBanco,
    QuestaoSimuladoLivre,
    ResultadoSimuladoLivreResponse,
    SimuladoLivreHistoricoItem,
    SimuladoLivrePorSelecao,
    SimuladoLivrePorSorteio,
    SimuladoLivreResponse,
    SubmeterSimuladoLivreRequest,
)

router = APIRouter(prefix="/simulado-livre", tags=["Simulado Livre"])

DIFICULDADES = ["FACIL", "MEDIO", "DIFICIL"]


def _require_aluno(usuario):
    if usuario.tipo != "ALUNO":
        raise HTTPException(status_code=403, detail="Acesso restrito a alunos")
    return usuario


async def _buscar_aluno(usuario_id: str):
    aluno = await db.aluno.find_unique(where={"usuarioId": usuario_id})
    if not aluno:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    return aluno


def _titulo(nomes: list[str]) -> str:
    nomes = nomes or ["Simulado"]
    return f"Simulado livre — {', '.join(nomes)}"[:200]


async def _nomes_componentes(componente_ids: list[str]) -> list[str]:
    componentes = await db.componentecurricular.find_many(
        where={"id": {"in": componente_ids}}
    )
    mapa = {c.id: c.nome for c in componentes}
    return [mapa[cid] for cid in componente_ids if cid in mapa]


def _assunto(questao_api: dict) -> str:
    topic = questao_api.get("topic") or {}
    return topic.get("name") or ""


def _alternativas_para_aluno(alternativas) -> list[AlternativaParaAluno]:
    raw = alternativas if isinstance(alternativas, list) else []
    return [
        AlternativaParaAluno(letra=a.get("letra", ""), texto=a.get("texto", ""))
        for a in raw
    ]


def _snapshot(questao_api: dict, dificuldade: str) -> dict:
    """Monta o snapshot de uma questão vinda da API externa."""
    alternativas, correta = questions_api.montar_alternativas(questao_api)
    return {
        "questaoId": questao_api.get("id"),
        "enunciado": questao_api.get("title", ""),
        "urlImagem": questao_api.get("imageUrl"),
        "alternativas": alternativas,
        "respostaCorreta": correta,
        "assunto": _assunto(questao_api),
        "dificuldade": dificuldade,
    }


async def _criar_simulado(
    aluno_id: str, componente_ids: list[str], duracao: int, snapshots: list[dict]
) -> SimuladoLivreResponse:
    nomes = await _nomes_componentes(componente_ids)
    simulado = await db.simuladolivre.create(
        data={
            "aluno": {"connect": {"id": aluno_id}},
            "titulo": _titulo(nomes),
            "componenteIds": Json(componente_ids),
            "duracaoMinutos": duracao,
            "status": "EM_ANDAMENTO",
        }
    )

    for ordem, snap in enumerate(snapshots, start=1):
        await db.itemsimuladolivre.create(
            data={
                "simuladoLivre": {"connect": {"id": simulado.id}},
                "questaoId": snap["questaoId"],
                "enunciado": snap["enunciado"],
                "urlImagem": snap.get("urlImagem"),
                "alternativas": Json(snap["alternativas"]),
                "respostaCorreta": snap["respostaCorreta"],
                "assunto": snap.get("assunto") or "",
                "dificuldade": snap.get("dificuldade") or "",
                "ordem": ordem,
            }
        )

    return SimuladoLivreResponse(
        id=simulado.id,
        titulo=simulado.titulo,
        duracaoMinutos=simulado.duracaoMinutos,
        totalQuestoes=len(snapshots),
        status=simulado.status,
        questoes=[
            QuestaoSimuladoLivre(
                ordem=ordem,
                questaoId=snap["questaoId"],
                enunciado=snap["enunciado"],
                assunto=snap.get("assunto") or "",
                dificuldade=snap.get("dificuldade") or "",
                alternativas=_alternativas_para_aluno(snap["alternativas"]),
                respostaSalva=None,
            )
            for ordem, snap in enumerate(snapshots, start=1)
        ],
    )


@router.get("/disciplinas", response_model=list[DisciplinaSimulado])
async def listar_disciplinas(usuario=Depends(get_current_user)):
    _require_aluno(usuario)

    componentes = await db.componentecurricular.find_many(where={"ativo": True})

    # Agrupa por nome. Componentes de mesmo nome compartilham o mesmo slug da
    # API, então a matéria é contada uma vez (não soma duplicado).
    por_nome: dict[str, dict] = {}
    for comp in componentes:
        slug = getattr(comp, "questionsSubjectSlug", None)
        if not slug:
            continue
        dados = por_nome.setdefault(comp.nome, {"componenteIds": [], "slug": slug})
        dados["componenteIds"].append(comp.id)

    disciplinas: list[DisciplinaSimulado] = []
    for nome, info in por_nome.items():
        facil, medio, dificil = await asyncio.gather(
            questions_api.contar_questoes(info["slug"], "FACIL"),
            questions_api.contar_questoes(info["slug"], "MEDIO"),
            questions_api.contar_questoes(info["slug"], "DIFICIL"),
        )
        total = facil + medio + dificil
        if total > 0:
            disciplinas.append(
                DisciplinaSimulado(
                    nome=nome,
                    componenteIds=info["componenteIds"],
                    totalQuestoes=total,
                    facil=facil,
                    medio=medio,
                    dificil=dificil,
                )
            )

    disciplinas.sort(key=lambda d: d.nome)
    return disciplinas


@router.get("/banco", response_model=list[QuestaoBanco])
async def listar_banco(
    usuario=Depends(get_current_user),
    componente_id: str = Query(..., min_length=1),
    assunto_id: str | None = Query(default=None),
    dificuldade: str | None = Query(default=None),
):
    _require_aluno(usuario)
    componente_ids = [c for c in componente_id.split(",") if c]
    slugs = await _subject_slugs(componente_ids)
    faceis, medias, dificeis = await _pools_por_dificuldade(slugs)

    itens: list[QuestaoBanco] = []
    for dif, pool in (("FACIL", faceis), ("MEDIO", medias), ("DIFICIL", dificeis)):
        if dificuldade in ("FACIL", "MEDIO", "DIFICIL") and dif != dificuldade:
            continue
        for q in pool:
            itens.append(
                QuestaoBanco(
                    id=q.get("id"),
                    enunciado=q.get("title", ""),
                    assunto=_assunto(q),
                    dificuldade=dif,
                    componenteId=componente_ids[0],
                )
            )
    return itens


@router.post("/sortear", response_model=SimuladoLivreResponse, status_code=201)
async def criar_por_sorteio(data: SimuladoLivrePorSorteio, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    slugs = await _subject_slugs(data.componenteIds)
    faceis, medias, dificeis = await _pools_por_dificuldade(slugs)

    snapshots: list[dict] = []
    for dif, qtd, pool in (
        ("FACIL", data.qtdFacil, faceis),
        ("MEDIO", data.qtdMedio, medias),
        ("DIFICIL", data.qtdDificil, dificeis),
    ):
        if qtd <= 0:
            continue
        if len(pool) < qtd:
            raise HTTPException(
                status_code=422,
                detail=f"Banco insuficiente: pediu {qtd} questões {dif.lower()}, há {len(pool)}",
            )
        snapshots.extend(_snapshot(q, dif) for q in random.sample(pool, qtd))

    random.shuffle(snapshots)
    return await _criar_simulado(aluno.id, data.componenteIds, data.duracaoMinutos, snapshots)


@router.post("/selecionar", response_model=SimuladoLivreResponse, status_code=201)
async def criar_por_selecao(data: SimuladoLivrePorSelecao, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    slugs = await _subject_slugs(data.componenteIds)
    faceis, medias, dificeis = await _pools_por_dificuldade(slugs)

    por_id: dict[str, tuple[dict, str]] = {}
    for dif, pool in (("FACIL", faceis), ("MEDIO", medias), ("DIFICIL", dificeis)):
        for q in pool:
            qid = q.get("id")
            if qid and qid not in por_id:
                por_id[qid] = (q, dif)

    ids_unicos = list(dict.fromkeys(data.questaoIds))
    faltando = [qid for qid in ids_unicos if qid not in por_id]
    if faltando:
        raise HTTPException(
            status_code=422,
            detail="Uma ou mais questões não foram encontradas no banco da API",
        )

    snapshots = [_snapshot(*por_id[qid]) for qid in ids_unicos]
    return await _criar_simulado(aluno.id, data.componenteIds, data.duracaoMinutos, snapshots)


@router.get("/{simulado_id}", response_model=SimuladoLivreResponse)
async def buscar_simulado(simulado_id: str, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    simulado = await db.simuladolivre.find_unique(
        where={"id": simulado_id},
        include={"itens": True},
    )
    if not simulado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    if simulado.alunoId != aluno.id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    itens = sorted(simulado.itens, key=lambda i: i.ordem)
    return SimuladoLivreResponse(
        id=simulado.id,
        titulo=simulado.titulo,
        duracaoMinutos=simulado.duracaoMinutos,
        totalQuestoes=len(itens),
        status=simulado.status,
        questoes=[
            QuestaoSimuladoLivre(
                ordem=item.ordem,
                questaoId=item.questaoId,
                enunciado=item.enunciado or "",
                assunto=item.assunto or "",
                dificuldade=item.dificuldade or "",
                alternativas=_alternativas_para_aluno(item.alternativas),
                respostaSalva=item.alternativaMarcada,
            )
            for item in itens
        ],
    )


@router.post("/{simulado_id}/submeter", response_model=ResultadoSimuladoLivreResponse)
async def submeter_simulado(
    simulado_id: str,
    data: SubmeterSimuladoLivreRequest,
    usuario=Depends(get_current_user),
):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    simulado = await db.simuladolivre.find_unique(
        where={"id": simulado_id},
        include={"itens": True},
    )
    if not simulado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    if simulado.alunoId != aluno.id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if simulado.status == "FINALIZADO":
        raise HTTPException(status_code=409, detail="Simulado já finalizado")

    marcadas = {r.questaoId: r.resposta.upper() for r in data.respostas}
    agora = datetime.now(timezone.utc)

    acertos = 0
    gabarito = []
    itens = sorted(simulado.itens, key=lambda i: i.ordem)

    for item in itens:
        marcada = marcadas.get(item.questaoId)
        correta_letra = (item.respostaCorreta or "").upper()
        acertou = marcada is not None and marcada == correta_letra
        if acertou:
            acertos += 1

        await db.itemsimuladolivre.update(
            where={
                "simuladoLivreId_questaoId": {
                    "simuladoLivreId": simulado.id,
                    "questaoId": item.questaoId,
                }
            },
            data={"alternativaMarcada": marcada, "respondidoEm": agora if marcada else None},
        )

        gabarito.append(
            GabaritoSimuladoLivreItem(
                ordem=item.ordem,
                questaoId=item.questaoId,
                enunciado=item.enunciado or "",
                assunto=item.assunto or "",
                dificuldade=item.dificuldade or "",
                alternativaMarcada=marcada,
                alternativaCorreta=correta_letra,
                correta=acertou,
            )
        )

    total = len(itens)
    pontuacao = round(acertos / total * 10, 1) if total > 0 else 0.0

    await db.simuladolivre.update(
        where={"id": simulado.id},
        data={"status": "FINALIZADO", "pontuacao": pontuacao, "finalizadoEm": agora},
    )

    return ResultadoSimuladoLivreResponse(
        id=simulado.id,
        titulo=simulado.titulo,
        pontuacao=pontuacao,
        acertos=acertos,
        total=total,
        status="FINALIZADO",
        finalizadoEm=agora,
        gabarito=gabarito,
    )


@router.get("", response_model=list[SimuladoLivreHistoricoItem])
async def historico(usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    simulados = await db.simuladolivre.find_many(
        where={"alunoId": aluno.id},
        include={"itens": True},
        order={"criadoEm": "desc"},
    )
    return [
        SimuladoLivreHistoricoItem(
            id=s.id,
            titulo=s.titulo,
            totalQuestoes=len(s.itens),
            pontuacao=s.pontuacao,
            status=s.status,
            criadoEm=s.criadoEm,
            finalizadoEm=s.finalizadoEm,
        )
        for s in simulados
    ]
