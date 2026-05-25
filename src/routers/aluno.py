from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from src.database import db
from src.dependencies import get_current_user
from src.schemas import (
    AutoSaveRequest,
    AutoSaveResponse,
    EtapaDisponivelResponse,
    GabaritoItem,
    IniciarProvaResponse,
    QuestaoParaAluno,
    AlternativaParaAluno,
    ResultadoResponse,
    SimuladoResumoResultado,
    StatusResultado,
)
from src.services.sorteio_questoes import sortear_questoes_para_prova

router = APIRouter(prefix="/aluno", tags=["Aluno"])


def _require_aluno(usuario):
    if usuario.tipo != "ALUNO":
        raise HTTPException(status_code=403, detail="Acesso restrito a alunos")
    return usuario


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _buscar_aluno_do_usuario(usuario_id: str):
    aluno = await db.aluno.find_unique(where={"usuarioId": usuario_id})
    if not aluno:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")
    return aluno


@router.get("/etapas-disponiveis", response_model=list[EtapaDisponivelResponse])
async def etapas_disponiveis(usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)
    agora = _agora()

    turmas_aluno = await db.turmaaluno.find_many(
        where={"alunoId": aluno.id, "saiuEm": None}
    )
    aluno_turma_ids = {ta.turmaId for ta in turmas_aluno}

    simulados = await db.simulado.find_many(
        where={
            "status": "PUBLICADO",
            "janelaFim": {"gte": agora},
        },
        include={
            "componente": {"include": {"modalidade": True}},
            "aplicacoes": True,
        },
        order={"janelaInicio": "asc"},
    )

    simulados_visiveis = [
        s for s in simulados
        if not s.aplicacoes or any(a.turmaId in aluno_turma_ids for a in s.aplicacoes)
    ]

    resultado_map: dict = {}
    if simulados_visiveis:
        resultados = await db.resultadoaluno.find_many(
            where={
                "alunoId": aluno.id,
                "simuladoId": {"in": [s.id for s in simulados_visiveis]},
            }
        )
        for r in resultados:
            resultado_map[r.simuladoId] = r

    return [
        EtapaDisponivelResponse(
            id=s.id,
            titulo=s.titulo,
            descricao=s.descricao,
            componente={
                "id": s.componente.id,
                "nome": s.componente.nome,
                "modalidade": s.componente.modalidade.nome,
            },
            duracaoMinutos=s.duracaoMinutos,
            totalQuestoes=s.qtdFacil + s.qtdMedio + s.qtdDificil,
            vagas=s.vagas,
            janelaInicio=s.janelaInicio,
            janelaFim=s.janelaFim,
            ativa=_aware(s.janelaInicio) <= agora <= _aware(s.janelaFim),
            jaIniciada=s.id in resultado_map,
            statusResultado=resultado_map[s.id].statusResultado if s.id in resultado_map else None,
            resultadoId=resultado_map[s.id].id if s.id in resultado_map else None,
        )
        for s in simulados_visiveis
    ]


@router.post("/iniciar-prova/{simulado_id}", response_model=IniciarProvaResponse, status_code=201)
async def iniciar_prova(simulado_id: str, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    simulado = await db.simulado.find_unique(
        where={"id": simulado_id},
        include={"componente": True},
    )
    if not simulado or simulado.status != "PUBLICADO":
        raise HTTPException(status_code=404, detail="Etapa não encontrada")

    agora = _agora()
    janela_inicio = _aware(simulado.janelaInicio)
    janela_fim = _aware(simulado.janelaFim)

    if not (janela_inicio <= agora <= janela_fim):
        raise HTTPException(status_code=422, detail="Etapa não está dentro da janela de realização")

    resultado_existente = await db.resultadoaluno.find_first(
        where={"simuladoId": simulado_id, "alunoId": aluno.id},
        include={"tentativasQuestoes": {"include": {"questao": True}}},
    )

    if resultado_existente:
        if resultado_existente.statusResultado == "FINALIZADO":
            raise HTTPException(
                status_code=409,
                detail={
                    "mensagem": "Etapa já realizada",
                    "resultadoId": resultado_existente.id,
                    "statusResultado": "FINALIZADO",
                },
            )

        if resultado_existente.statusResultado == "EXPIRADO":
            raise HTTPException(
                status_code=409,
                detail={
                    "mensagem": "Tentativa expirada",
                    "resultadoId": resultado_existente.id,
                    "statusResultado": "EXPIRADO",
                },
            )

        iniciado_em = _aware(resultado_existente.iniciadoEm)
        expira_em = iniciado_em + timedelta(minutes=simulado.duracaoMinutos)

        if agora > expira_em:
            await db.resultadoaluno.update(
                where={"id": resultado_existente.id},
                data={"statusResultado": "EXPIRADO"},
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "mensagem": "Tentativa expirada",
                    "resultadoId": resultado_existente.id,
                    "statusResultado": "EXPIRADO",
                },
            )

        tentativas_ordenadas = sorted(resultado_existente.tentativasQuestoes, key=lambda tq: tq.ordem)
        questoes = [
            QuestaoParaAluno(
                ordem=tq.ordem,
                questaoId=tq.questaoId,
                enunciado=tq.questao.enunciado,
                alternativas=[
                    AlternativaParaAluno(letra=a.get("letra", ""), texto=a.get("texto", ""))
                    for a in (tq.questao.alternativas if isinstance(tq.questao.alternativas, list) else [])
                ],
                respostaSalva=tq.alternativaMarcada,
            )
            for tq in tentativas_ordenadas
        ]

        return IniciarProvaResponse(
            resultadoId=resultado_existente.id,
            iniciadoEm=iniciado_em,
            expiraEm=expira_em,
            duracaoMinutos=simulado.duracaoMinutos,
            totalQuestoes=len(questoes),
            questoes=questoes,
        )

    questoes_sorteadas = await sortear_questoes_para_prova(
        componente_id=simulado.componenteId,
        qtd_facil=simulado.qtdFacil,
        qtd_medio=simulado.qtdMedio,
        qtd_dificil=simulado.qtdDificil,
    )

    iniciado_em = _agora()
    expira_em = iniciado_em + timedelta(minutes=simulado.duracaoMinutos)

    novo_resultado = await db.resultadoaluno.create(
        data={
            "simulado": {"connect": {"id": simulado_id}},
            "aluno": {"connect": {"id": aluno.id}},
            "statusResultado": "EM_ANDAMENTO",
            "iniciadoEm": iniciado_em,
        }
    )

    for q in questoes_sorteadas:
        await db.tentativaquestao.create(
            data={
                "resultado": {"connect": {"id": novo_resultado.id}},
                "questao": {"connect": {"id": q["questaoId"]}},
                "ordem": q["ordem"],
            }
        )

    questoes_response = [
        QuestaoParaAluno(
            ordem=q["ordem"],
            questaoId=q["questaoId"],
            enunciado=q["enunciado"],
            alternativas=[
                AlternativaParaAluno(letra=a["letra"], texto=a["texto"])
                for a in q["alternativas"]
            ],
            respostaSalva=None,
        )
        for q in questoes_sorteadas
    ]

    return IniciarProvaResponse(
        resultadoId=novo_resultado.id,
        iniciadoEm=iniciado_em,
        expiraEm=expira_em,
        duracaoMinutos=simulado.duracaoMinutos,
        totalQuestoes=len(questoes_response),
        questoes=questoes_response,
    )


@router.patch("/responder/{resultado_id}", response_model=AutoSaveResponse)
async def auto_save_respostas(
    resultado_id: str,
    data: AutoSaveRequest,
    usuario=Depends(get_current_user),
):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    resultado = await db.resultadoaluno.find_unique(
        where={"id": resultado_id},
        include={"simulado": True},
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    if resultado.alunoId != aluno.id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if resultado.statusResultado == "FINALIZADO":
        raise HTTPException(status_code=422, detail="Prova já finalizada")

    agora = _agora()
    expira_em = _aware(resultado.iniciadoEm) + timedelta(minutes=resultado.simulado.duracaoMinutos)

    if agora > expira_em:
        await db.resultadoaluno.update(
            where={"id": resultado_id},
            data={"statusResultado": "EXPIRADO"},
        )
        raise HTTPException(status_code=422, detail="Prova expirada")

    mapa = {item.questaoId: item.resposta.upper() for item in data.respostas}

    for questao_id, alternativa in mapa.items():
        await db.tentativaquestao.update(
            where={"resultadoId_questaoId": {"resultadoId": resultado_id, "questaoId": questao_id}},
            data={"alternativaMarcada": alternativa, "respondidoEm": agora},
        )

    total_salvas = await db.tentativaquestao.count(
        where={"resultadoId": resultado_id, "alternativaMarcada": {"not": None}}
    )

    return AutoSaveResponse(salvo=True, totalSalvas=total_salvas, salvoEm=agora)


@router.post("/submeter/{resultado_id}", response_model=ResultadoResponse)
async def submeter_prova(resultado_id: str, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    resultado = await db.resultadoaluno.find_unique(
        where={"id": resultado_id},
        include={
            "simulado": {"include": {"componente": True}},
            "tentativasQuestoes": {"include": {"questao": True}},
        },
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    if resultado.alunoId != aluno.id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if resultado.statusResultado == "FINALIZADO":
        raise HTTPException(status_code=409, detail="Prova já finalizada anteriormente")

    agora = _agora()
    expira_em = _aware(resultado.iniciadoEm) + timedelta(minutes=resultado.simulado.duracaoMinutos)
    status_final = "EXPIRADO" if agora > expira_em else "FINALIZADO"

    acertos = 0
    gabarito: list[GabaritoItem] = []

    for tq in sorted(resultado.tentativasQuestoes, key=lambda x: x.ordem):
        resposta_correta = tq.questao.respostaCorreta.upper()
        resposta_aluno = tq.alternativaMarcada.upper() if tq.alternativaMarcada else None
        correta = resposta_aluno == resposta_correta

        if correta:
            acertos += 1

        gabarito.append(GabaritoItem(
            ordem=tq.ordem,
            questaoId=tq.questaoId,
            respostaAluno=resposta_aluno,
            respostaCorreta=resposta_correta,
            correta=correta,
        ))

    total = len(resultado.tentativasQuestoes)
    pontuacao = round(acertos / total * 10, 1) if total > 0 else 0.0

    await db.resultadoaluno.update(
        where={"id": resultado_id},
        data={
            "pontuacao": pontuacao,
            "statusResultado": status_final,
            "finalizadoEm": agora,
        },
    )

    return ResultadoResponse(
        resultadoId=resultado_id,
        pontuacao=pontuacao,
        acertos=acertos,
        total=total,
        statusResultado=StatusResultado(status_final),
        finalizadoEm=agora,
        simulado=SimuladoResumoResultado(
            titulo=resultado.simulado.titulo,
            componente=resultado.simulado.componente.nome,
            duracaoMinutos=resultado.simulado.duracaoMinutos,
        ),
        gabarito=gabarito,
    )


@router.get("/resultado/{resultado_id}", response_model=ResultadoResponse)
async def ver_resultado(resultado_id: str, usuario=Depends(get_current_user)):
    resultado = await db.resultadoaluno.find_unique(
        where={"id": resultado_id},
        include={
            "simulado": {"include": {"componente": True}},
            "tentativasQuestoes": {"include": {"questao": True}},
        },
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Resultado não encontrado")

    if usuario.tipo == "ALUNO":
        aluno = await _buscar_aluno_do_usuario(usuario.id)
        if resultado.alunoId != aluno.id:
            raise HTTPException(status_code=403, detail="Acesso negado")

    if resultado.statusResultado not in ("FINALIZADO", "EXPIRADO"):
        raise HTTPException(status_code=422, detail="Resultado ainda não disponível")

    acertos = 0
    gabarito: list[GabaritoItem] = []

    for tq in sorted(resultado.tentativasQuestoes, key=lambda x: x.ordem):
        resposta_correta = tq.questao.respostaCorreta.upper()
        resposta_aluno = tq.alternativaMarcada.upper() if tq.alternativaMarcada else None
        correta = resposta_aluno == resposta_correta

        if correta:
            acertos += 1

        gabarito.append(GabaritoItem(
            ordem=tq.ordem,
            questaoId=tq.questaoId,
            respostaAluno=resposta_aluno,
            respostaCorreta=resposta_correta,
            correta=correta,
        ))

    total = len(resultado.tentativasQuestoes)

    return ResultadoResponse(
        resultadoId=resultado_id,
        pontuacao=resultado.pontuacao or 0.0,
        acertos=acertos,
        total=total,
        statusResultado=StatusResultado(resultado.statusResultado),
        finalizadoEm=resultado.finalizadoEm,
        simulado=SimuladoResumoResultado(
            titulo=resultado.simulado.titulo,
            componente=resultado.simulado.componente.nome,
            duracaoMinutos=resultado.simulado.duracaoMinutos,
        ),
        gabarito=gabarito,
    )