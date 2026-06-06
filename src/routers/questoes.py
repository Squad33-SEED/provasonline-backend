from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Json

from src.database import db
from src.dependencies import get_current_user, require_professor
from src.schemas import (
    QuestaoCreate,
    QuestaoListItem,
    QuestaoResponse,
    QuestaoUpdate,
)

router = APIRouter(prefix="/questoes", tags=["Questões"])

_INCLUDE = {
    "componente": True,
    "assunto": True,
    "professor": {"include": {"usuario": True}},
}


async def _professor_do_usuario(usuario_id: str):
    professor = await db.professor.find_unique(where={"usuarioId": usuario_id})
    if not professor:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    return professor


async def _validar_componente_assunto(componente_id: str, assunto_id: str):
    componente = await db.componentecurricular.find_unique(where={"id": componente_id})
    if not componente or not componente.ativo:
        raise HTTPException(
            status_code=422,
            detail="Componente curricular não encontrado ou inativo",
        )

    assunto = await db.assunto.find_unique(where={"id": assunto_id})
    if not assunto or assunto.componenteId != componente_id:
        raise HTTPException(
            status_code=422,
            detail="Assunto não pertence ao componente selecionado",
        )


def _alternativas_list(valor) -> list:
    return valor if isinstance(valor, list) else []


def _serializar_questao(q) -> QuestaoResponse:
    return QuestaoResponse(
        id=q.id,
        enunciado=q.enunciado,
        componenteId=q.componenteId,
        componente=q.componente.nome if q.componente else "—",
        assuntoId=q.assuntoId,
        assunto=q.assunto.nome if q.assunto else "—",
        tipo=q.tipo,
        dificuldade=q.dificuldade,
        alternativas=_alternativas_list(q.alternativas),
        respostaCorreta=q.respostaCorreta,
        urlImagem=q.urlImagem,
        ativa=q.ativa,
        criadoEm=q.criadoEm,
    )


@router.post("", response_model=QuestaoResponse, status_code=201)
async def criar_questao(payload: QuestaoCreate, usuario=Depends(require_professor)):
    professor = await _professor_do_usuario(usuario.id)
    await _validar_componente_assunto(payload.componenteId, payload.assuntoId)

    questao = await db.questao.create(
        data={
            "professor": {"connect": {"id": professor.id}},
            "componente": {"connect": {"id": payload.componenteId}},
            "assunto": {"connect": {"id": payload.assuntoId}},
            "tipo": payload.tipo,
            "dificuldade": payload.dificuldade.value,
            "enunciado": payload.enunciado,
            "urlImagem": payload.urlImagem,
            "alternativas": Json([a.model_dump() for a in payload.alternativas]),
            "respostaCorreta": payload.respostaCorreta,
        },
        include=_INCLUDE,
    )
    return _serializar_questao(questao)


@router.get("", response_model=list[QuestaoListItem])
async def listar_questoes(
    componenteId: str | None = Query(default=None),
    assuntoId: str | None = Query(default=None),
    dificuldade: str | None = Query(default=None),
    ativa: bool | None = Query(default=None),
    somente_minhas: bool = Query(default=False),
    usuario=Depends(get_current_user),
):
    where: dict = {}
    if componenteId:
        where["componenteId"] = componenteId
    if assuntoId:
        where["assuntoId"] = assuntoId
    if dificuldade:
        where["dificuldade"] = dificuldade
    if ativa is not None:
        where["ativa"] = ativa
    if somente_minhas and usuario.tipo == "PROFESSOR":
        professor = await _professor_do_usuario(usuario.id)
        where["professorId"] = professor.id

    questoes = await db.questao.find_many(
        where=where,
        include=_INCLUDE,
        order={"criadoEm": "desc"},
    )

    resultado: list[QuestaoListItem] = []
    for q in questoes:
        usuario_professor = q.professor.usuario if q.professor else None
        resultado.append(
            QuestaoListItem(
                id=q.id,
                enunciado=q.enunciado,
                componente=q.componente.nome if q.componente else "—",
                assunto=q.assunto.nome if q.assunto else "—",
                tipo=q.tipo,
                dificuldade=q.dificuldade,
                ativa=q.ativa,
                totalAlternativas=len(_alternativas_list(q.alternativas)),
                professorNome=usuario_professor.nome if usuario_professor else "—",
            )
        )
    return resultado


@router.get("/{questao_id}", response_model=QuestaoResponse)
async def buscar_questao(questao_id: str, usuario=Depends(get_current_user)):
    questao = await db.questao.find_unique(where={"id": questao_id}, include=_INCLUDE)
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return _serializar_questao(questao)


@router.put("/{questao_id}", response_model=QuestaoResponse)
async def editar_questao(
    questao_id: str, payload: QuestaoUpdate, usuario=Depends(require_professor)
):
    professor = await _professor_do_usuario(usuario.id)

    questao = await db.questao.find_unique(where={"id": questao_id})
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    if questao.professorId != professor.id:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: esta questão não pertence a você",
        )

    await _validar_componente_assunto(payload.componenteId, payload.assuntoId)

    atualizada = await db.questao.update(
        where={"id": questao_id},
        data={
            "componente": {"connect": {"id": payload.componenteId}},
            "assunto": {"connect": {"id": payload.assuntoId}},
            "tipo": payload.tipo,
            "dificuldade": payload.dificuldade.value,
            "enunciado": payload.enunciado,
            "urlImagem": payload.urlImagem,
            "alternativas": Json([a.model_dump() for a in payload.alternativas]),
            "respostaCorreta": payload.respostaCorreta,
        },
        include=_INCLUDE,
    )
    return _serializar_questao(atualizada)


@router.patch("/{questao_id}/toggle", response_model=QuestaoResponse)
async def alternar_questao(questao_id: str, usuario=Depends(get_current_user)):
    if usuario.tipo not in ("PROFESSOR", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a professores ou administradores",
        )

    questao = await db.questao.find_unique(where={"id": questao_id})
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")

    if usuario.tipo == "PROFESSOR":
        professor = await _professor_do_usuario(usuario.id)
        if questao.professorId != professor.id:
            raise HTTPException(
                status_code=403,
                detail="Acesso negado: esta questão não pertence a você",
            )

    if questao.ativa:
        em_andamento = await db.tentativaquestao.find_first(
            where={
                "questaoId": questao_id,
                "resultado": {"is": {"statusResultado": "EM_ANDAMENTO"}},
            }
        )
        if em_andamento:
            raise HTTPException(
                status_code=422,
                detail="Questão em uso em etapa em andamento não pode ser desativada",
            )

    atualizada = await db.questao.update(
        where={"id": questao_id},
        data={"ativa": not questao.ativa},
        include=_INCLUDE,
    )
    return _serializar_questao(atualizada)
