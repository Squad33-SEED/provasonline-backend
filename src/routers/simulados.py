from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Json

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    ComponenteResumo,
    DisponibilidadeQuestoes,
    GeracaoRapidaCreate,
    ModalidadeResumo,
    QuestaoBanco,
    RelatorioEtapaResponse,
    RelatorioItemAluno,
    DashboardEmExecucaoItem,
    DashboardResponse,
    DesempenhoEscolaItem,
    SimuladoCreate,
    SimuladoResponse,
    TurmaResumoSimples,
)
from src.routers.aluno import _contar_acertos, _agora, _aware
from src.services import questions_api
from src.services.sorteio_questoes import (
    contar_disponiveis,
    verificar_disponibilidade_multi,
)

DIFICULDADE_API_PARA_PROVAS = {"easy": "FACIL", "medium": "MEDIO", "hard": "DIFICIL"}

router = APIRouter(prefix="/simulados", tags=["Simulados"])

_INCLUDE_COMPLETO = {
    "componente": {"include": {"modalidade": True}},
    "aplicacoes": {"include": {"turma": {"include": {"escola": True}}}},
}


def _resumo_componente(componente) -> ComponenteResumo:
    return ComponenteResumo(
        id=componente.id,
        nome=componente.nome,
        modalidade=ModalidadeResumo(
            id=componente.modalidade.id,
            nome=componente.modalidade.nome,
        ),
    )


async def _mapa_componentes(simulados) -> dict[str, ComponenteResumo]:
    """Pré-carrega (em 1 query) os componentes referenciados em componenteIds."""
    ids: set[str] = set()
    for s in simulados:
        cids = getattr(s, "componenteIds", None)
        if isinstance(cids, list):
            ids.update(cids)
    if not ids:
        return {}
    componentes = await db.componentecurricular.find_many(
        where={"id": {"in": list(ids)}},
        include={"modalidade": True},
    )
    return {c.id: _resumo_componente(c) for c in componentes}


def _serializar_simulado(
    simulado_obj,
    total_inscritos: int = 0,
    componentes_por_id: dict[str, ComponenteResumo] | None = None,
) -> SimuladoResponse:
    principal = _resumo_componente(simulado_obj.componente)
    total = simulado_obj.qtdFacil + simulado_obj.qtdMedio + simulado_obj.qtdDificil

    ids = getattr(simulado_obj, "componenteIds", None)
    if isinstance(ids, list) and ids and componentes_por_id:
        componentes = [componentes_por_id[i] for i in ids if i in componentes_por_id]
    else:
        componentes = []
    if not componentes:
        componentes = [principal]

    turmas: list[TurmaResumoSimples] = []
    if simulado_obj.aplicacoes:
        turmas = [
            TurmaResumoSimples(
                id=a.turma.id,
                nome=a.turma.nome,
                escolaNome=a.turma.escola.nome,
            )
            for a in simulado_obj.aplicacoes
        ]

    return SimuladoResponse(
        id=simulado_obj.id,
        titulo=simulado_obj.titulo,
        descricao=simulado_obj.descricao,
        componente=principal,
        componentes=componentes,
        qtdFacil=simulado_obj.qtdFacil,
        qtdMedio=simulado_obj.qtdMedio,
        qtdDificil=simulado_obj.qtdDificil,
        totalQuestoes=total,
        vagas=simulado_obj.vagas,
        totalInscritos=total_inscritos,
        vagasDisponiveis=max(simulado_obj.vagas - total_inscritos, 0),
        duracaoMinutos=simulado_obj.duracaoMinutos,
        janelaInicio=simulado_obj.janelaInicio,
        janelaFim=simulado_obj.janelaFim,
        status=simulado_obj.status,
        criadoEm=simulado_obj.criadoEm,
        turmas=turmas,
        embaralharAlternativas=simulado_obj.embaralharAlternativas,
        geraCertificado=simulado_obj.geraCertificado,
        nivelEnsinoId=simulado_obj.nivelEnsinoId,
        notaMinimaCertificacao=simulado_obj.notaMinimaCertificacao,
    )


async def _criar_aplicacoes(simulado_id: str, turma_ids: list[str], janela_inicio: datetime, janela_fim: datetime) -> None:
    for turma_id in turma_ids:
        await db.aplicacao.create(
            data={
                "simulado": {"connect": {"id": simulado_id}},
                "turma": {"connect": {"id": turma_id}},
                "dataInicio": janela_inicio,
                "dataFim": janela_fim,
                "status": "AGENDADA",
            }
        )


@router.get("/disponibilidade", response_model=DisponibilidadeQuestoes)
async def obter_disponibilidade(
    componenteId: str = Query(..., min_length=1),
    _=Depends(get_current_user),
):
    componente = await db.componentecurricular.find_unique(
        where={"id": componenteId}
    )
    if not componente:
        raise HTTPException(
            status_code=422,
            detail="Componente curricular não encontrado",
        )

    try:
        contadores = await contar_disponiveis(componenteId)
    except HTTPException as exc:
        if exc.status_code != 502:
            raise

        contadores = {
            "facil": 0,
            "medio": 0,
            "dificil": 0,
        }

    return DisponibilidadeQuestoes(
        componenteId=componenteId,
        facil=contadores["facil"],
        medio=contadores["medio"],
        dificil=contadores["dificil"],
    )


@router.get("/banco", response_model=list[QuestaoBanco])
async def listar_banco_questoes(
    componenteId: str = Query(..., min_length=1),
    assuntoId: str | None = Query(default=None),
    dificuldade: str | None = Query(default=None),
    _=Depends(require_admin),
):
    componente = await db.componentecurricular.find_unique(where={"id": componenteId})
    if not componente or not componente.questionsSubjectSlug:
        raise HTTPException(
            status_code=422,
            detail="Componente não está vinculado a uma matéria da API de questões",
        )

    slug = componente.questionsSubjectSlug
    dificuldades = [dificuldade] if dificuldade in ("FACIL", "MEDIO", "DIFICIL") else ["FACIL", "MEDIO", "DIFICIL"]

    resultado: list[QuestaoBanco] = []
    for dif in dificuldades:
        for q in await questions_api.listar_questoes(slug, dif):
            topico = q.get("topic") or {}
            resultado.append(QuestaoBanco(
                id=q.get("id"),
                enunciado=q.get("title", ""),
                assunto=topico.get("name", ""),
                dificuldade=dif,
                componenteId=componenteId,
            ))

    return resultado


@router.post("/gerar-rapido", response_model=SimuladoResponse, status_code=201)
async def gerar_rapido(data: GeracaoRapidaCreate, _=Depends(require_admin)):
    componente = await db.componentecurricular.find_unique(
        where={"id": data.componenteId},
        include={"modalidade": True},
    )
    if not componente or not componente.ativo:
        raise HTTPException(
            status_code=422,
            detail="Componente curricular não encontrado ou inativo",
        )

    disponiveis = await contar_disponiveis(data.componenteId)

    qtd_facil = min(4, disponiveis["facil"])
    qtd_medio = min(4, disponiveis["medio"])
    qtd_dificil = min(2, disponiveis["dificil"])

    if qtd_facil + qtd_medio + qtd_dificil < 1:
        raise HTTPException(
            status_code=422,
            detail="Banco insuficiente para geração automática. Cadastre questões neste componente.",
        )

    professor_demo = await db.professor.find_first()
    if not professor_demo:
        raise HTTPException(
            status_code=500,
            detail="Nenhum professor cadastrado no sistema.",
        )

    agora = datetime.now(timezone.utc)
    janela_inicio = agora + timedelta(minutes=5)
    janela_fim = agora + timedelta(days=8)

    novo = await db.simulado.create(
        data={
            "titulo": f"Etapa rápida — {componente.nome}",
            "componente": {"connect": {"id": data.componenteId}},
            "professor": {"connect": {"id": professor_demo.id}},
            "qtdFacil": qtd_facil,
            "qtdMedio": qtd_medio,
            "qtdDificil": qtd_dificil,
            "vagas": data.vagas,
            "duracaoMinutos": data.duracaoMinutos,
            "janelaInicio": janela_inicio,
            "janelaFim": janela_fim,
            "status": "PUBLICADO",
            "embaralharAlternativas": True,
        },
        include=_INCLUDE_COMPLETO,
    )

    for turma_id in data.turmaIds:
        turma = await db.turma.find_unique(where={"id": turma_id})
        if turma:
            await db.aplicacao.create(
                data={
                    "simulado": {"connect": {"id": novo.id}},
                    "turma": {"connect": {"id": turma_id}},
                    "dataInicio": janela_inicio,
                    "dataFim": janela_fim,
                    "status": "AGENDADA",
                }
            )

    simulado_completo = await db.simulado.find_unique(
        where={"id": novo.id},
        include=_INCLUDE_COMPLETO,
    )

    mapa_comp = await _mapa_componentes([simulado_completo])
    return _serializar_simulado(simulado_completo, componentes_por_id=mapa_comp)


@router.post("", response_model=SimuladoResponse, status_code=201)
async def criar_simulado(data: SimuladoCreate, _=Depends(require_admin)):
    componente_ids = list(dict.fromkeys(data.componenteIds or [data.componenteId]))
    componente_principal_id = componente_ids[0]

    componentes = await db.componentecurricular.find_many(
        where={"id": {"in": componente_ids}, "ativo": True},
        include={"modalidade": True},
    )

    if len(componentes) != len(componente_ids):
        raise HTTPException(
            status_code=422,
            detail="Um ou mais componentes curriculares não foram encontrados ou estão inativos",
        )

    if data.geraCertificado:
        nivel = await db.nivelensino.find_unique(where={"id": data.nivelEnsinoId})
        if not nivel:
            raise HTTPException(
                status_code=422,
                detail="Nível de ensino não encontrado para etapa certificadora",
            )

    qtd_facil = data.qtdFacil
    qtd_medio = data.qtdMedio
    qtd_dificil = data.qtdDificil
    questoes_selecionadas = None

    if data.questaoIds:
        ids_unicos = list(dict.fromkeys(data.questaoIds))
        slugs = [c.questionsSubjectSlug for c in componentes if c.questionsSubjectSlug]
        if not slugs:
            raise HTTPException(
                status_code=422,
                detail="Componente não está vinculado a uma matéria da API de questões",
            )
        faceis: set[str] = set()
        medias: set[str] = set()
        dificeis: set[str] = set()
        for slug in slugs:
            faceis |= {q.get("id") for q in await questions_api.listar_questoes(slug, "FACIL")}
            medias |= {q.get("id") for q in await questions_api.listar_questoes(slug, "MEDIO")}
            dificeis |= {q.get("id") for q in await questions_api.listar_questoes(slug, "DIFICIL")}
        validos = faceis | medias | dificeis
        if any(qid not in validos for qid in ids_unicos):
            raise HTTPException(
                status_code=422,
                detail="Há questões inválidas ou de outra matéria na seleção",
            )
        qtd_facil = sum(1 for qid in ids_unicos if qid in faceis)
        qtd_medio = sum(1 for qid in ids_unicos if qid in medias)
        qtd_dificil = sum(1 for qid in ids_unicos if qid in dificeis)
        questoes_selecionadas = Json(ids_unicos)
    else:
        # Sorteio automático: valida disponibilidade na API de questões,
        # somando o banco de TODOS os componentes da etapa (estilo ENEM).
        disponivel, faltas = await verificar_disponibilidade_multi(
            componente_ids, qtd_facil, qtd_medio, qtd_dificil
        )
        if not disponivel:
            raise HTTPException(status_code=422, detail=" · ".join(faltas))

    turmas_validas: list[str] = []
    for turma_id in data.turmaIds:
        turma = await db.turma.find_unique(where={"id": turma_id})
        if not turma:
            raise HTTPException(
                status_code=422,
                detail=f"Turma não encontrada: {turma_id}",
            )
        turmas_validas.append(turma_id)

    professor_demo = await db.professor.find_first()
    if not professor_demo:
        raise HTTPException(
            status_code=500,
            detail="Nenhum professor cadastrado no sistema. Rode seed_catalogo.py.",
        )

    novo = await db.simulado.create(
        data={
            "titulo": data.titulo,
            "descricao": data.descricao,
            "componente": {"connect": {"id": componente_principal_id}},
            "componenteIds": Json(componente_ids),
            "professor": {"connect": {"id": professor_demo.id}},
            "qtdFacil": qtd_facil,
            "qtdMedio": qtd_medio,
            "qtdDificil": qtd_dificil,
            "vagas": data.vagas,
            "duracaoMinutos": data.duracaoMinutos,
            "janelaInicio": data.janelaInicio,
            "janelaFim": data.janelaFim,
            "status": "PUBLICADO",
            "embaralharAlternativas": data.embaralharAlternativas,
            "geraCertificado": data.geraCertificado,
            "notaMinimaCertificacao": data.notaMinimaCertificacao,
            **(
                {"questoesSelecionadas": questoes_selecionadas}
                if questoes_selecionadas is not None
                else {}
            ),
            **(
                {"nivelEnsino": {"connect": {"id": data.nivelEnsinoId}}}
                if data.geraCertificado
                else {}
            ),
        },
        include=_INCLUDE_COMPLETO,
    )

    await _criar_aplicacoes(novo.id, turmas_validas, data.janelaInicio, data.janelaFim)

    simulado_completo = await db.simulado.find_unique(
        where={"id": novo.id},
        include=_INCLUDE_COMPLETO,
    )

    mapa_comp = await _mapa_componentes([simulado_completo])
    return _serializar_simulado(simulado_completo, componentes_por_id=mapa_comp)


@router.get("", response_model=list[SimuladoResponse])
async def listar_simulados(_=Depends(get_current_user)):
    simulados = await db.simulado.find_many(
        include=_INCLUDE_COMPLETO,
        order={"criadoEm": "desc"},
    )

    inscritos_por_simulado: dict[str, int] = {}
    if simulados:
        contagens = await db.inscricaoaluno.group_by(
            by=["simuladoId"],
            where={"simuladoId": {"in": [s.id for s in simulados]}},
            count=True,
        )
        inscritos_por_simulado = {
            c["simuladoId"]: c["_count"]["_all"] for c in contagens
        }

    mapa_comp = await _mapa_componentes(simulados)
    return [
        _serializar_simulado(s, inscritos_por_simulado.get(s.id, 0), mapa_comp)
        for s in simulados
    ]




def _turma_escola_dashboard(simulado_obj) -> str:
    if not simulado_obj.aplicacoes:
        return "Todas as turmas"

    valores = []

    for aplicacao in simulado_obj.aplicacoes:
        turma = aplicacao.turma

        if not turma:
            continue

        escola = turma.escola.nome if turma.escola else "Escola não informada"
        valores.append(f"{turma.nome} - {escola}")

    if not valores:
        return "Todas as turmas"

    return " / ".join(dict.fromkeys(valores))


async def _desempenho_por_escola() -> list[DesempenhoEscolaItem]:
    resultados = await db.resultadoaluno.find_many(
        where={"statusResultado": "FINALIZADO", "pontuacao": {"not": None}},
        include={
            "aluno": {
                "include": {
                    "turmas": {"include": {"turma": {"include": {"escola": True}}}}
                }
            }
        },
    )

    agregado: dict[str, dict] = {}

    for resultado in resultados:
        aluno = resultado.aluno
        if not aluno or not aluno.turmas:
            continue

        vinculo = next(
            (t for t in aluno.turmas if t.saiuEm is None and t.turma and t.turma.escola),
            None,
        )
        if not vinculo:
            continue

        escola = vinculo.turma.escola
        dados = agregado.setdefault(
            escola.id,
            {"nome": escola.nome, "soma": 0.0, "qtd": 0, "alunos": set()},
        )
        dados["soma"] += resultado.pontuacao
        dados["qtd"] += 1
        dados["alunos"].add(aluno.id)

    itens = [
        DesempenhoEscolaItem(
            escola=dados["nome"],
            media=round(dados["soma"] / dados["qtd"], 1),
            alunos=len(dados["alunos"]),
        )
        for dados in agregado.values()
        if dados["qtd"] > 0
    ]

    itens.sort(key=lambda item: item.media, reverse=True)
    return itens


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard_simulados(_=Depends(require_admin)):
    agora = _agora()

    simulados = await db.simulado.find_many(
        include=_INCLUDE_COMPLETO,
    )

    etapas_ativas = []
    etapas_finalizadas = 0

    for simulado in simulados:
        janela_inicio = _aware(simulado.janelaInicio)
        janela_fim = _aware(simulado.janelaFim)

        if simulado.status == "PUBLICADO" and janela_inicio <= agora <= janela_fim:
            etapas_ativas.append(simulado)

        if janela_fim < agora:
            etapas_finalizadas += 1

    em_execucao = []

    for simulado in etapas_ativas:
        iniciados = await db.resultadoaluno.count(
            where={
                "simuladoId": simulado.id,
            }
        )

        finalizados = await db.resultadoaluno.count(
            where={
                "simuladoId": simulado.id,
                "statusResultado": "FINALIZADO",
            }
        )

        em_execucao.append(
            DashboardEmExecucaoItem(
                id=simulado.id,
                titulo=simulado.titulo,
                componente=simulado.componente.nome,
                turmaEscola=_turma_escola_dashboard(simulado),
                janelaInicio=simulado.janelaInicio,
                janelaFim=simulado.janelaFim,
                iniciados=iniciados,
                finalizados=finalizados,
            )
        )

    desempenho_por_escola = await _desempenho_por_escola()

    return DashboardResponse(
        etapasAtivas=len(etapas_ativas),
        etapasFinalizadas=etapas_finalizadas,
        emExecucao=em_execucao,
        desempenhoPorEscola=desempenho_por_escola,
    )

@router.get("/{simulado_id}", response_model=SimuladoResponse)
async def buscar_simulado(simulado_id: str, _=Depends(get_current_user)):
    simulado = await db.simulado.find_unique(
        where={"id": simulado_id},
        include=_INCLUDE_COMPLETO,
    )
    if not simulado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")

    total_inscritos = await db.inscricaoaluno.count(
        where={"simuladoId": simulado_id}
    )
    mapa_comp = await _mapa_componentes([simulado])
    return _serializar_simulado(simulado, total_inscritos, mapa_comp)


@router.get("/{simulado_id}/relatorio", response_model=RelatorioEtapaResponse)
async def relatorio_etapa(simulado_id: str, _=Depends(require_admin)):
    simulado = await db.simulado.find_unique(
        where={"id": simulado_id},
        include={"componente": True},
    )
    if not simulado:
        raise HTTPException(status_code=404, detail="Etapa não encontrada")

    resultados = await db.resultadoaluno.find_many(
        where={"simuladoId": simulado_id},
        include={
            "aluno": {
                "include": {
                    "usuario": True,
                    "turmas": {
                        "where": {"saiuEm": None},
                        "include": {"turma": True},
                        "take": 1,
                    },
                }
            },
            "tentativasQuestoes": True,
        },
        order={"finalizadoEm": "desc"},
    )

    itens: list[RelatorioItemAluno] = []
    notas: list[float] = []
    finalizados = 0

    for r in resultados:
        aluno = r.aluno
        usuario = aluno.usuario if aluno else None
        vinculo = aluno.turmas[0] if aluno and aluno.turmas else None
        turma_nome = vinculo.turma.nome if vinculo and vinculo.turma else None

        total = len(r.tentativasQuestoes)
        concluido = r.statusResultado in ("FINALIZADO", "EXPIRADO")
        acertos = _contar_acertos(r.tentativasQuestoes) if concluido else None

        if r.statusResultado == "FINALIZADO":
            finalizados += 1
            if r.pontuacao is not None:
                notas.append(r.pontuacao)

        itens.append(RelatorioItemAluno(
            alunoNome=usuario.nome if usuario else "—",
            alunoCpf=usuario.cpf if usuario else "—",
            turma=turma_nome,
            nota=r.pontuacao,
            acertos=acertos,
            total=total,
            statusResultado=r.statusResultado,
            finalizadoEm=r.finalizadoEm,
        ))

    media = round(sum(notas) / len(notas), 1) if notas else None
    percentual = round(media * 10, 1) if media is not None else None

    total_inscritos = await db.inscricaoaluno.count(
        where={"simuladoId": simulado_id}
    )

    return RelatorioEtapaResponse(
        simuladoId=simulado.id,
        titulo=simulado.titulo,
        componente=simulado.componente.nome if simulado.componente else "—",
        inscritos=total_inscritos,
        totalAlunos=len(resultados),
        finalizados=finalizados,
        mediaNota=media,
        percentualAcerto=percentual,
        itens=itens,
    )