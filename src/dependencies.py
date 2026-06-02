from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from src.database import db
from src.security import decode_token, hash_token

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = credentials.credentials

    try:
        decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    db_token = await db.tokenacesso.find_unique(where={"tokenHash": hash_token(token)})
    if not db_token:
        raise HTTPException(status_code=401, detail="Token revogado ou inválido")

    if db_token.revogadoEm is not None:
        raise HTTPException(status_code=401, detail="Token revogado")

    if db_token.expiraEm <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expirado")

    usuario = await db.usuario.find_unique(where={"id": db_token.usuarioId})
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo")

    return usuario


async def require_admin(usuario=Depends(get_current_user)):
    if usuario.tipo != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores",
        )
    return usuario


async def require_professor(usuario=Depends(get_current_user)):
    if usuario.tipo != "PROFESSOR":
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a professores",
        )
    return usuario