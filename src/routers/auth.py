from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.database import db
from src.dependencies import get_current_user
from src.schemas import (
    LoginRequest,
    TokenResponse,
    TrocarSenhaRequest,
    TrocarSenhaResponse,
    UsuarioResponse,
)
from src.security import create_access_token, hash_password, hash_token, verify_password


def login_rate_key(request: Request) -> str:
    ip = get_remote_address(request)
    cpf = ""
    try:
        body = getattr(request.state, "login_cpf", None)
        if body:
            cpf = body
    except Exception:
        cpf = ""
    return f"{cpf}:{ip}" if cpf else ip


limiter = Limiter(key_func=login_rate_key)

router = APIRouter(prefix="/auth", tags=["Auth"])

bearer_scheme = HTTPBearer()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15 minutes")
async def login(request: Request, data: LoginRequest):
    request.state.login_cpf = data.cpf

    usuario = await db.usuario.find_unique(where={"cpf": data.cpf})

    ip_origem = get_remote_address(request)
    user_agent = request.headers.get("user-agent", "")[:500]

    if not usuario or not verify_password(data.senha, usuario.senhaHash):
        await db.logacesso.create(
            data={
                "usuarioId": usuario.id if usuario else None,
                "cpfTentado": data.cpf,
                "ipOrigem": ip_origem,
                "dispositivo": user_agent,
                "resultado": "FALHA",
            },
        )
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    if not usuario.ativo:
        await db.logacesso.create(
            data={
                "usuarioId": usuario.id,
                "cpfTentado": data.cpf,
                "ipOrigem": ip_origem,
                "dispositivo": user_agent,
                "resultado": "FALHA",
            },
        )
        raise HTTPException(status_code=403, detail="Usuário inativo")

    token, expires_at = create_access_token({"sub": usuario.id, "role": usuario.tipo})

    await db.tokenacesso.create(
        data={
            "usuarioId": usuario.id,
            "tipo": "ACCESS",
            "tokenHash": hash_token(token),
            "expiraEm": expires_at,
        },
    )

    await db.logacesso.create(
        data={
            "usuarioId": usuario.id,
            "cpfTentado": data.cpf,
            "ipOrigem": ip_origem,
            "dispositivo": user_agent,
            "resultado": "SUCESSO",
        },
    )

    return TokenResponse(
        access_token=token,
        requer_troca_senha=usuario.senhaProvisoria,
    )


@router.post("/trocar-senha", response_model=TrocarSenhaResponse)
async def trocar_senha(
    data: TrocarSenhaRequest,
    usuario=Depends(get_current_user),
):
    if not verify_password(data.senha_atual, usuario.senhaHash):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")

    if data.senha_atual == data.senha_nova:
        raise HTTPException(
            status_code=422,
            detail="A nova senha deve ser diferente da senha atual",
        )

    novo_hash = hash_password(data.senha_nova)

    await db.usuario.update(
        where={"id": usuario.id},
        data={"senhaHash": novo_hash, "senhaProvisoria": False},
    )

    agora = datetime.now(timezone.utc)
    await db.tokenacesso.update_many(
        where={"usuarioId": usuario.id, "revogadoEm": None},
        data={"revogadoEm": agora},
    )

    return TrocarSenhaResponse()


@router.post("/logout", status_code=204)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token_hash = hash_token(credentials.credentials)
    db_token = await db.tokenacesso.find_unique(where={"tokenHash": token_hash})

    if db_token:
        await db.tokenacesso.delete(where={"tokenHash": token_hash})


@router.get("/me", response_model=UsuarioResponse)
async def me(usuario=Depends(get_current_user)):
    return usuario