import asyncio
from datetime import datetime

from prisma import Prisma

from src.security import hash_password


USERS = [
    {
        "nome": "Administrador Demo",
        "email": "admin@seed.se.gov.br",
        "cpf": "12345678909",
        "tipo": "ADMIN",
    },
    {
        "nome": "Ana Paula Santos",
        "email": "professor@seed.se.gov.br",
        "cpf": "98765432100",
        "tipo": "PROFESSOR",
        "especialidade": "Matemática",
    },
    {
        "nome": "Lucas Silva",
        "email": "aluno@seed.se.gov.br",
        "cpf": "11122233396",
        "tipo": "ALUNO",
        "dataNascimento": datetime(2006, 5, 12),
    },
]


async def main() -> None:
    db = Prisma()
    await db.connect()

    senha_hash = hash_password("admin123")

    for user in USERS:
        existing = await db.usuario.find_unique(where={"cpf": user["cpf"]})

        if existing:
            await db.usuario.update(
                where={"id": existing.id},
                data={
                    "nome": user["nome"],
                    "email": user["email"],
                    "tipo": user["tipo"],
                    "senhaHash": senha_hash,
                    "ativo": True,
                },
            )
            usuario_id = existing.id
        else:
            created = await db.usuario.create(
                data={
                    "nome": user["nome"],
                    "email": user["email"],
                    "cpf": user["cpf"],
                    "senhaHash": senha_hash,
                    "tipo": user["tipo"],
                }
            )
            usuario_id = created.id

        if user["tipo"] == "PROFESSOR":
            await db.professor.upsert(
                where={"usuarioId": usuario_id},
                data={
                    "create": {
                        "usuarioId": usuario_id,
                        "especialidade": user.get("especialidade"),
                    },
                    "update": {
                        "especialidade": user.get("especialidade"),
                    },
                },
            )

        if user["tipo"] == "ALUNO":
            await db.aluno.upsert(
                where={"usuarioId": usuario_id},
                data={
                    "create": {
                        "usuarioId": usuario_id,
                        "dataNascimento": user["dataNascimento"],
                    },
                    "update": {
                        "dataNascimento": user["dataNascimento"],
                    },
                },
            )

        print(f"[ok] {user['tipo']:<9} {user['nome']} — cpf {user['cpf']}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
