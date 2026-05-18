from fastapi import APIRouter, Depends, HTTPException, Query

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    EscolaResumo,
    ModalidadeResumo,
    TurmaCreate,
    TurmaResponse,
)

router = APIRouter(prefix="/turmas", tags=["Turmas"])


def _serializar_turma(turma_obj, total_alunos: int) -> TurmaResponse:
    return TurmaResponse(
        id=turma_obj.id,
        nome=turma_obj.nome,
        anoLetivo=turma_obj.anoLetivo,
        escola=EscolaResumo(id=turma_obj.escola.id, nome=turma_obj.escola.nome),
        modalidade=ModalidadeResumo(
            id=turma_obj.modalidade.id, nome=turma_obj.modalidade.nome
        ),
        totalAlunos=total_alunos,
    )


@router.post("", response_model=TurmaResponse, status_code=201)
async def criar_turma(data: TurmaCreate, _=Depends(require_admin)):
    escola = await db.escola.find_unique(where={"id": data.escolaId})
    if not escola or not escola.ativo:
        raise HTTPException(status_code=422, detail="Escola não encontrada ou inativa")

    modalidade = await db.modalidade.find_unique(where={"id": data.modalidadeId})
    if not modalidade or not modalidade.ativo:
        raise HTTPException(
            status_code=422, detail="Modalidade não encontrada ou inativa"
        )

    duplicada = await db.turma.find_first(
        where={
            "escolaId": data.escolaId,
            "nome": data.nome,
            "anoLetivo": data.anoLetivo,
        },
    )
    if duplicada:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma turma com este nome nesta escola e ano letivo",
        )

    nova = await db.turma.create(
        data={
            "nome": data.nome,
            "anoLetivo": data.anoLetivo,
            "escolaId": data.escolaId,
            "modalidadeId": data.modalidadeId,
        },
        include={"escola": True, "modalidade": True},
    )

    return _serializar_turma(nova, total_alunos=0)


@router.get("", response_model=list[TurmaResponse])
async def listar_turmas(
    _=Depends(get_current_user),
    escola_id: str | None = Query(default=None),
    ano_letivo: int | None = Query(default=None, ge=2024, le=2030),
):
    where: dict = {}
    if escola_id:
        where["escolaId"] = escola_id
    if ano_letivo:
        where["anoLetivo"] = ano_letivo

    turmas = await db.turma.find_many(
        where=where,
        include={"escola": True, "modalidade": True},
        order={"anoLetivo": "desc"},
    )

    resultado = []
    for t in turmas:
        total = await db.turmaaluno.count(where={"turmaId": t.id, "saiuEm": None})
        resultado.append(_serializar_turma(t, total))

    return resultado


@router.get("/{turma_id}", response_model=TurmaResponse)
async def buscar_turma(turma_id: str, _=Depends(get_current_user)):
    turma = await db.turma.find_unique(
        where={"id": turma_id},
        include={"escola": True, "modalidade": True},
    )
    if not turma:
        raise HTTPException(status_code=404, detail="Turma não encontrada")

    total = await db.turmaaluno.count(where={"turmaId": turma.id, "saiuEm": None})
    return _serializar_turma(turma, total)