# Testes Automatizados — Backend SEED-SE

Suíte de testes com `pytest` + `pytest-asyncio`, cobrindo as prioridades de
segurança e correção definidas no Passo 5 do projeto.

## Como executar

```powershell
cd provasonline-backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Suíte completa
python -m pytest

# Apenas testes unitários (não precisam de banco)
python -m pytest tests/test_security.py tests/test_sorteio_questoes.py

# Um arquivo específico, modo verboso
python -m pytest tests/test_anti_cola.py -v
```

> Os testes de integração (`test_auth_rbac`, `test_rate_limit`, `test_anti_cola`)
> usam o PostgreSQL configurado em `DATABASE_URL` (`.env`) e as contas demo do
> seed. Rode `seed_catalogo.py` e `seed_questoes_demo.py` antes, caso o banco
> esteja vazio.

## Cobertura atual (35 testes)

| Arquivo | Testes | Foco | Prioridade |
|---------|--------|------|-----------|
| `test_security.py` | 12 | Hash de senha (bcrypt), JWT (encode/decode/jti), hash de token | Fundamentos |
| `test_sorteio_questoes.py` | 8 | Embaralhamento mantém correção via `letraOriginal` | #3 |
| `test_auth_rbac.py` | 9 | Login, token inválido/ausente, RBAC cruzado, revogação no logout | #4 |
| `test_rate_limit.py` | 3 | Bloqueio após 5 tentativas em 15min, isolamento por CPF | #5 |
| `test_anti_cola.py` | 3 | Gabarito oculto antes da `janelaFim`, liberado depois, admin sempre vê | #2 |

## Detalhes de design

- **Isolamento de rate-limit**: fixture autouse `limpar_rate_limit` zera o
  contador do SlowAPI antes/depois de cada teste, evitando 429 cruzado entre
  testes que reutilizam o mesmo CPF.
- **Tokens reutilizados**: as fixtures de login (`token_admin`, `token_aluno`,
  `token_professor`) são `session`-scoped para não consumir o limite de
  tentativas de login durante a suíte.
- **Dados efêmeros**: os testes de anti-cola criam simulado + resultado próprios
  e os removem ao final (fixtures com `yield`), sem poluir o banco.
- **ASGI direto**: o `httpx.AsyncClient` usa `ASGITransport(app=app)`, então a
  suíte roda sem precisar subir o `uvicorn` em paralelo.
