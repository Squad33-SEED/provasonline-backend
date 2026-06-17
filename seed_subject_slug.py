import asyncio
import re
import unicodedata

from prisma import Prisma

# Slugs validos na API de questoes (fonte: GET https://questions.zenixcode.cloud/subjects).
SLUGS_VALIDOS = {
    "biologia",
    "fisica",
    "geografia",
    "historia",
    "ingles",
    "matematica",
    "portugues",
    "quimica",
}

# Mapa explicito: nome do componente (normalizado) -> slug da materia na API.
#
# A API de questoes e organizada por DISCIPLINA (8 materias), enquanto o
# catalogo da SEED tem componentes por AREA do ENEM. Como questionsSubjectSlug
# e um slug unico por componente, cada componente-area aponta para a disciplina
# mais representativa (mapa pragmatico). Para cobrir uma area inteira, crie uma
# etapa multi-componente selecionando as disciplinas correspondentes.
MAPA = {
    "matematica": "matematica",
    "lingua portuguesa": "portugues",
    "portugues": "portugues",
    "lingua inglesa": "ingles",
    "ingles": "ingles",
    "ciencias da natureza": "biologia",
    "ciencias humanas": "historia",
    "historia e geografia": "historia",
    "historia": "historia",
    "geografia": "geografia",
    "biologia": "biologia",
    "fisica": "fisica",
    "quimica": "quimica",
    "ciencias": "biologia",
}


def normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    sem_acento = base.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.lower().strip())


async def main():
    db = Prisma()
    await db.connect()

    componentes = await db.componentecurricular.find_many()

    atualizados = 0
    sem_mapa: list[str] = []
    for componente in componentes:
        slug = MAPA.get(normalizar(componente.nome))
        if not slug:
            sem_mapa.append(componente.nome)
            print(f"[IGNORADO] {componente.nome}: sem mapeamento definido")
            continue
        if slug not in SLUGS_VALIDOS:
            print(f"[ALERTA] {componente.nome} -> {slug} (slug nao existe na API!)")
        await db.componentecurricular.update(
            where={"id": componente.id},
            data={"questionsSubjectSlug": slug},
        )
        print(f"[OK] {componente.nome} -> {slug}")
        atualizados += 1

    print(f"\n{atualizados} componente(s) vinculado(s) a uma materia da API Questions.")
    if sem_mapa:
        print("\nSem mapeamento (adicione ao MAPA e rode de novo):")
        for nome in sorted(set(sem_mapa)):
            print(f"  - {nome}")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
