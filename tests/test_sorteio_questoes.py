from src.services.sorteio_questoes import embaralhar_alternativas_questao


def _alternativas_padrao():
    return [
        {"letra": "A", "texto": "Resposta A"},
        {"letra": "B", "texto": "Resposta B"},
        {"letra": "C", "texto": "Resposta C"},
        {"letra": "D", "texto": "Resposta D"},
    ]


def test_embaralhar_mantem_quantidade_de_alternativas():
    novas, _ = embaralhar_alternativas_questao(_alternativas_padrao(), "A")
    assert len(novas) == 4


def test_embaralhar_reletra_em_sequencia():
    novas, _ = embaralhar_alternativas_questao(_alternativas_padrao(), "A")
    assert [a["letra"] for a in novas] == ["A", "B", "C", "D"]


def test_embaralhar_preserva_todos_os_textos():
    originais = {a["texto"] for a in _alternativas_padrao()}
    novas, _ = embaralhar_alternativas_questao(_alternativas_padrao(), "A")
    assert {a["texto"] for a in novas} == originais


def test_cada_alternativa_guarda_letra_original_coerente():
    novas, _ = embaralhar_alternativas_questao(_alternativas_padrao(), "B")
    for alt in novas:
        letra_original = alt["letraOriginal"]
        assert alt["texto"] == f"Resposta {letra_original}"


def test_resposta_correta_acompanha_o_texto_original():
    novas, nova_resposta = embaralhar_alternativas_questao(_alternativas_padrao(), "C")
    alt_correta = next(a for a in novas if a["letra"] == nova_resposta)
    assert alt_correta["texto"] == "Resposta C"


def test_resposta_correta_aponta_para_letra_original_correta():
    novas, nova_resposta = embaralhar_alternativas_questao(_alternativas_padrao(), "D")
    alt_correta = next(a for a in novas if a["letra"] == nova_resposta)
    assert alt_correta["letraOriginal"] == "D"


def test_embaralhar_funciona_com_cinco_alternativas():
    cinco = _alternativas_padrao() + [{"letra": "E", "texto": "Resposta E"}]
    novas, nova_resposta = embaralhar_alternativas_questao(cinco, "E")
    assert len(novas) == 5
    assert [a["letra"] for a in novas] == ["A", "B", "C", "D", "E"]
    alt_correta = next(a for a in novas if a["letra"] == nova_resposta)
    assert alt_correta["letraOriginal"] == "E"


def test_embaralhamento_eventualmente_altera_a_ordem():
    alternativas = _alternativas_padrao()
    houve_mudanca = False
    for _ in range(50):
        novas, _ = embaralhar_alternativas_questao(alternativas, "A")
        if [a["texto"] for a in novas] != [a["texto"] for a in alternativas]:
            houve_mudanca = True
            break
    assert houve_mudanca
