from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from prisma import Json

from src.database import db
from src.dependencies import get_current_user
from src.services.certificacao import processar_certificacao
from src.schemas import (
    AproveitamentoNivel,
    AutoSaveRequest,
    AutoSaveResponse,
    CertificadoItem,
    ComponenteAprovadoItem,
    ComponenteProgresso,
    EtapaDisponivelResponse,
    GabaritoItemDetalhado,
    HistoricoItem,
    IniciarProvaResponse,
    InscricaoResponse,
    QuestaoParaAluno,
    AlternativaParaAluno,
    ResultadoResponse,
    SimuladoResumoResultado,
    StatusResultado,
    ViolacaoRequest,
    ViolacaoResponse,
)

ROTULOS_VIOLACAO = {
    "saiu_tela_cheia": "saiu do modo tela cheia",
    "trocou_aba": "trocou de aba ou janela",
    "perdeu_foco": "saiu da janela da prova",
    "copiar_colar": "tentou copiar ou colar conteúdo",
    "menu_contexto": "abriu o menu de contexto (botão direito)",
    "atalho_proibido": "usou um atalho de teclado bloqueado",
}
from src.services.sorteio_questoes import (
    embaralhar_alternativas_questao,
    montar_questoes_selecionadas,
    sortear_questoes_para_prova,
)

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


def _texto_alternativa(alternativas: list, letra: str | None) -> str | None:
    if not letra or not isinstance(alternativas, list):
        return None
    for alt in alternativas:
        if isinstance(alt, dict) and alt.get("letra", "").upper() == letra.upper():
            return alt.get("texto", "")
    return None


def _resolver_resposta_original(alternativas_embaralhadas: list | None, resposta_aluno: str | None) -> str | None:
    if not resposta_aluno or not alternativas_embaralhadas:
        return resposta_aluno
    for alt in alternativas_embaralhadas:
        if isinstance(alt, dict) and alt.get("letra", "").upper() == resposta_aluno.upper():
            return alt.get("letraOriginal", resposta_aluno)
    return resposta_aluno


def _montar_gabarito(tentativas_questoes: list) -> list[GabaritoItemDetalhado]:
    gabarito: list[GabaritoItemDetalhado] = []
    for tq in sorted(tentativas_questoes, key=lambda x: x.ordem):
        alternativas_base = tq.questao.alternativas if isinstance(tq.questao.alternativas, list) else []
        alternativas_embaralhadas = tq.alternativasEmbaralhadas if isinstance(getattr(tq, "alternativasEmbaralhadas", None), list) else None

        resposta_correta_original = tq.questao.respostaCorreta.upper()
        resposta_aluno_exibida = tq.alternativaMarcada.upper() if tq.alternativaMarcada else None
        resposta_aluno_original = _resolver_resposta_original(alternativas_embaralhadas, resposta_aluno_exibida)

        correta = resposta_aluno_original == resposta_correta_original

        texto_marcada = _texto_alternativa(
            alternativas_embaralhadas or alternativas_base,
            resposta_aluno_exibida,
        )
        texto_correta = _texto_alternativa(alternativas_base, resposta_correta_original)

        gabarito.append(GabaritoItemDetalhado(
            ordem=tq.ordem,
            questaoId=tq.questaoId,
            enunciado=tq.questao.enunciado,
            alternativaMarcada=texto_marcada,
            alternativaCorreta=texto_correta or resposta_correta_original,
            correta=correta,
        ))
    return gabarito


def _contar_acertos(tentativas_questoes: list) -> int:
    total = 0
    for tq in tentativas_questoes:
        if not tq.alternativaMarcada:
            continue
        alternativas_embaralhadas = getattr(tq, "alternativasEmbaralhadas", None)
        resposta_original = _resolver_resposta_original(
            alternativas_embaralhadas if isinstance(alternativas_embaralhadas, list) else None,
            tq.alternativaMarcada.upper(),
        )
        if resposta_original and resposta_original.upper() == tq.questao.respostaCorreta.upper():
            total += 1
    return total


async def _notificar_gabarito_disponivel(usuario_id: str, resultado_id: str, titulo_simulado: str) -> None:
    existente = await db.notificacao.find_first(
        where={
            "usuarioDestId": usuario_id,
            "referenciaId": resultado_id,
            "referenciaTipo": "resultado",
        }
    )
    if not existente:
        await db.notificacao.create(
            data={
                "usuarioDest": {"connect": {"id": usuario_id}},
                "tipo": "gabarito_disponivel",
                "titulo": "Gabarito disponível",
                "mensagem": f"O gabarito da etapa '{titulo_simulado}' já está disponível para consulta.",
                "referenciaId": resultado_id,
                "referenciaTipo": "resultado",
                "status": "PENDENTE",
            }
        )


async def _notificar_violacao(
    resultado_id: str,
    simulado,
    aluno_nome: str,
    descricao: str,
    total: int,
) -> None:
    destinatarios: set[str] = set()

    if simulado and simulado.professor and simulado.professor.usuarioId:
        destinatarios.add(simulado.professor.usuarioId)

    admins = await db.usuario.find_many(where={"tipo": "ADMIN", "ativo": True})
    for admin in admins:
        destinatarios.add(admin.id)

    titulo_simulado = simulado.titulo if simulado else "etapa"
    mensagem = (
        f"O aluno {aluno_nome} {descricao} durante a etapa '{titulo_simulado}'. "
        f"Total de ocorrências: {total}."
    )

    for usuario_id in destinatarios:
        await db.notificacao.create(
            data={
                "usuarioDest": {"connect": {"id": usuario_id}},
                "tipo": "violacao_prova",
                "titulo": "Possível tentativa de cola detectada",
                "mensagem": mensagem,
                "referenciaId": resultado_id,
                "referenciaTipo": "resultado",
                "status": "PENDENTE",
            }
        )


@router.post("/violacao/{resultado_id}", response_model=ViolacaoResponse)
async def registrar_violacao(
    resultado_id: str,
    data: ViolacaoRequest,
    usuario=Depends(get_current_user),
):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    resultado = await db.resultadoaluno.find_unique(
        where={"id": resultado_id},
        include={"simulado": {"include": {"professor": True}}},
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Resultado não encontrado")
    if resultado.alunoId != aluno.id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    descricao = ROTULOS_VIOLACAO.get(data.tipo, "realizou uma ação suspeita")

    await db.violacaoprova.create(
        data={
            "resultado": {"connect": {"id": resultado_id}},
            "tipo": data.tipo,
            "detalhe": data.detalhe or descricao,
        }
    )

    total = await db.violacaoprova.count(where={"resultadoId": resultado_id})

    await _notificar_violacao(
        resultado_id=resultado_id,
        simulado=resultado.simulado,
        aluno_nome=usuario.nome,
        descricao=descricao,
        total=total,
    )

    return ViolacaoResponse(registrada=True, totalViolacoes=total)


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

    inscricoes_set: set[str] = set()
    if simulados_visiveis:
        inscricoes = await db.inscricaoaluno.find_many(
            where={
                "alunoId": aluno.id,
                "simuladoId": {"in": [s.id for s in simulados_visiveis]},
            }
        )
        inscricoes_set = {i.simuladoId for i in inscricoes}

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
            inscrito=s.id in inscricoes_set,
            geraCertificado=s.geraCertificado,
            statusResultado=resultado_map[s.id].statusResultado if s.id in resultado_map else None,
            resultadoId=resultado_map[s.id].id if s.id in resultado_map else None,
        )
        for s in simulados_visiveis
    ]


@router.get("/certificados", response_model=list[CertificadoItem])
async def listar_certificados(usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    certificados = await db.certificado.find_many(
        where={"alunoId": aluno.id},
        include={"nivel": True},
        order={"emitidoEm": "desc"},
    )

    return [
        CertificadoItem(
            id=c.id,
            tipo=c.tipo,
            nivel=c.nivel.nome,
            anoReferencia=c.anoReferencia,
            codigoVerificacao=c.codigoVerificacao,
            emitidoEm=c.emitidoEm,
            componentesAprovados=[
                ComponenteAprovadoItem(componente=item["componente"], nota=item["nota"])
                for item in (c.componentesAprovados or [])
            ],
        )
        for c in certificados
    ]


@router.get("/aproveitamento", response_model=list[AproveitamentoNivel])
async def listar_aproveitamento(usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)
    ano = _agora().year

    niveis = await db.nivelensino.find_many(
        where={"ativo": True, "componentesNivel": {"some": {}}},
        include={"componentesNivel": {"include": {"componente": True}}},
        order=[{"ordem": "asc"}, {"nome": "asc"}],
    )

    aprovacoes = await db.aproveitamentocandidato.find_many(
        where={"alunoId": aluno.id, "anoReferencia": ano, "aprovado": True},
    )
    nota_por_chave = {(a.nivelId, a.componenteId): a.notaObtida for a in aprovacoes}

    resultado = []
    for nivel in niveis:
        componentes = []
        aprovados = 0
        for nc in nivel.componentesNivel:
            chave = (nivel.id, nc.componenteId)
            ok = chave in nota_por_chave
            if ok:
                aprovados += 1
            componentes.append(
                ComponenteProgresso(
                    componente=nc.componente.nome,
                    aprovado=ok,
                    nota=nota_por_chave.get(chave),
                )
            )
        componentes.sort(key=lambda c: c.componente)
        resultado.append(
            AproveitamentoNivel(
                nivel=nivel.nome,
                anoReferencia=ano,
                totalComponentes=len(componentes),
                aprovados=aprovados,
                componentes=componentes,
            )
        )

    return resultado


@router.post("/inscrever/{simulado_id}", response_model=InscricaoResponse)
async def inscrever_em_prova(simulado_id: str, usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    simulado = await db.simulado.find_unique(
        where={"id": simulado_id},
        include={"aplicacoes": True},
    )
    if not simulado or simulado.status != "PUBLICADO":
        raise HTTPException(status_code=404, detail="Etapa não encontrada")

    if _aware(simulado.janelaFim) < _agora():
        raise HTTPException(status_code=422, detail="Etapa já encerrada")

    turmas_aluno = await db.turmaaluno.find_many(
        where={"alunoId": aluno.id, "saiuEm": None}
    )
    aluno_turma_ids = {ta.turmaId for ta in turmas_aluno}

    if simulado.aplicacoes and not any(a.turmaId in aluno_turma_ids for a in simulado.aplicacoes):
        raise HTTPException(status_code=403, detail="Etapa não disponível para sua turma")

    existente = await db.inscricaoaluno.find_unique(
        where={"simuladoId_alunoId": {"simuladoId": simulado_id, "alunoId": aluno.id}}
    )
    if not existente:
        await db.inscricaoaluno.create(
            data={
                "simulado": {"connect": {"id": simulado_id}},
                "aluno": {"connect": {"id": aluno.id}},
            }
        )

    return InscricaoResponse(inscrito=True, simuladoId=simulado_id)


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
        questoes = []
        for tq in tentativas_ordenadas:
            alts_raw = getattr(tq, "alternativasEmbaralhadas", None)
            alts = (
                [AlternativaParaAluno(letra=a.get("letra", ""), texto=a.get("texto", "")) for a in alts_raw]
                if isinstance(alts_raw, list)
                else [
                    AlternativaParaAluno(letra=a.get("letra", ""), texto=a.get("texto", ""))
                    for a in (tq.questao.alternativas if isinstance(tq.questao.alternativas, list) else [])
                ]
            )
            questoes.append(QuestaoParaAluno(
                ordem=tq.ordem,
                questaoId=tq.questaoId,
                enunciado=tq.questao.enunciado,
                alternativas=alts,
                respostaSalva=tq.alternativaMarcada,
            ))

        return IniciarProvaResponse(
            resultadoId=resultado_existente.id,
            iniciadoEm=iniciado_em,
            expiraEm=expira_em,
            duracaoMinutos=simulado.duracaoMinutos,
            totalQuestoes=len(questoes),
            questoes=questoes,
        )

    selecionadas = getattr(simulado, "questoesSelecionadas", None)
    if isinstance(selecionadas, list) and selecionadas:
        questoes_sorteadas = await montar_questoes_selecionadas(selecionadas)
    else:
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

    questoes_response = []
    for q in questoes_sorteadas:
        alternativas_originais = q["alternativas"]
        resposta_correta = q["respostaCorreta"]

        if simulado.embaralharAlternativas:
            alternativas_exibidas, _ = embaralhar_alternativas_questao(
                alternativas_originais, resposta_correta
            )
            alts_para_salvar = Json(alternativas_exibidas)
        else:
            alternativas_exibidas = alternativas_originais
            alts_para_salvar = None

        await db.tentativaquestao.create(
            data={
                "resultado": {"connect": {"id": novo_resultado.id}},
                "questao": {"connect": {"id": q["questaoId"]}},
                "ordem": q["ordem"],
                **({"alternativasEmbaralhadas": alts_para_salvar} if alts_para_salvar else {}),
            }
        )

        questoes_response.append(QuestaoParaAluno(
            ordem=q["ordem"],
            questaoId=q["questaoId"],
            enunciado=q["enunciado"],
            alternativas=[
                AlternativaParaAluno(letra=a["letra"], texto=a["texto"])
                for a in alternativas_exibidas
            ],
            respostaSalva=None,
        ))

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

    acertos = _contar_acertos(resultado.tentativasQuestoes)
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

    if status_final == "FINALIZADO":
        await processar_certificacao(
            resultado.simulado, resultado_id, aluno.id, pontuacao, agora
        )

    janela_fim = _aware(resultado.simulado.janelaFim)

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
        gabaritoDisponivel=False,
        gabaritoDisponivelEm=janela_fim,
        gabarito=None,
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

    agora = _agora()
    janela_fim = _aware(resultado.simulado.janelaFim)
    acertos = _contar_acertos(resultado.tentativasQuestoes)
    total = len(resultado.tentativasQuestoes)

    gabarito_disponivel = usuario.tipo != "ALUNO" or agora >= janela_fim

    if gabarito_disponivel and usuario.tipo == "ALUNO":
        await _notificar_gabarito_disponivel(
            usuario_id=usuario.id,
            resultado_id=resultado_id,
            titulo_simulado=resultado.simulado.titulo,
        )

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
        gabaritoDisponivel=gabarito_disponivel,
        gabaritoDisponivelEm=janela_fim,
        gabarito=_montar_gabarito(resultado.tentativasQuestoes) if gabarito_disponivel else None,
    )


@router.get("/historico", response_model=list[HistoricoItem])
async def historico(usuario=Depends(get_current_user)):
    _require_aluno(usuario)
    aluno = await _buscar_aluno_do_usuario(usuario.id)

    resultados = await db.resultadoaluno.find_many(
        where={
            "alunoId": aluno.id,
            "statusResultado": {"in": ["FINALIZADO", "EXPIRADO"]},
        },
        include={
            "simulado": {"include": {"componente": True}},
            "tentativasQuestoes": {"include": {"questao": True}},
        },
        order={"finalizadoEm": "desc"},
    )

    agora = _agora()
    historico_items: list[HistoricoItem] = []

    for r in resultados:
        total = len(r.tentativasQuestoes)
        acertos = _contar_acertos(r.tentativasQuestoes) if total > 0 else 0
        janela_fim = _aware(r.simulado.janelaFim)

        historico_items.append(HistoricoItem(
            resultadoId=r.id,
            simuladoId=r.simuladoId,
            titulo=r.simulado.titulo,
            componente=r.simulado.componente.nome,
            pontuacao=r.pontuacao,
            acertos=acertos,
            total=total,
            statusResultado=StatusResultado(r.statusResultado),
            finalizadoEm=r.finalizadoEm,
            gabaritoDisponivel=agora >= janela_fim,
            gabaritoDisponivelEm=janela_fim,
        ))

    return historico_items