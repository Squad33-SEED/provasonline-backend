from fastapi import APIRouter, Depends, HTTPException, Query
from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    ComponenteResumo,
    DisponibilidadeQuestoes,
    ModalidadeResumo,
    SimuladoCreate,
    SimuladoResponse,
)
from src.services.sorteio_questoes import (
    contar_disponiveis,
    verificar_disponibilidade,
    gerar_questoes_simulado,  
)

router = APIRouter(prefix="/simulados", tags=["Simulados"])


def _serializar_simulado(simulado_obj) -> SimuladoResponse:
    componente = simulado_obj.componente
    modalidade = componente.modalidade

    total = simulado_obj.qtdFacil + simulado_obj.qtdMedio + simulado_obj.qtdDificil

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


@router.post("/criar", response_model=SimuladoResponse, status_code=201)
async def criar_simulado_livre(data: SimuladoCreate, _=Depends(get_current_user)):
    componente = await db.componentecurricular.find_unique(
        where={"id": data.componenteId},
        include={"modalidade": True},
    )
    if not componente or not componente.ativo:
        raise HTTPException(
            status_code=422,
            detail="Componente curricular não encontrado ou inativo",
        )

    componente_ids = [data.componenteId]
    if data.descricao and data.descricao.startswith("IDS:"):
        try:
            ids_extras = data.descricao.replace("IDS:", "").split(",")
            componente_ids = [i.strip() for i in ids_extras if i.strip()]
        except:
            pass

    disponivel, faltas = await verificar_disponibilidade(
        data.componenteId,
        data.qtdFacil,
        data.qtdMedio,
        data.qtdDificil,
        componente_ids=componente_ids,
    )
    if not disponivel:
        raise HTTPException(
            status_code=422,
            detail=" · ".join(faltas),
        )

    professor_demo = await db.professor.find_first()
    if not professor_demo:
        raise HTTPException(
            status_code=500,
            detail="Nenhum professor cadastrado no sistema. Rode seed_catalogo.py.",
        )

    novo = await db.simulado.create(
        data={
            "titulo": data.titulo or f"Simulado Livre - {componente.nome}",
            "descricao": data.descricao or "Simulado gerado automaticamente pelo aluno.",
            "componente": {"connect": {"id": data.componenteId}},
            "professor": {"connect": {"id": professor_demo.id}},
            "qtdFacil": data.qtdFacil,
            "qtdMedio": data.qtdMedio,
            "qtdDificil": data.qtdDificil,
            "vagas": data.vagas or 1,
            "duracaoMinutos": data.duracaoMinutos,
            "janelaInicio": data.janelaInicio,
            "janelaFim": data.janelaFim,
            "status": "PUBLICADO",
        },
        include={"componente": {"include": {"modalidade": True}}},
    )

    return _serializar_simulado(novo)


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

    componente_ids = [data.componenteId]
    if data.descricao and data.descricao.startswith("IDS:"):
        try:
            ids_extras = data.descricao.replace("IDS:", "").split(",")
            componente_ids = [i.strip() for i in ids_extras if i.strip()]
        except:
            pass

    disponivel, faltas = await verificar_disponibilidade(
        data.componenteId,
        data.qtdFacil,
        data.qtdMedio,
        data.qtdDificil,
        componente_ids=componente_ids,
    )
    if not disponivel:
        raise HTTPException(
            status_code=422,
            detail=" · ".join(faltas),
        )

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
        include={"componente": {"include": {"modalidade": True}}},
    )

    return _serializar_simulado(novo)


@router.get("", response_model=list[SimuladoResponse])
async def listar_simulados(_=Depends(get_current_user)):
    simulados = await db.simulado.find_many(
        include={"componente": {"include": {"modalidade": True}}},
        order={"criadoEm": "desc"},
    )

    return [_serializar_simulado(s) for s in simulados]


@router.get("/{simulado_id}", response_model=SimuladoResponse)
async def buscar_simulado(simulado_id: str, _=Depends(get_current_user)):
    simulados = await db.simulado.find_unique(
        where={"id": simulado_id},
        include={"componente": {"include": {"modalidade": True}}},
    )
    if not simulados:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")

    return _serializar_simulado(simulados)


@router.get("/{simulado_id}/questoes")
async def obter_questoes_do_simulado(simulado_id: str):   
    simulado = await db.simulado.find_unique(where={"id": simulado_id})
    
    if not simulado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    
    componente_ids = [simulado.componenteId]
    if simulado.descricao and simulado.descricao.startswith("IDS:"):
        try:
            ids_extras = simulado.descricao.replace("IDS:", "").split(",")
            componente_ids = [i.strip() for i in ids_extras if i.strip()]
        except:
            pass
        
    questoes = await gerar_questoes_simulado(
        componente_id=simulado.componenteId,
        qtd_facil=simulado.qtdFacil,
        qtd_medio=simulado.qtdMedio,
        qtd_dificil=simulado.qtdDificil,
        componente_ids=componente_ids
    )
    
    return questoes