from fastapi import APIRouter, Depends, HTTPException

from src.database import db
from src.dependencies import get_current_user
from src.schemas import UsuarioCreate, UsuarioResponse, UsuarioUpdate
from src.security import hash_password

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.post("/", response_model=UsuarioResponse, status_code=201)
async def criar_usuario(data: UsuarioCreate):
    if await db.usuario.find_unique(where={"email": data.email}):
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    if await db.usuario.find_unique(where={"cpf": data.cpf}):
        raise HTTPException(status_code=400, detail="CPF já cadastrado")

    return await db.usuario.create(data={
        "nome": data.nome,
        "email": data.email,
        "cpf": data.cpf,
        "senhaHash": hash_password(data.senha),
        "tipo": data.tipo.value,
    })


@router.get("/", response_model=list[UsuarioResponse])
async def listar_usuarios(_=Depends(get_current_user)):
    return await db.usuario.find_many()


@router.get("/{id}", response_model=UsuarioResponse)
async def buscar_usuario(id: str, _=Depends(get_current_user)):
    usuario = await db.usuario.find_unique(where={"id": id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


@router.put("/{id}", response_model=UsuarioResponse)
async def atualizar_usuario(id: str, data: UsuarioUpdate, _=Depends(get_current_user)):
    usuario = await db.usuario.find_unique(where={"id": id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        return usuario

    if "tipo" in update_data:
        tipo = update_data["tipo"]
        update_data["tipo"] = tipo.value if hasattr(tipo, "value") else tipo

    if "senha" in update_data:
        update_data["senhaHash"] = hash_password(update_data.pop("senha"))

    return await db.usuario.update(where={"id": id}, data=update_data)


@router.delete("/{id}", status_code=204)
async def deletar_usuario(id: str, _=Depends(get_current_user)):
    usuario = await db.usuario.find_unique(where={"id": id})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    await db.usuario.delete(where={"id": id})
