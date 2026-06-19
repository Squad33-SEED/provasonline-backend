from types import SimpleNamespace

from src.routers.aluno import _resultado_por_componente


def _tq(componente_id, marcada, correta):
    return SimpleNamespace(
        componenteId=componente_id,
        alternativaMarcada=marcada,
        alternativasEmbaralhadas=None,
        respostaCorreta=correta,
        ordem=0,
    )


def test_pontuacao_calculada_dentro_de_cada_componente():
    # Componente X: 1 acerto em 2 -> nota 5.0
    # Componente Y: 2 acertos em 2 -> nota 10.0
    tentativas = [
        _tq("X", "A", "A"),
        _tq("X", "B", "A"),
        _tq("Y", "C", "C"),
        _tq("Y", "D", "D"),
    ]

    por_comp = _resultado_por_componente(tentativas)

    assert por_comp["X"] == {"acertos": 1, "total": 2, "nota": 5.0}
    assert por_comp["Y"] == {"acertos": 2, "total": 2, "nota": 10.0}


def test_questoes_sem_componente_sao_ignoradas():
    # Etapas antigas (sem componenteId) não entram na quebra por componente.
    tentativas = [
        _tq(None, "A", "A"),
        _tq("X", "A", "A"),
    ]

    por_comp = _resultado_por_componente(tentativas)

    assert list(por_comp.keys()) == ["X"]
    assert por_comp["X"]["total"] == 1


def test_sem_resposta_conta_como_erro_no_componente():
    # Questão não respondida (marcada=None) conta no total mas não como acerto.
    tentativas = [
        _tq("X", "A", "A"),
        _tq("X", None, "A"),
    ]

    por_comp = _resultado_por_componente(tentativas)

    assert por_comp["X"] == {"acertos": 1, "total": 2, "nota": 5.0}
