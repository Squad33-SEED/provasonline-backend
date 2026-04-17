# Seed Backend

API em FastAPI + Prisma + PostgreSQL para o sistema de provas online da SEED-SE.

## Requisitos

- Python 3.11+
- PostgreSQL rodando localmente

## Como rodar

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edite .env com sua DATABASE_URL

prisma db push
prisma generate

python seed.py
uvicorn main:app --reload --port 3333
```

Servidor em `http://localhost:3333` · Docs em `http://localhost:3333/docs`.

## Contas demo (senha `admin123`)

| Papel | CPF |
|---|---|
| ADMIN | 123.456.789-09 |
| PROFESSOR | 987.654.321-00 |
| ALUNO | 111.222.333-96 |
