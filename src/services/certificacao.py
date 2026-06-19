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


async def processar_certificacao(
    simulado,
    resultado_id: str,
    aluno_id: str,
    pontuacao: float,
    momento: datetime,
    notas_por_componente: dict[str, float] | None = None,
):
    if not simulado.geraCertificado or not simulado.nivelEnsinoId:
        return

    nota_minima = simulado.notaMinimaCertificacao if simulado.notaMinimaCertificacao is not None else 6.0

    nivel_id = simulado.nivelEnsinoId
    ano = momento.year

    # Notas por componente: etapas multi-componente novas trazem a nota de CADA
    # componente (questões etiquetadas com componenteId). Etapas antigas, sem
    # essa quebra, creditam o componente principal com a nota global (compat).
    if notas_por_componente:
        creditos = dict(notas_por_componente)
    else:
        creditos = {simulado.componenteId: pontuacao}

    creditou = False
    for componente_id, nota in creditos.items():
        # Cada componente é aprovado independentemente: só credita quem atingiu
        # a nota mínima (certificação acumulativa por componente).
        if nota < nota_minima:
            continue

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
                    "notaObtida": nota,
                },
                "update": {
                    "aprovado": True,
                    "notaObtida": nota,
                    "tentativa": {"connect": {"id": resultado_id}},
                },
            },
        )
        creditou = True

    # Nenhum componente atingiu a nota mínima nesta tentativa: nada a fazer.
    if not creditou:
        return

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

    # Decisão de produto (mentoria): não existe certificado parcial — o sistema
    # só emite o de CONCLUSÃO, quando todos os componentes obrigatórios do nível
    # foram aprovados. Enquanto não completa, nada é emitido (passou ou reprovou).
    if not completo:
        return

    tipo = "CONCLUSAO"

    componentes_aprovados = [
        {"componente": a.componente.nome, "nota": a.notaObtida}
        for a in sorted(aprovados, key=lambda a: a.componente.nome)
    ]

    # Remove eventual parcial legado (emitido antes desta regra) deste aluno/nível/ano.
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
