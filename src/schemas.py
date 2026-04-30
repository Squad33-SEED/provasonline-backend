from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, field_validator


class TipoUsuario(str, Enum):
    ADMIN = "ADMIN"
    PROFESSOR = "PROFESSOR"
    ALUNO = "ALUNO"


class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr | None = None
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
    email: str | None = None
    cpf: str
    tipo: str
    ativo: bool
    senhaProvisoria: bool
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
    requer_troca_senha: bool = False


class TrocarSenhaRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
    senha_nova: str = Field(min_length=8, max_length=128)

    @field_validator("senha_nova")
    @classmethod
    def validar_senha_forte(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("A nova senha deve conter ao menos uma letra")
        if not any(c.isdigit() for c in v):
            raise ValueError("A nova senha deve conter ao menos um número")
        return v


class TrocarSenhaResponse(BaseModel):
    sucesso: bool = True
    mensagem: str = "Senha alterada com sucesso"