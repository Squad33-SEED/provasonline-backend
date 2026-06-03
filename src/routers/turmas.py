from fastapi import APIRouter, Depends, HTTPException, Query

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    EscolaResumo,
    ModalidadeResumo,
    ProfessorResumo,
    ProfessorVinculoCreate,
    TurmaCreate,
    TurmaResponse,
)


def _professor_resumo(professor) -> "ProfessorResumo":
    return ProfessorResumo(
        id=professor.id,
        nome=professor.usuario.nome if professor.usuario else "—",
        cpf=professor.usuario.cpf if professor.usuario else "—",
        especialidade=professor.especialidade,
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


@router.get("/{turma_id}/professores", response_model=list[ProfessorResumo])
async def listar_professores_da_turma(turma_id: str, _=Depends(require_admin)):
    turma = await db.turma.find_unique(where={"id": turma_id})
    if not turma:
        raise HTTPException(status_code=404, detail="Turma não encontrada")

    vinculos = await db.professorturma.find_many(
        where={"turmaId": turma_id},
        include={"professor": {"include": {"usuario": True}}},
    )

    resumos = [_professor_resumo(v.professor) for v in vinculos if v.professor]
    resumos.sort(key=lambda r: r.nome.lower())
    return resumos


@router.post("/{turma_id}/professores", response_model=ProfessorResumo, status_code=201)
async def vincular_professor(
    turma_id: str, data: ProfessorVinculoCreate, _=Depends(require_admin)
):
    turma = await db.turma.find_unique(where={"id": turma_id})
    if not turma:
        raise HTTPException(status_code=404, detail="Turma não encontrada")

    professor = await db.professor.find_unique(
        where={"id": data.professorId},
        include={"usuario": True},
    )
    if not professor:
        raise HTTPException(status_code=422, detail="Professor não encontrado")

    existente = await db.professorturma.find_unique(
        where={
            "professorId_turmaId": {
                "professorId": data.professorId,
                "turmaId": turma_id,
            }
        }
    )
    if existente:
        raise HTTPException(
            status_code=409, detail="Professor já vinculado a esta turma"
        )

    await db.professorturma.create(
        data={
            "professor": {"connect": {"id": data.professorId}},
            "turma": {"connect": {"id": turma_id}},
        }
    )

    return _professor_resumo(professor)


@router.delete("/{turma_id}/professores/{professor_id}", status_code=204)
async def desvincular_professor(
    turma_id: str, professor_id: str, _=Depends(require_admin)
):
    existente = await db.professorturma.find_unique(
        where={
            "professorId_turmaId": {
                "professorId": professor_id,
                "turmaId": turma_id,
            }
        }
    )
    if not existente:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")

    await db.professorturma.delete(
        where={
            "professorId_turmaId": {
                "professorId": professor_id,
                "turmaId": turma_id,
            }
        }
    )