import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Json

from src.database import db
from src.dependencies import get_current_user
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


def _require_aluno(usuario):
    if usuario.tipo != "ALUNO":
        raise HTTPException(status_code=403, detail="Acesso restrito a alunos")
    return usuario


async def _buscar_aluno(usuario_id: str):
    aluno = await db.aluno.find_unique(where={"usuarioId": usuario_id})
    if not aluno:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    return aluno


def _alternativas(questao) -> list[AlternativaParaAluno]:
    raw = questao.alternativas if isinstance(questao.alternativas, list) else []
    return [
        AlternativaParaAluno(letra=a.get("letra", ""), texto=a.get("texto", ""))
        for a in raw
    ]


def _titulo(nomes: list[str]) -> str:
    nomes = nomes or ["Simulado"]
    return f"Simulado livre — {', '.join(nomes)}"[:200]


async def _nomes_componentes(componente_ids: list[str]) -> list[str]:
    componentes = await db.componentecurricular.find_many(
        where={"id": {"in": componente_ids}}
    )
    mapa = {c.id: c.nome for c in componentes}
    return [mapa[cid] for cid in componente_ids if cid in mapa]


async def _criar_simulado(aluno_id: str, componente_ids: list[str], duracao: int, questoes: list):
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

    for ordem, questao in enumerate(questoes, start=1):
        await db.itemsimuladolivre.create(
            data={
                "simuladoLivre": {"connect": {"id": simulado.id}},
                "questao": {"connect": {"id": questao.id}},
                "ordem": ordem,
            }
        )

    return _montar_response(simulado, questoes)


def _montar_response(simulado, questoes_ordenadas) -> SimuladoLivreResponse:
    return SimuladoLivreResponse(
        id=simulado.id,
        titulo=simulado.titulo,
        duracaoMinutos=simulado.duracaoMinutos,
        totalQuestoes=len(questoes_ordenadas),
        status=simulado.status,
        questoes=[
            QuestaoSimuladoLivre(
                ordem=ordem,
                questaoId=q.id,
                enunciado=q.enunciado,
                assunto=q.assunto.nome if q.assunto else "",
                dificuldade=q.dificuldade,
                alternativas=_alternativas(q),
                respostaSalva=None,
            )
            for ordem, q in enumerate(questoes_ordenadas, start=1)
        ],
    )


@router.get("/disciplinas", response_model=list[DisciplinaSimulado])
async def listar_disciplinas(usuario=Depends(get_current_user)):
    _require_aluno(usuario)

    componentes = await db.componentecurricular.find_many(where={"ativo": True})
    questoes = await db.questao.find_many(where={"ativa": True})

    por_componente: dict[str, dict[str, int]] = {}
    for q in questoes:
        c = por_componente.setdefault(q.componenteId, {"FACIL": 0, "MEDIO": 0, "DIFICIL": 0})
        if q.dificuldade in c:
            c[q.dificuldade] += 1

    agregado: dict[str, dict] = {}
    for comp in componentes:
        dados = agregado.setdefault(
            comp.nome,
            {"componenteIds": [], "facil": 0, "medio": 0, "dificil": 0},
        )
        dados["componenteIds"].append(comp.id)
        cont = por_componente.get(comp.id, {"FACIL": 0, "MEDIO": 0, "DIFICIL": 0})
        dados["facil"] += cont["FACIL"]
        dados["medio"] += cont["MEDIO"]
        dados["dificil"] += cont["DIFICIL"]

    disciplinas = [
        DisciplinaSimulado(
            nome=nome,
            componenteIds=dados["componenteIds"],
            totalQuestoes=dados["facil"] + dados["medio"] + dados["dificil"],
            facil=dados["facil"],
            medio=dados["medio"],
            dificil=dados["dificil"],
        )
        for nome, dados in agregado.items()
    ]
    disciplinas = [d for d in disciplinas if d.totalQuestoes > 0]
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
    where: dict = {"componenteId": {"in": componente_ids}, "ativa": True}
    if assunto_id:
        where["assuntoId"] = assunto_id
    if dificuldade in ("FACIL", "MEDIO", "DIFICIL"):
        where["dificuldade"] = dificuldade

    questoes = await db.questao.find_many(
        where=where,
        include={"assunto": True},
        order={"criadoEm": "desc"},
    )
    return [
        QuestaoBanco(
            id=q.id,
            enunciado=q.enunciado,
            assunto=q.assunto.nome if q.assunto else "",
            dificuldade=q.dificuldade,
            componenteId=q.componenteId,
        )
        for q in questoes
    ]


@router.post("/sortear", response_model=SimuladoLivreResponse, status_code=201)
async def criar_por_sorteio(data: SimuladoLivrePorSorteio, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    selecionadas = []
    for dificuldade, qtd in (
        ("FACIL", data.qtdFacil),
        ("MEDIO", data.qtdMedio),
        ("DIFICIL", data.qtdDificil),
    ):
        if qtd <= 0:
            continue
        disponiveis = await db.questao.find_many(
            where={
                "componenteId": {"in": data.componenteIds},
                "dificuldade": dificuldade,
                "ativa": True,
            },
            include={"assunto": True},
        )
        if len(disponiveis) < qtd:
            raise HTTPException(
                status_code=422,
                detail=f"Banco insuficiente: pediu {qtd} questões {dificuldade.lower()}, há {len(disponiveis)}",
            )
        selecionadas.extend(random.sample(disponiveis, qtd))

    random.shuffle(selecionadas)
    return await _criar_simulado(aluno.id, data.componenteIds, data.duracaoMinutos, selecionadas)


@router.post("/selecionar", response_model=SimuladoLivreResponse, status_code=201)
async def criar_por_selecao(data: SimuladoLivrePorSelecao, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    questoes = await db.questao.find_many(
        where={"id": {"in": data.questaoIds}, "ativa": True},
        include={"assunto": True},
    )
    if len(questoes) != len(set(data.questaoIds)):
        raise HTTPException(status_code=422, detail="Uma ou mais questões não foram encontradas")

    ordem_map = {qid: i for i, qid in enumerate(data.questaoIds)}
    questoes.sort(key=lambda q: ordem_map.get(q.id, 0))
    return await _criar_simulado(aluno.id, data.componenteIds, data.duracaoMinutos, questoes)


@router.get("/{simulado_id}", response_model=SimuladoLivreResponse)
async def buscar_simulado(simulado_id: str, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno(usuario.id)

    simulado = await db.simuladolivre.find_unique(
        where={"id": simulado_id},
        include={"itens": {"include": {"questao": {"include": {"assunto": True}}}}},
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
                enunciado=item.questao.enunciado,
                assunto=item.questao.assunto.nome if item.questao.assunto else "",
                dificuldade=item.questao.dificuldade,
                alternativas=_alternativas(item.questao),
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
        include={"itens": {"include": {"questao": {"include": {"assunto": True}}}}},
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
        correta_letra = item.questao.respostaCorreta.upper()
        acertou = marcada == correta_letra
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
                enunciado=item.questao.enunciado,
                assunto=item.questao.assunto.nome if item.questao.assunto else "",
                dificuldade=item.questao.dificuldade,
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
