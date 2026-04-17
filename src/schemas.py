from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class TipoUsuario(str, Enum):
    ADMIN = "ADMIN"
    PROFESSOR = "PROFESSOR"
    ALUNO = "ALUNO"


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    cpf: str = Field(pattern=r"^\d{11}$")
    senha: str
    tipo: TipoUsuario = TipoUsuario.ALUNO


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    email: EmailStr | None = None
    cpf: str | None = Field(default=None, pattern=r"^\d{11}$")
    senha: str | None = None
    tipo: TipoUsuario | None = None
    ativo: bool | None = None


class UsuarioResponse(BaseModel):
    id: str
    nome: str
    email: str
    cpf: str
    tipo: str
    ativo: bool
    criadoEm: datetime
    atualizadoEm: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    cpf: str = Field(pattern=r"^\d{11}$")
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
