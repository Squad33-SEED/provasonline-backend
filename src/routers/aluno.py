from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.database import db
from src.dependencies import get_current_user

router = APIRouter(prefix="/aluno", tags=["Aluno"])


class ComponenteResumo(BaseModel):
    id: str
    nome: str
    modalidade: str


class EtapaDisponivelResponse(BaseModel):
    id: str
    titulo: str
    descricao: str | None
    componente: ComponenteResumo
    duracaoMinutos: int
    totalQuestoes: int
    vagas: int
    janelaInicio: datetime
    janelaFim: datetime
    ativa: bool


@router.get("/etapas-disponiveis", response_model=list[EtapaDisponivelResponse])
async def etapas_disponiveis(_=Depends(get_current_user)):
    agora = datetime.now(timezone.utc)

    simulados = await db.simulado.find_many(
        where={
            "status": "PUBLICADO",
            "janelaFim": {"gte": agora},
        },
        include={
            "componente": {
                "include": {"modalidade": True}
            }
        },
        order={"janelaInicio": "asc"},
    )

    return [
        EtapaDisponivelResponse(
            id=s.id,
            titulo=s.titulo,
            descricao=s.descricao,
            componente=ComponenteResumo(
                id=s.componente.id,
                nome=s.componente.nome,
                modalidade=s.componente.modalidade.nome,
            ),
            duracaoMinutos=s.duracaoMinutos,
            totalQuestoes=s.qtdFacil + s.qtdMedio + s.qtdDificil,
            vagas=s.vagas,
            janelaInicio=s.janelaInicio,
            janelaFim=s.janelaFim,
            ativa=s.janelaInicio <= agora,
        )
        for s in simulados
    ]