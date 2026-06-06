import hmac
import secrets
from datetime import datetime
from hashlib import sha256

from prisma import Json

from src.database import db
from src.security import settings


def gerar_codigo_verificacao() -> str:
    return secrets.token_urlsafe(32)


def gerar_assinatura(codigo: str, aluno_id: str, nivel_id: str, ano: int, tipo: str) -> str:
    payload = f"{codigo}|{aluno_id}|{nivel_id}|{ano}|{tipo}"
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        sha256,
    ).hexdigest()


async def processar_certificacao(simulado, resultado_id: str, aluno_id: str, pontuacao: float, momento: datetime):
    if not simulado.geraCertificado or not simulado.nivelEnsinoId:
        return

    nota_minima = simulado.notaMinimaCertificacao if simulado.notaMinimaCertificacao is not None else 6.0
    if pontuacao < nota_minima:
        return

    nivel_id = simulado.nivelEnsinoId
    componente_id = simulado.componenteId
    ano = momento.year

    await db.aproveitamentocandidato.upsert(
        where={
            "alunoId_componenteId_nivelId_anoReferencia": {
                "alunoId": aluno_id,
                "componenteId": componente_id,
                "nivelId": nivel_id,
                "anoReferencia": ano,
            }
        },
        data={
            "create": {
                "aluno": {"connect": {"id": aluno_id}},
                "componente": {"connect": {"id": componente_id}},
                "nivel": {"connect": {"id": nivel_id}},
                "tentativa": {"connect": {"id": resultado_id}},
                "anoReferencia": ano,
                "aprovado": True,
                "notaObtida": pontuacao,
            },
            "update": {
                "aprovado": True,
                "notaObtida": pontuacao,
                "tentativa": {"connect": {"id": resultado_id}},
            },
        },
    )

    requeridos = await db.nivelcomponente.find_many(
        where={"nivelId": nivel_id, "obrigatorio": True}
    )
    requeridos_ids = {nc.componenteId for nc in requeridos}

    aprovados = await db.aproveitamentocandidato.find_many(
        where={"alunoId": aluno_id, "nivelId": nivel_id, "anoReferencia": ano, "aprovado": True},
        include={"componente": True},
    )
    aprovados_ids = {a.componenteId for a in aprovados}

    completo = len(requeridos_ids) > 0 and requeridos_ids.issubset(aprovados_ids)
    tipo = "CONCLUSAO" if completo else "PROFICIENCIA_PARCIAL"

    componentes_aprovados = [
        {"componente": a.componente.nome, "nota": a.notaObtida}
        for a in sorted(aprovados, key=lambda a: a.componente.nome)
    ]

    if completo:
        await db.certificado.delete_many(
            where={
                "alunoId": aluno_id,
                "nivelId": nivel_id,
                "anoReferencia": ano,
                "tipo": "PROFICIENCIA_PARCIAL",
            }
        )

    existente = await db.certificado.find_unique(
        where={
            "alunoId_nivelId_anoReferencia_tipo": {
                "alunoId": aluno_id,
                "nivelId": nivel_id,
                "anoReferencia": ano,
                "tipo": tipo,
            }
        }
    )

    if existente:
        await db.certificado.update(
            where={"id": existente.id},
            data={"componentesAprovados": Json(componentes_aprovados)},
        )
        return

    codigo = gerar_codigo_verificacao()
    assinatura = gerar_assinatura(codigo, aluno_id, nivel_id, ano, tipo)

    await db.certificado.create(
        data={
            "aluno": {"connect": {"id": aluno_id}},
            "nivel": {"connect": {"id": nivel_id}},
            "anoReferencia": ano,
            "tipo": tipo,
            "codigoVerificacao": codigo,
            "assinaturaHash": assinatura,
            "componentesAprovados": Json(componentes_aprovados),
        }
    )
