from fastapi import APIRouter, Depends, HTTPException

from src.database import db
from src.dependencies import require_professor
from src.schemas import (
    ProfessorQuestaoItem,
    ProfessorResultadoEtapa,
    ProfessorTurmaItem,
    ViolacaoEtapaResumo,
    ViolacaoPainelItem,
    ViolacaoPainelResponse,
)

_INCLUDE_VIOLACAO = {
    "resultado": {
        "include": {
            "aluno": {"include": {"usuario": True}},
            "simulado": {"include": {"componente": True}},
        }
    }
}

router = APIRouter(prefix="/professor", tags=["Professor"])


async def _professor_do_usuario(usuario_id: str):
    professor = await db.professor.find_unique(where={"usuarioId": usuario_id})
    if not professor:
        raise HTTPException(status_code=404, detail="Professor não encontrado")
    return professor


@router.get("/turmas", response_model=list[ProfessorTurmaItem])
async def listar_turmas(usuario=Depends(require_professor)):
    professor = await _professor_do_usuario(usuario.id)

    vinculos = await db.professorturma.find_many(
        where={"professorId": professor.id},
        include={"turma": {"include": {"escola": True, "modalidade": True}}},
    )

    resultado: list[ProfessorTurmaItem] = []
    for vinculo in vinculos:
        turma = vinculo.turma
        if not turma:
            continue
        total = await db.turmaaluno.count(
            where={"turmaId": turma.id, "saiuEm": None}
        )
        resultado.append(ProfessorTurmaItem(
            id=turma.id,
            nome=turma.nome,
            anoLetivo=turma.anoLetivo,
            escolaNome=turma.escola.nome,
            modalidadeNome=turma.modalidade.nome,
            totalAlunos=total,
        ))
    return resultado


@router.get("/questoes", response_model=list[ProfessorQuestaoItem])
async def listar_questoes(usuario=Depends(require_professor)):
    professor = await _professor_do_usuario(usuario.id)

    questoes = await db.questao.find_many(
        where={"professorId": professor.id},
        include={"componente": True, "assunto": True},
        order={"criadoEm": "desc"},
    )

    resultado: list[ProfessorQuestaoItem] = []
    for q in questoes:
        alternativas = q.alternativas if isinstance(q.alternativas, list) else []
        resultado.append(ProfessorQuestaoItem(
            id=q.id,
            enunciado=q.enunciado,
            componente=q.componente.nome if q.componente else "—",
            assunto=q.assunto.nome if q.assunto else "—",
            dificuldade=q.dificuldade,
            ativa=q.ativa,
            totalAlternativas=len(alternativas),
        ))
    return resultado


@router.get("/resultados", response_model=list[ProfessorResultadoEtapa])
async def listar_resultados(usuario=Depends(require_professor)):
    professor = await _professor_do_usuario(usuario.id)

    vinculos = await db.professorturma.find_many(
        where={"professorId": professor.id}
    )
    turma_ids = [v.turmaId for v in vinculos]
    if not turma_ids:
        return []

    matriculas = await db.turmaaluno.find_many(
        where={"turmaId": {"in": turma_ids}, "saiuEm": None}
    )
    aluno_ids = list({m.alunoId for m in matriculas})
    if not aluno_ids:
        return []

    aplicacoes = await db.aplicacao.find_many(
        where={"turmaId": {"in": turma_ids}},
        include={"simulado": {"include": {"componente": True}}},
    )

    simulados: dict = {}
    for aplicacao in aplicacoes:
        if aplicacao.simulado and aplicacao.simulado.id not in simulados:
            simulados[aplicacao.simulado.id] = aplicacao.simulado

    resultado: list[ProfessorResultadoEtapa] = []
    for simulado_id, simulado in simulados.items():
        resultados = await db.resultadoaluno.find_many(
            where={
                "simuladoId": simulado_id,
                "alunoId": {"in": aluno_ids},
                "statusResultado": "FINALIZADO",
            },
        )
        finalizados = len(resultados)
        notas = [r.pontuacao for r in resultados if r.pontuacao is not None]
        media = round(sum(notas) / len(notas), 1) if notas else None
        percentual = round(media * 10, 1) if media is not None else None

        resultado.append(ProfessorResultadoEtapa(
            simuladoId=simulado_id,
            etapaTitulo=simulado.titulo,
            componente=simulado.componente.nome if simulado.componente else "—",
            finalizados=finalizados,
            mediaNota=media,
            percentualAcerto=percentual,
        ))

    resultado.sort(key=lambda e: e.finalizados, reverse=True)
    return resultado


@router.get("/violacoes", response_model=ViolacaoPainelResponse)
async def listar_violacoes(usuario=Depends(require_professor)):
    professor = await _professor_do_usuario(usuario.id)

    vinculos = await db.professorturma.find_many(
        where={"professorId": professor.id}
    )
    turma_ids = [v.turmaId for v in vinculos]
    vazio = ViolacaoPainelResponse(total=0, porEtapa=[], ocorrencias=[])
    if not turma_ids:
        return vazio

    matriculas = await db.turmaaluno.find_many(
        where={"turmaId": {"in": turma_ids}, "saiuEm": None}
    )
    aluno_ids = list({m.alunoId for m in matriculas})
    if not aluno_ids:
        return vazio

    violacoes = await db.violacaoprova.find_many(
        where={"resultado": {"is": {"alunoId": {"in": aluno_ids}}}},
        include=_INCLUDE_VIOLACAO,
        order={"criadoEm": "desc"},
    )

    ocorrencias: list[ViolacaoPainelItem] = []
    resumo: dict = {}

    for v in violacoes:
        resultado = v.resultado
        simulado = resultado.simulado if resultado else None
        aluno = resultado.aluno if resultado else None
        usuario_aluno = aluno.usuario if aluno else None

        etapa_titulo = simulado.titulo if simulado else "—"
        componente_nome = simulado.componente.nome if simulado and simulado.componente else "—"

        ocorrencias.append(ViolacaoPainelItem(
            id=v.id,
            resultadoId=v.resultadoId,
            tipo=v.tipo,
            detalhe=v.detalhe,
            criadoEm=v.criadoEm,
            alunoNome=usuario_aluno.nome if usuario_aluno else "—",
            alunoCpf=usuario_aluno.cpf if usuario_aluno else "—",
            etapaTitulo=etapa_titulo,
            componenteNome=componente_nome,
        ))

        if simulado:
            entrada = resumo.setdefault(
                simulado.id,
                {"titulo": etapa_titulo, "total": 0, "alunos": set()},
            )
            entrada["total"] += 1
            if aluno:
                entrada["alunos"].add(aluno.id)

    por_etapa = [
        ViolacaoEtapaResumo(
            simuladoId=sid,
            etapaTitulo=dados["titulo"],
            totalViolacoes=dados["total"],
            alunosEnvolvidos=len(dados["alunos"]),
        )
        for sid, dados in resumo.items()
    ]
    por_etapa.sort(key=lambda e: e.totalViolacoes, reverse=True)

    return ViolacaoPainelResponse(
        total=len(ocorrencias),
        porEtapa=por_etapa,
        ocorrencias=ocorrencias,
    )
