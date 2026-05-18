def _calcular_digito(cpf_parcial: str, peso_inicial: int) -> int:
    soma = sum(int(digito) * (peso_inicial - i) for i, digito in enumerate(cpf_parcial))
    resto = (soma * 10) % 11
    return 0 if resto == 10 else resto


def validar_cpf(cpf: str) -> bool:
    if not cpf or len(cpf) != 11 or not cpf.isdigit():
        return False

    if cpf == cpf[0] * 11:
        return False

    digito_1 = _calcular_digito(cpf[:9], 10)
    if digito_1 != int(cpf[9]):
        return False

    digito_2 = _calcular_digito(cpf[:10], 11)
    if digito_2 != int(cpf[10]):
        return False

    return True