from datetime import date, datetime, timezone
import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from prisma import Json

from src.database import db
from src.dependencies import get_current_user, require_admin
from src.schemas import (
    AlunoCreate,
    AlunoCreateResponse,
    AlunoListItem,
    ImportacaoCreateResponse,
    ImportacaoStatusResponse,
    ProcessarLoteResponse,
)
from src.security import hash_password
from src.services.cpf_validator import validar_cpf
from src.services.senha_provisoria import gerar_senha_provisoria

router = APIRouter(prefix="/alunos", tags=["Alunos"])

TAMANHO_LOTE = 50


@router.post("", response_model=AlunoCreateResponse, status_code=201)
async def criar_aluno(data: AlunoCreate, admin=Depends(require_admin)):
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

    prereq_extra = {}
    if data.prereqValidado:
        prereq_extra = {
            "prereqValidadoPorId": admin.id,
            "prereqValidadoEm": datetime.now(timezone.utc),
        }

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
                "tipoCandidato": data.tipoCandidato,
                "prereqValidado": data.prereqValidado,
                "prereqDocumento": data.prereqDocumento,
                **prereq_extra,
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


@router.post("/importar", response_model=ImportacaoCreateResponse, status_code=201)
async def importar_alunos_csv(
    arquivo: UploadFile = File(...),
    _=Depends(require_admin),
):
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo não enviado")

    if not arquivo.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv")

    conteudo = await arquivo.read()

    try:
        texto = conteudo.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Arquivo CSV inválido")

    leitor = csv.DictReader(io.StringIO(texto))

    linhas = []
    for numero_linha, linha in enumerate(leitor, start=2):
        linhas.append({
            "numero": numero_linha,
            "nome": (linha.get("nome") or "").strip(),
            "email": (linha.get("email") or "").strip() or None,
            "cpf": (linha.get("cpf") or "").strip(),
            "dataNascimento": (linha.get("data_nascimento") or "").strip(),
            "turmaId": (linha.get("turma_id") or "").strip() or None,
        })

    if not linhas:
        raise HTTPException(status_code=400, detail="CSV vazio ou sem linhas de dados")

    importacao = await db.importacaoalunos.create(
        data={
            "arquivoNome": arquivo.filename,
            "status": "PENDENTE",
            "totalLinhas": len(linhas),
            "linhas": Json(linhas),
            "erros": Json([]),
        }
    )

    return ImportacaoCreateResponse(
        id=importacao.id,
        status=importacao.status,
        totalLinhas=importacao.totalLinhas,
    )


async def _processar_linha(linha: dict) -> tuple[bool, str | None]:
    numero = linha.get("numero")
    nome = linha.get("nome")
    email = linha.get("email")
    cpf = linha.get("cpf")
    data_nascimento = linha.get("dataNascimento")
    turma_id = linha.get("turmaId")

    if not nome or not cpf or not data_nascimento:
        return False, f"Linha {numero}: nome, CPF ou data de nascimento ausente"

    if not validar_cpf(cpf):
        return False, f"Linha {numero}: CPF inválido ({cpf})"

    cpf_existente = await db.usuario.find_unique(where={"cpf": cpf})
    if cpf_existente:
        return False, f"Linha {numero}: CPF já cadastrado ({cpf})"

    try:
        data_nascimento_date = datetime.strptime(data_nascimento, "%Y-%m-%d").date()
    except ValueError:
        return False, f"Linha {numero}: data inválida ({data_nascimento})"

    senha_hash = hash_password(gerar_senha_provisoria(data_nascimento_date))
    data_nascimento_dt = datetime.combine(data_nascimento_date, datetime.min.time())

    async with db.tx() as transaction:
        novo_usuario = await transaction.usuario.create(
            data={
                "nome": nome,
                "email": email,
                "cpf": cpf,
                "senhaHash": senha_hash,
                "senhaProvisoria": True,
                "tipo": "ALUNO",
                "ativo": True,
            }
        )

        novo_aluno = await transaction.aluno.create(
            data={
                "usuarioId": novo_usuario.id,
                "dataNascimento": data_nascimento_dt,
                "necessidadeEspecial": False,
            }
        )

        if turma_id:
            await transaction.turmaaluno.create(
                data={
                    "turmaId": turma_id,
                    "alunoId": novo_aluno.id,
                    "entrouEm": datetime.combine(date.today(), datetime.min.time()),
                }
            )

    return True, None


@router.post("/importar/{importacao_id}/processar", response_model=ProcessarLoteResponse)
async def processar_lote_importacao(importacao_id: str, _=Depends(require_admin)):
    importacao = await db.importacaoalunos.find_unique(where={"id": importacao_id})
    if not importacao:
        raise HTTPException(status_code=404, detail="Importação não encontrada")

    if importacao.status == "CONCLUIDA":
        return ProcessarLoteResponse(
            id=importacao.id,
            status=importacao.status,
            processadas=importacao.processadas,
            totalLinhas=importacao.totalLinhas,
            importados=importacao.importados,
            ignorados=importacao.ignorados,
            concluida=True,
        )

    linhas = importacao.linhas if isinstance(importacao.linhas, list) else []
    erros = list(importacao.erros) if isinstance(importacao.erros, list) else []

    inicio = importacao.processadas
    fim = min(inicio + TAMANHO_LOTE, importacao.totalLinhas)
    lote = linhas[inicio:fim]

    importados = importacao.importados
    ignorados = importacao.ignorados

    for linha in lote:
        ok, erro = await _processar_linha(linha)
        if ok:
            importados += 1
        else:
            ignorados += 1
            if erro:
                erros.append(erro)

    concluida = fim >= importacao.totalLinhas
    novo_status = "CONCLUIDA" if concluida else "PROCESSANDO"

    atualizada = await db.importacaoalunos.update(
        where={"id": importacao_id},
        data={
            "status": novo_status,
            "processadas": fim,
            "importados": importados,
            "ignorados": ignorados,
            "erros": Json(erros),
        },
    )

    return ProcessarLoteResponse(
        id=atualizada.id,
        status=atualizada.status,
        processadas=atualizada.processadas,
        totalLinhas=atualizada.totalLinhas,
        importados=atualizada.importados,
        ignorados=atualizada.ignorados,
        concluida=concluida,
    )


@router.get("/importar/{importacao_id}", response_model=ImportacaoStatusResponse)
async def status_importacao(importacao_id: str, _=Depends(require_admin)):
    importacao = await db.importacaoalunos.find_unique(where={"id": importacao_id})
    if not importacao:
        raise HTTPException(status_code=404, detail="Importação não encontrada")

    erros = list(importacao.erros) if isinstance(importacao.erros, list) else []

    return ImportacaoStatusResponse(
        id=importacao.id,
        arquivoNome=importacao.arquivoNome,
        status=importacao.status,
        totalLinhas=importacao.totalLinhas,
        processadas=importacao.processadas,
        importados=importacao.importados,
        ignorados=importacao.ignorados,
        erros=erros,
        concluida=importacao.status == "CONCLUIDA",
    )