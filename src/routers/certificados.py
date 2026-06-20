from fastapi import APIRouter

from src.database import db
from src.schemas import ComponenteAprovadoItem, VerificacaoCertificado
from src.services.certificacao import gerar_assinatura

router = APIRouter(prefix="/certificados", tags=["Certificados"])


def _mascarar_cpf(cpf: str | None) -> str:
    """Máscara parcial (LGPD): esconde os 3 primeiros e os 2 últimos dígitos,
    mantendo os 6 do meio visíveis. Ex.: 11122233396 -> ***.222.333-**."""
    digitos = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(digitos) != 11:
        return "***.***.***-**"
    return f"***.{digitos[3:6]}.{digitos[6:9]}-**"


def _mascarar_nome(nome: str | None) -> str:
    """Mantém apenas a 1ª letra de cada nome; o resto vira asteriscos.
    Ex.: 'Maria Clara de Oliva' -> 'M**** C**** d* O****'."""
    partes = (nome or "").split()
    return " ".join(p[0] + "*" * (len(p) - 1) for p in partes)


@router.get("/verificar/{codigo}", response_model=VerificacaoCertificado)
async def verificar_certificado(codigo: str):
    certificado = await db.certificado.find_unique(
        where={"codigoVerificacao": codigo},
        include={"nivel": True, "aluno": {"include": {"usuario": True}}},
    )
    if not certificado:
        return VerificacaoCertificado(status="NAO_ENCONTRADO")

    assinatura_esperada = gerar_assinatura(
        certificado.codigoVerificacao,
        certificado.alunoId,
        certificado.nivelId,
        certificado.anoReferencia,
        certificado.tipo,
    )
    if assinatura_esperada != certificado.assinaturaHash:
        return VerificacaoCertificado(status="INVALIDO")

    return VerificacaoCertificado(
        status="VALIDO",
        nome=_mascarar_nome(certificado.aluno.usuario.nome),
        nivel=certificado.nivel.nome,
        tipo=certificado.tipo,
        anoReferencia=certificado.anoReferencia,
        emitidoEm=certificado.emitidoEm,
        cpf=_mascarar_cpf(certificado.aluno.usuario.cpf),
        componentesAprovados=[
            ComponenteAprovadoItem(componente=item["componente"], nota=item["nota"])
            for item in (certificado.componentesAprovados or [])
        ],
    )
