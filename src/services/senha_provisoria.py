from datetime import date


def gerar_senha_provisoria(data_nascimento: date) -> str:
    return data_nascimento.strftime("%d%m%Y")