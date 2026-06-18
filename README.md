# provasonline-backend — SEED · Squad 33

API do **Sistema de Gestão de Provas Online** da SEED-SE: catálogo curricular, banco de questões,
geração e aplicação de provas com segurança (Modo Seguro), correção automática e **certificação
acumulativa com verificação pública**.

**Stack:** FastAPI · Prisma (`prisma-client-py`) · PostgreSQL · JWT (HS256)

| | |
|---|---|
| Frontend (prod) | https://provasonline-frontend-lksp.vercel.app |
| Backend (prod) | https://provasonline-backend.vercel.app |
| Frontend (repo) | https://github.com/Squad33-SEED/provasonline-frontend |
| Organização | https://github.com/Squad33-SEED |

> **Nota (MVP AI-Powered):** o sistema **não consome um serviço de LLM em tempo de execução** — não
> há chave de API de IA para configurar. A IA (Claude/Claude Code, Gemini, GitHub Copilot) foi o
> **motor de desenvolvimento** do projeto. Ver `prompt.me` (prompt-mestre/spec do sistema).

---

## Requisitos

- Python 3.13+ e `pip`
- PostgreSQL (local ou Prisma Postgres)

## Variáveis de ambiente (`.env`)

```env
DATABASE_URL="postgresql://USUARIO:SENHA@HOST:5432/BANCO?sslmode=require"
SECRET_KEY="uma-chave-secreta-forte"   # assina o JWT e o HMAC dos certificados
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
# Opcionais (têm default no código):
# QUESTIONS_API_BASE_URL="https://questions.zenixcode.cloud"
# CORS_ORIGINS="https://provasonline-frontend-lksp.vercel.app"
```

## Como rodar (local)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

cp .env.example .env              # edite a DATABASE_URL

python -m prisma generate
python -m prisma migrate deploy

# Dados-base: catálogo + contas demo, certificação e vínculo de disciplinas da API
python seed_catalogo.py
python seed_certificacao.py
python seed_subject_slug.py

uvicorn src.main:app --reload --port 3333
```

Servidor em `http://localhost:3333` · Documentação **OpenAPI/Swagger** em `http://localhost:3333/docs`.

> **Prisma + venv:** após mudar `schema.prisma`, o `prisma generate` grava no Python global. É
> preciso **espelhar** a pasta gerada `…/site-packages/prisma/` para dentro do `.venv` para o
> cliente reconhecer os novos campos.

## Testes

```bash
# SEMPRE contra banco LOCAL (os testes criam/alteram dados)
python -m pytest -q
```

## Deploy (Vercel)

Deploy automático a cada push na `main` (entrypoint `api/index.py` + `vercel.json`). Configurar
`DATABASE_URL`, `SECRET_KEY` e (opcional) `CORS_ORIGINS` nas *Environment Variables*. **Aplicar as
migrations em produção antes do merge** (`prisma migrate deploy` apontando para o `DATABASE_URL` de
prod).

## Papéis

| Papel | Acesso |
|---|---|
| `ADMIN` | Catálogo, turmas, alunos, agendamento de provas, IPs autorizados, dashboard |
| `PROFESSOR` | Banco de questões do seu componente, resultados, violações |
| `ALUNO` | Realizar provas (Modo Seguro), simulado livre, histórico, certificados |

## Contas de demonstração (senha `admin123`)

| Papel | CPF (só números) |
|---|---|
| ADMIN | `12345678909` |
| PROFESSOR | `98765432100` |
| ALUNO | `11122233396` |
