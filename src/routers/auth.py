from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.database import db
from src.dependencies import get_current_user
from src.schemas import LoginRequest, TokenResponse, UsuarioResponse
from src.security import create_access_token, hash_token, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])

bearer_scheme = HTTPBearer()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    usuario = await db.usuario.find_unique(where={"cpf": data.cpf})

    if not usuario or not verify_password(data.senha, usuario.senhaHash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")

    token, expires_at = create_access_token({"sub": usuario.id, "role": usuario.tipo})

    await db.tokenacesso.create(data={
        "usuarioId": usuario.id,
        "tipo": "ACCESS",
        "tokenHash": hash_token(token),
        "expiraEm": expires_at,
    })

    return {"access_token": token}


@router.post("/logout", status_code=204)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token_hash = hash_token(credentials.credentials)
    db_token = await db.tokenacesso.find_unique(where={"tokenHash": token_hash})

    if db_token:
        await db.tokenacesso.delete(where={"tokenHash": token_hash})


@router.get("/me", response_model=UsuarioResponse)
async def me(usuario=Depends(get_current_user)):
    return usuario
