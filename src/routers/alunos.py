from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import AlunoCreate, AlunoCreateResponse, AlunoListItem
from src.security import hash_password
from src.services.cpf_validator import validar_cpf
from src.services.senha_provisoria import gerar_senha_provisoria

router = APIRouter(prefix="/alunos", tags=["Alunos"])


@router.post("", response_model=AlunoCreateResponse, status_code=201)
async def criar_aluno(data: AlunoCreate, _=Depends(require_admin)):
    if not validar_cpf(data.cpf):
        raise HTTPException(status_code=422, detail="CPF inválido")

    cpf_existente = await db.usuario.find_unique(where={"cpf": data.cpf})
    if cpf_existente:
        raise HTTPException(status_code=409, detail="CPF já cadastrado")

    if data.email:
        email_existente = await db.usuario.find_unique(where={"email": data.email})
        if email_existente:
            raise HTTPException(status_code=409, detail="Email já cadastrado")

    if data.turmaId:
        turma = await db.turma.find_unique(where={"id": data.turmaId})
        if not turma:
            raise HTTPException(status_code=422, detail="Turma não encontrada")

    senha_provisoria = gerar_senha_provisoria(data.dataNascimento)
    senha_hash = hash_password(senha_provisoria)
    data_nascimento_dt = datetime.combine(data.dataNascimento, datetime.min.time())

    async with db.tx() as transaction:
        novo_usuario = await transaction.usuario.create(
            data={
                "nome": data.nome,
                "email": data.email,
                "cpf": data.cpf,
                "senhaHash": senha_hash,
                "senhaProvisoria": True,
                "tipo": "ALUNO",
                "ativo": True,
            },
        )

        novo_aluno = await transaction.aluno.create(
            data={
                "usuarioId": novo_usuario.id,
                "dataNascimento": data_nascimento_dt,
                "necessidadeEspecial": data.necessidadeEspecial,
            },
        )

        if data.turmaId:
            await transaction.turmaaluno.create(
                data={
                    "turmaId": data.turmaId,
                    "alunoId": novo_aluno.id,
                    "entrouEm": datetime.combine(date.today(), datetime.min.time()),
                },
            )

    return AlunoCreateResponse(
        id=novo_aluno.id,
        usuarioId=novo_usuario.id,
        nome=novo_usuario.nome,
        cpf=novo_usuario.cpf,
        email=novo_usuario.email,
        senhaProvisoria=senha_provisoria,
        dataNascimento=data.dataNascimento,
        turmaId=data.turmaId,
    )


@router.get("", response_model=list[AlunoListItem])
async def listar_alunos(
    _=Depends(get_current_user),
    turma_id: str | None = Query(default=None),
    escola_id: str | None = Query(default=None),
    busca: str | None = Query(default=None, max_length=100),
):
    where_aluno: dict = {}

    if busca and len(busca.strip()) > 0:
        termo = busca.strip()
        if termo.isdigit():
            where_aluno["usuario"] = {"is": {"cpf": {"contains": termo}}}
        else:
            where_aluno["usuario"] = {
                "is": {"nome": {"contains": termo, "mode": "insensitive"}}
            }

    if turma_id:
        where_aluno["turmas"] = {
            "some": {"turmaId": turma_id, "saiuEm": None},
        }
    elif escola_id:
        where_aluno["turmas"] = {
            "some": {"saiuEm": None, "turma": {"is": {"escolaId": escola_id}}},
        }

    alunos = await db.aluno.find_many(
        where=where_aluno,
        include={
            "usuario": True,
            "turmas": {
                "where": {"saiuEm": None},
                "include": {"turma": {"include": {"escola": True}}},
                "take": 1,
            },
        },
    )

    resultado = []
    for a in alunos:
        vinculo = a.turmas[0] if a.turmas else None
        turma_obj = vinculo.turma if vinculo else None
        resultado.append(
            AlunoListItem(
                id=a.id,
                nome=a.usuario.nome,
                cpf=a.usuario.cpf,
                email=a.usuario.email,
                dataNascimento=a.dataNascimento.date(),
                necessidadeEspecial=a.necessidadeEspecial,
                turmaNome=turma_obj.nome if turma_obj else None,
                escolaNome=turma_obj.escola.nome if turma_obj else None,
            )
        )

    return resultado


@router.get("/{aluno_id}", response_model=AlunoListItem)
async def buscar_aluno(aluno_id: str, _=Depends(get_current_user)):
    aluno = await db.aluno.find_unique(
        where={"id": aluno_id},
        include={
            "usuario": True,
            "turmas": {
                "where": {"saiuEm": None},
                "include": {"turma": {"include": {"escola": True}}},
                "take": 1,
            },
        },
    )
    if not aluno:
        raise HTTPException(status_code=404, detail="Aluno não encontrado")

    vinculo = aluno.turmas[0] if aluno.turmas else None
    turma_obj = vinculo.turma if vinculo else None

    return AlunoListItem(
        id=aluno.id,
        nome=aluno.usuario.nome,
        cpf=aluno.usuario.cpf,
        email=aluno.usuario.email,
        dataNascimento=aluno.dataNascimento.date(),
        necessidadeEspecial=aluno.necessidadeEspecial,
        turmaNome=turma_obj.nome if turma_obj else None,
        escolaNome=turma_obj.escola.nome if turma_obj else None,
    )