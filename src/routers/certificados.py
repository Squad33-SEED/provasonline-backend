from fastapi import APIRouter

from src.database import db
from src.schemas import ComponenteAprovadoItem, VerificacaoCertificado
from src.services.certificacao import gerar_assinatura

router = APIRouter(prefix="/certificados", tags=["Certificados"])


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
        nome=certificado.aluno.usuario.nome,
        nivel=certificado.nivel.nome,
        tipo=certificado.tipo,
        anoReferencia=certificado.anoReferencia,
        emitidoEm=certificado.emitidoEm,
        cpf="***.***.***-**",
        componentesAprovados=[
            ComponenteAprovadoItem(componente=item["componente"], nota=item["nota"])
            for item in (certificado.componentesAprovados or [])
        ],
    )
