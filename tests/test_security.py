from datetime import datetime, timezone

import pytest
from jose import jwt

from src.security import (
    create_access_token,
    decode_token,
    hash_password,
    hash_token,
    settings,
    verify_password,
)


def test_hash_password_gera_hash_diferente_da_senha():
    senha = "admin123"
    hashed = hash_password(senha)
    assert hashed != senha
    assert hashed.startswith("$2")


def test_hash_password_salt_torna_hashes_distintos():
    senha = "admin123"
    assert hash_password(senha) != hash_password(senha)


def test_verify_password_aceita_senha_correta():
    hashed = hash_password("admin123")
    assert verify_password("admin123", hashed) is True


def test_verify_password_rejeita_senha_errada():
    hashed = hash_password("admin123")
    assert verify_password("senhaErrada", hashed) is False


def test_hash_token_e_deterministico():
    token = "qualquer.jwt.aqui"
    assert hash_token(token) == hash_token(token)


def test_hash_token_muda_com_entrada_diferente():
    assert hash_token("token-a") != hash_token("token-b")


def test_hash_token_tem_64_caracteres_hex():
    resultado = hash_token("abc")
    assert len(resultado) == 64
    int(resultado, 16)


def test_create_access_token_retorna_token_e_expiracao():
    token, expira_em = create_access_token({"sub": "user-123", "role": "ALUNO"})
    assert isinstance(token, str)
    assert isinstance(expira_em, datetime)
    assert expira_em > datetime.now(timezone.utc)


def test_create_access_token_inclui_claims_e_jti():
    token, _ = create_access_token({"sub": "user-123", "role": "ADMIN"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "user-123"
    assert payload["role"] == "ADMIN"
    assert "jti" in payload
    assert "exp" in payload


def test_create_access_token_gera_jti_unico():
    token_a, _ = create_access_token({"sub": "x"})
    token_b, _ = create_access_token({"sub": "x"})
    jti_a = jwt.decode(token_a, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["jti"]
    jti_b = jwt.decode(token_b, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["jti"]
    assert jti_a != jti_b


def test_decode_token_recupera_payload():
    token, _ = create_access_token({"sub": "user-xyz", "role": "PROFESSOR"})
    payload = decode_token(token)
    assert payload["sub"] == "user-xyz"
    assert payload["role"] == "PROFESSOR"


def test_decode_token_rejeita_token_invalido():
    from jose import JWTError

    with pytest.raises(JWTError):
        decode_token("token.invalido.aqui")


def test_decode_token_rejeita_assinatura_adulterada():
    from jose import JWTError

    token, _ = create_access_token({"sub": "user"})
    adulterado = token[:-4] + "AAAA"
    with pytest.raises(JWTError):
        decode_token(adulterado)
