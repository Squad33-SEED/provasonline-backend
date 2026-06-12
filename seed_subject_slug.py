import asyncio
import re
import unicodedata

from prisma import Prisma


def slugify(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    sem_acento = normalizado.encode("ascii", "ignore").decode("ascii")
    minusculo = sem_acento.lower().strip()
    return re.sub(r"[^a-z0-9]+", "-", minusculo).strip("-")


async def main():
    db = Prisma()
    await db.connect()

    componentes = await db.componentecurricular.find_many()

    atualizados = 0
    for componente in componentes:
        if componente.questionsSubjectSlug:
            continue
        slug = slugify(componente.nome)
        if not slug:
            continue
        await db.componentecurricular.update(
            where={"id": componente.id},
            data={"questionsSubjectSlug": slug},
        )
        print(f"{componente.nome} -> {slug}")
        atualizados += 1

    print(f"\n{atualizados} componente(s) vinculado(s) a um subject da API Questions.")
    print("Ajuste manualmente os slugs que não baterem com os subjects reais da API.")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
