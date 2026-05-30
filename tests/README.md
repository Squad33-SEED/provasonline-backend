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

## Cobertura atual (37 testes — todos verdes)

| Arquivo | Foco | Prioridade |
|---------|------|-----------|
| `test_security.py` | Hash de senha (bcrypt), JWT (encode/decode/jti), hash de token | Fundamentos |
| `test_sorteio_questoes.py` | Embaralhamento mantém correção via `letraOriginal` | #3 |
| `test_auth_rbac.py` | Login, token inválido/ausente, RBAC cruzado, revogação no logout | #4 |
| `test_rate_limit.py` | Bloqueio após 5 tentativas em 15min e proteção de credenciais válidas | #5 |
| `test_anti_cola.py` | Gabarito oculto antes da `janelaFim`, liberado depois, admin sempre vê | #2 |

> **Achado durante os testes:** o rate-limit do login é efetivamente **por IP**,
> não por CPF. O `login_rate_key` lê `request.state.login_cpf`, mas esse valor é
> definido dentro do handler — que executa *depois* da checagem do SlowAPI — então
> a chave cai no fallback de IP. Para tornar o limite por CPF de fato, o CPF
> precisaria ser extraído do corpo da requisição dentro da própria `key_func`.

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
