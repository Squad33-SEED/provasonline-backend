from fastapi import APIRouter, Depends, HTTPException

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    AssuntoCreate,
    AssuntoResponse,
    AssuntoResponseSimples,
    AssuntoResumo,
    ComponenteCreate,
    ComponenteResponse,
    ComponenteResumo,
    ComponenteUpdate,
    EscolaResumo,
    ModalidadeCreate,
    ModalidadeResponse,
    ModalidadeResumo,
    ModalidadeUpdate,
    NivelCreate,
    NivelResponse,
    NivelResumo,
    NivelUpdate,
)

router = APIRouter(prefix="/catalogo", tags=["Catálogo"])

async def _desativar_componentes_em_cascata(componente_ids: list[str]) -> None:
    """Desativa os componentes informados + seus assuntos e questões.
    Cascata do catálogo: não toca em simulados publicados (provas em andamento)."""
    if not componente_ids:
        return
    await db.assunto.update_many(
        where={"componenteId": {"in": componente_ids}}, data={"ativo": False}
    )
    await db.questao.update_many(
        where={"componenteId": {"in": componente_ids}}, data={"ativa": False}
    )
    await db.componentecurricular.update_many(
        where={"id": {"in": componente_ids}}, data={"ativo": False}
    )


async def _desativar_modalidades_em_cascata(modalidade_ids: list[str]) -> None:
    """Desativa as modalidades + seus componentes (e descendentes). Não toca em turmas."""
    if not modalidade_ids:
        return
    comps = await db.componentecurricular.find_many(
        where={"modalidadeId": {"in": modalidade_ids}}
    )
    await _desativar_componentes_em_cascata([c.id for c in comps])
    await db.modalidade.update_many(
        where={"id": {"in": modalidade_ids}}, data={"ativo": False}
    )

@router.get("/niveis", response_model=list[NivelResumo])
async def listar_niveis(_=Depends(get_current_user)):
    niveis = await db.nivelensino.find_many(
        where={"ativo": True},
        order=[{"ordem": "asc"}, {"nome": "asc"}],
    )
    return [NivelResumo(id=n.id, nome=n.nome, ordem=n.ordem) for n in niveis]


@router.get("/escolas", response_model=list[EscolaResumo])
async def listar_escolas(_=Depends(get_current_user)):
    escolas = await db.escola.find_many(
        where={"ativo": True},
        order={"nome": "asc"},
    )
    return [EscolaResumo(id=e.id, nome=e.nome) for e in escolas]


@router.get("/modalidades", response_model=list[ModalidadeResumo])
async def listar_modalidades(_=Depends(get_current_user)):
    modalidades = await db.modalidade.find_many(
        where={"ativo": True},
        include={"nivel": True},
        order=[{"nivelId": "asc"}, {"nome": "asc"}],
    )
    return [
        ModalidadeResumo(id=m.id, nome=f"{m.nivel.nome} — {m.nome}")
        for m in modalidades
    ]


@router.get("/componentes", response_model=list[ComponenteResumo])
async def listar_componentes(_=Depends(get_current_user)):
    componentes = await db.componentecurricular.find_many(
        where={"ativo": True},
        include={
            "modalidade": {"include": {"nivel": True}},
            "assuntos": {"where": {"ativo": True}},
        },
        order={"nome": "asc"},
    )
    resultado = []
    for c in componentes:
        modalidade = c.modalidade
        nome_modalidade = f"{modalidade.nivel.nome} — {modalidade.nome}"
        assuntos = sorted(c.assuntos or [], key=lambda a: a.nome)
        resultado.append(
            ComponenteResumo(
                id=c.id,
                nome=c.nome,
                modalidade=ModalidadeResumo(id=modalidade.id, nome=nome_modalidade),
                assuntos=[AssuntoResumo(id=a.id, nome=a.nome) for a in assuntos],
            )
        )
    return resultado

@router.get("/assuntos/nomes-existentes", response_model=list[str])
async def listar_nomes_assuntos(_=Depends(require_admin)):
    assuntos = await db.assunto.find_many()
    nomes = sorted(set(a.nome for a in assuntos))
    return nomes


@router.get("/assuntos/{componente_id}", response_model=list[AssuntoResumo])
async def listar_assuntos(componente_id: str, _=Depends(get_current_user)):
    assuntos = await db.assunto.find_many(
        where={"componenteId": componente_id, "ativo": True},
        order={"nome": "asc"},
    )
    return [AssuntoResumo(id=a.id, nome=a.nome) for a in assuntos]

@router.post("/niveis", response_model=NivelResponse, status_code=201)
async def criar_nivel(data: NivelCreate, _=Depends(require_admin)):
    nivel = await db.nivelensino.create(
        data={
            "nome": data.nome,
            "descricao": data.descricao,
            "ordem": data.ordem,
        }
    )
    return NivelResponse(
        id=nivel.id,
        nome=nivel.nome,
        descricao=nivel.descricao,
        ordem=nivel.ordem,
        ativo=nivel.ativo,
    )


@router.get("/niveis/admin", response_model=list[NivelResponse])
async def listar_niveis_admin(_=Depends(require_admin)):
    niveis = await db.nivelensino.find_many(
        order=[{"ativo": "desc"}, {"ordem": "asc"}, {"nome": "asc"}],
    )
    return [
        NivelResponse(
            id=n.id,
            nome=n.nome,
            descricao=n.descricao,
            ordem=n.ordem,
            ativo=n.ativo,
        )
        for n in niveis
    ]


@router.put("/niveis/{nivel_id}", response_model=NivelResponse)
async def editar_nivel(nivel_id: str, data: NivelUpdate, _=Depends(require_admin)):
    nivel = await db.nivelensino.find_unique(where={"id": nivel_id})
    if not nivel:
        raise HTTPException(status_code=404, detail="Nível não encontrado")
    atualizado = await db.nivelensino.update(
        where={"id": nivel_id},
        data={"nome": data.nome, "descricao": data.descricao}
    )
    return NivelResponse(
        id=atualizado.id,
        nome=atualizado.nome,
        descricao=atualizado.descricao,
        ordem=atualizado.ordem,
        ativo=atualizado.ativo,
    )


@router.patch("/niveis/{nivel_id}/toggle", response_model=NivelResponse)
async def toggle_nivel(nivel_id: str, _=Depends(require_admin)):
    nivel = await db.nivelensino.find_unique(where={"id": nivel_id})
    if not nivel:
        raise HTTPException(status_code=404, detail="Nível não encontrado")

    # Ao desativar, cascateia para modalidades/componentes/assuntos/questões.
    # Reativar não cascateia (o admin reativa os filhos seletivamente).
    if nivel.ativo:
        mods = await db.modalidade.find_many(where={"nivelId": nivel_id})
        await _desativar_modalidades_em_cascata([m.id for m in mods])

    atualizado = await db.nivelensino.update(
        where={"id": nivel_id},
        data={"ativo": not nivel.ativo},
    )
    return NivelResponse(
        id=atualizado.id,
        nome=atualizado.nome,
        descricao=atualizado.descricao,
        ordem=atualizado.ordem,
        ativo=atualizado.ativo,
    )

@router.post("/modalidades", response_model=ModalidadeResponse, status_code=201)
async def criar_modalidade(data: ModalidadeCreate, _=Depends(require_admin)):
    nivel = await db.nivelensino.find_unique(where={"id": data.nivelId})
    if not nivel or not nivel.ativo:
        raise HTTPException(status_code=422, detail="Nível não encontrado ou inativo")

    modalidade = await db.modalidade.create(
        data={
            "nome": data.nome,
            "supletivo": data.supletivo,
            "nivel": {"connect": {"id": data.nivelId}},
        }
    )
    return ModalidadeResponse(
        id=modalidade.id,
        nivelId=modalidade.nivelId,
        nome=modalidade.nome,
        supletivo=modalidade.supletivo,
        ativo=modalidade.ativo,
    )


@router.put("/modalidades/{modalidade_id}", response_model=ModalidadeResponse)
async def editar_modalidade(
    modalidade_id: str, data: ModalidadeUpdate, _=Depends(require_admin)
):
    modalidade = await db.modalidade.find_unique(where={"id": modalidade_id})
    if not modalidade:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada")

    atualizada = await db.modalidade.update(
        where={"id": modalidade_id},
        data={"nome": data.nome, "supletivo": data.supletivo},
    )
    return ModalidadeResponse(
        id=atualizada.id,
        nivelId=atualizada.nivelId,
        nome=atualizada.nome,
        supletivo=atualizada.supletivo,
        ativo=atualizada.ativo,
    )


@router.patch("/modalidades/{modalidade_id}/toggle", response_model=ModalidadeResponse)
async def toggle_modalidade(modalidade_id: str, _=Depends(require_admin)):
    modalidade = await db.modalidade.find_unique(where={"id": modalidade_id})
    if not modalidade:
        raise HTTPException(status_code=404, detail="Modalidade não encontrada")

    # Ao desativar, cascateia para os componentes (e descendentes). Turmas não
    # são tocadas. Reativar não cascateia.
    if modalidade.ativo:
        comps = await db.componentecurricular.find_many(
            where={"modalidadeId": modalidade_id}
        )
        await _desativar_componentes_em_cascata([c.id for c in comps])

    atualizada = await db.modalidade.update(
        where={"id": modalidade_id},
        data={"ativo": not modalidade.ativo},
    )
    return ModalidadeResponse(
        id=atualizada.id,
        nivelId=atualizada.nivelId,
        nome=atualizada.nome,
        supletivo=atualizada.supletivo,
        ativo=atualizada.ativo,
    )


@router.get("/modalidades/admin", response_model=list[ModalidadeResponse])
async def listar_modalidades_admin(_=Depends(require_admin)):
    modalidades = await db.modalidade.find_many(
        order=[{"nivelId": "asc"}, {"nome": "asc"}],
    )
    return [
        ModalidadeResponse(
            id=m.id,
            nivelId=m.nivelId,
            nome=m.nome,
            supletivo=m.supletivo,
            ativo=m.ativo,
        )
        for m in modalidades
    ]

@router.post("/componentes", response_model=ComponenteResponse, status_code=201)
async def criar_componente(data: ComponenteCreate, _=Depends(require_admin)):
    modalidade = await db.modalidade.find_unique(where={"id": data.modalidadeId})
    if not modalidade or not modalidade.ativo:
        raise HTTPException(status_code=422, detail="Modalidade não encontrada ou inativa")

    slug = (data.questionsSubjectSlug or "").strip() or None
    componente = await db.componentecurricular.create(
        data={
            "nome": data.nome,
            "codigo": data.codigo,
            "questionsSubjectSlug": slug,
            "modalidade": {"connect": {"id": data.modalidadeId}},
        }
    )

    assuntos_criados = []
    for nome_assunto in data.assuntos:
        if nome_assunto.strip():
            a = await db.assunto.create(
                data={
                    "nome": nome_assunto.strip(),
                    "componente": {"connect": {"id": componente.id}},
                }
            )
            assuntos_criados.append(AssuntoResponseSimples(id=a.id, nome=a.nome, ativo=a.ativo))

    return ComponenteResponse(
        id=componente.id,
        modalidadeId=componente.modalidadeId,
        nome=componente.nome,
        codigo=componente.codigo,
        ativo=componente.ativo,
        questionsSubjectSlug=componente.questionsSubjectSlug,
        totalAssuntos=len(assuntos_criados),
        totalQuestoes=0,
        assuntos=assuntos_criados,
    )


@router.put("/componentes/{componente_id}", response_model=ComponenteResponse)
async def editar_componente(
    componente_id: str, data: ComponenteUpdate, _=Depends(require_admin)
):
    componente = await db.componentecurricular.find_unique(where={"id": componente_id})
    if not componente:
        raise HTTPException(status_code=404, detail="Componente não encontrado")

    slug = (data.questionsSubjectSlug or "").strip() or None
    atualizado = await db.componentecurricular.update(
        where={"id": componente_id},
        data={"nome": data.nome, "codigo": data.codigo, "questionsSubjectSlug": slug},
    )
    return ComponenteResponse(
        id=atualizado.id,
        modalidadeId=atualizado.modalidadeId,
        nome=atualizado.nome,
        codigo=atualizado.codigo,
        ativo=atualizado.ativo,
        questionsSubjectSlug=atualizado.questionsSubjectSlug,
    )


@router.patch("/componentes/{componente_id}/toggle", response_model=ComponenteResponse)
async def toggle_componente(componente_id: str, _=Depends(require_admin)):
    componente = await db.componentecurricular.find_unique(where={"id": componente_id})
    if not componente:
        raise HTTPException(status_code=404, detail="Componente não encontrado")

    # Ao desativar, cascateia para assuntos e questões. Simulados publicados não
    # são tocados (não derruba provas em andamento). Reativar não cascateia.
    if componente.ativo:
        await db.assunto.update_many(
            where={"componenteId": componente_id}, data={"ativo": False}
        )
        await db.questao.update_many(
            where={"componenteId": componente_id}, data={"ativa": False}
        )

    atualizado = await db.componentecurricular.update(
        where={"id": componente_id},
        data={"ativo": not componente.ativo},
    )
    n_assuntos = await db.assunto.count(where={"componenteId": componente_id, "ativo": True})
    n_questoes_total = await db.questao.count(where={"componenteId": componente_id})
    return ComponenteResponse(
        id=atualizado.id,
        modalidadeId=atualizado.modalidadeId,
        nome=atualizado.nome,
        codigo=atualizado.codigo,
        ativo=atualizado.ativo,
        questionsSubjectSlug=atualizado.questionsSubjectSlug,
        totalAssuntos=n_assuntos,
        totalQuestoes=n_questoes_total,
    )

@router.post(
    "/componentes/{componente_id}/assuntos",
    response_model=AssuntoResponse,
    status_code=201,
)
async def criar_assunto(
    componente_id: str, data: AssuntoCreate, _=Depends(require_admin)
):
    componente = await db.componentecurricular.find_unique(where={"id": componente_id})
    if not componente or not componente.ativo:
        raise HTTPException(status_code=422, detail="Componente não encontrado ou inativo")

    assunto = await db.assunto.create(
        data={
            "nome": data.nome,
            "componente": {"connect": {"id": componente_id}},
        }
    )
    return AssuntoResponse(
        id=assunto.id,
        componenteId=assunto.componenteId,
        nome=assunto.nome,
        ativo=assunto.ativo,
    )

@router.get("/componentes/admin", response_model=list[ComponenteResponse])
async def listar_componentes_admin(_=Depends(require_admin)):
    componentes = await db.componentecurricular.find_many(
        include={"assuntos": {"where": {"ativo": True}}},
        order={"nome": "asc"},
    )

    todas_questoes = await db.questao.find_many()
    contagem: dict[str, int] = {}
    for q in todas_questoes:
        contagem[q.componenteId] = contagem.get(q.componenteId, 0) + 1

    resultado = []
    for c in componentes:
        assuntos = sorted(c.assuntos or [], key=lambda a: a.nome)
        resultado.append(
            ComponenteResponse(
                id=c.id,
                modalidadeId=c.modalidadeId,
                nome=c.nome,
                codigo=c.codigo,
                ativo=c.ativo,
                questionsSubjectSlug=c.questionsSubjectSlug,
                totalAssuntos=len(assuntos),
                totalQuestoes=contagem.get(c.id, 0),
                assuntos=[AssuntoResponseSimples(id=a.id, nome=a.nome, ativo=a.ativo) for a in assuntos],
            )
        )
    return resultado


@router.patch("/assuntos/{assunto_id}/toggle", response_model=AssuntoResponse)
async def toggle_assunto(assunto_id: str, _=Depends(require_admin)):
    assunto = await db.assunto.find_unique(where={"id": assunto_id})
    if not assunto:
        raise HTTPException(status_code=404, detail="Assunto não encontrado")

    if assunto.ativo:
        n_questoes = await db.questao.count(
            where={"assuntoId": assunto_id, "ativa": True}
        )
        if n_questoes > 0:
            raise HTTPException(
                status_code=422,
                detail=_msg_bloqueio([f"{n_questoes} questão(ões)"]),
            )

    atualizado = await db.assunto.update(
        where={"id": assunto_id},
        data={"ativo": not assunto.ativo},
    )
    return AssuntoResponse(
        id=atualizado.id,
        componenteId=atualizado.componenteId,
        nome=atualizado.nome,
        ativo=atualizado.ativo,
    )
    
@router.get("/assuntos/todos/{componente_id}", response_model=list[AssuntoResponse])
async def listar_todos_assuntos(componente_id: str, _=Depends(require_admin)):
    assuntos = await db.assunto.find_many(
        where={"componenteId": componente_id},
        order={"nome": "asc"},
    )
    return [
        AssuntoResponse(
            id=a.id,
            componenteId=a.componenteId,
            nome=a.nome,
            ativo=a.ativo,
        )
        for a in assuntos
    ]