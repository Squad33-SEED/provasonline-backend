from fastapi import APIRouter, Depends, HTTPException, Query

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    ComponenteResumo,
    DisponibilidadeQuestoes,
    ModalidadeResumo,
    SimuladoCreate,
    SimuladoResponse,
    TurmaResumoSimples,
)
from src.services.sorteio_questoes import (
    contar_disponiveis,
    verificar_disponibilidade,
)

router = APIRouter(prefix="/simulados", tags=["Simulados"])

_INCLUDE_COMPLETO = {
    "componente": {"include": {"modalidade": True}},
    "aplicacoes": {"include": {"turma": {"include": {"escola": True}}}},
}


def _serializar_simulado(simulado_obj) -> SimuladoResponse:
    componente = simulado_obj.componente
    modalidade = componente.modalidade
    total = simulado_obj.qtdFacil + simulado_obj.qtdMedio + simulado_obj.qtdDificil

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
        componente=ComponenteResumo(
            id=componente.id,
            nome=componente.nome,
            modalidade=ModalidadeResumo(
                id=modalidade.id,
                nome=modalidade.nome,
            ),
        ),
        qtdFacil=simulado_obj.qtdFacil,
        qtdMedio=simulado_obj.qtdMedio,
        qtdDificil=simulado_obj.qtdDificil,
        totalQuestoes=total,
        vagas=simulado_obj.vagas,
        duracaoMinutos=simulado_obj.duracaoMinutos,
        janelaInicio=simulado_obj.janelaInicio,
        janelaFim=simulado_obj.janelaFim,
        status=simulado_obj.status,
        criadoEm=simulado_obj.criadoEm,
        turmas=turmas,
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

    contadores = await contar_disponiveis(componenteId)

    return DisponibilidadeQuestoes(
        componenteId=componenteId,
        facil=contadores["facil"],
        medio=contadores["medio"],
        dificil=contadores["dificil"],
    )


@router.post("", response_model=SimuladoResponse, status_code=201)
async def criar_simulado(data: SimuladoCreate, _=Depends(require_admin)):
    componente = await db.componentecurricular.find_unique(
        where={"id": data.componenteId},
        include={"modalidade": True},
    )
    if not componente or not componente.ativo:
        raise HTTPException(
            status_code=422,
            detail="Componente curricular não encontrado ou inativo",
        )

    disponivel, faltas = await verificar_disponibilidade(
        data.componenteId,
        data.qtdFacil,
        data.qtdMedio,
        data.qtdDificil,
    )
    if not disponivel:
        raise HTTPException(
            status_code=422,
            detail=" · ".join(faltas),
        )

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
            "componente": {"connect": {"id": data.componenteId}},
            "professor": {"connect": {"id": professor_demo.id}},
            "qtdFacil": data.qtdFacil,
            "qtdMedio": data.qtdMedio,
            "qtdDificil": data.qtdDificil,
            "vagas": data.vagas,
            "duracaoMinutos": data.duracaoMinutos,
            "janelaInicio": data.janelaInicio,
            "janelaFim": data.janelaFim,
            "status": "PUBLICADO",
        },
        include=_INCLUDE_COMPLETO,
    )

    for turma_id in turmas_validas:
        await db.aplicacao.create(
            data={
                "simulado": {"connect": {"id": novo.id}},
                "turma": {"connect": {"id": turma_id}},
                "dataInicio": data.janelaInicio,
                "dataFim": data.janelaFim,
                "status": "AGENDADA",
            }
        )

    simulado_completo = await db.simulado.find_unique(
        where={"id": novo.id},
        include=_INCLUDE_COMPLETO,
    )

    return _serializar_simulado(simulado_completo)


@router.get("", response_model=list[SimuladoResponse])
async def listar_simulados(_=Depends(get_current_user)):
    simulados = await db.simulado.find_many(
        include=_INCLUDE_COMPLETO,
        order={"criadoEm": "desc"},
    )
    return [_serializar_simulado(s) for s in simulados]


@router.get("/{simulado_id}", response_model=SimuladoResponse)
async def buscar_simulado(simulado_id: str, _=Depends(get_current_user)):
    simulado = await db.simulado.find_unique(
        where={"id": simulado_id},
        include=_INCLUDE_COMPLETO,
    )
    if not simulado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    return _serializar_simulado(simulado)