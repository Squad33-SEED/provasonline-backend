from fastapi import APIRouter, Depends

from src.database import db
from src.dependencies import require_admin
from src.schemas import ProfessorResumo

router = APIRouter(prefix="/professores", tags=["Professores"])


@router.get("", response_model=list[ProfessorResumo])
async def listar_professores(_=Depends(require_admin)):
    professores = await db.professor.find_many(include={"usuario": True})

    resumos = [
        ProfessorResumo(
            id=p.id,
            nome=p.usuario.nome if p.usuario else "—",
            cpf=p.usuario.cpf if p.usuario else "—",
            especialidade=p.especialidade,
        )
        for p in professores
        if not p.usuario or p.usuario.ativo
    ]
    resumos.sort(key=lambda r: r.nome.lower())
    return resumos
