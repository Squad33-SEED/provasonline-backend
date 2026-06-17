import asyncio

from prisma import Prisma


def _ordem_do_nivel(nome: str) -> int | None:
    nome = nome.lower()
    if "fundamental" in nome:
        return 1
    if "dio" in nome:
        return 2
    return None


async def main():
    db = Prisma()
    await db.connect()

    niveis = await db.nivelensino.find_many(
        include={"modalidades": {"include": {"componentes": True}}}
    )

    criados = 0
    for nivel in niveis:
        ordem = _ordem_do_nivel(nivel.nome)
        if ordem is None:
            continue

        await db.nivelensino.update(where={"id": nivel.id}, data={"ordem": ordem})

        componentes = []
        for modalidade in nivel.modalidades or []:
            if modalidade.supletivo:
                continue
            for componente in modalidade.componentes or []:
                if componente.ativo:
                    componentes.append(componente)

        for componente in componentes:
            existente = await db.nivelcomponente.find_unique(
                where={
                    "nivelId_componenteId": {
                        "nivelId": nivel.id,
                        "componenteId": componente.id,
                    }
                }
            )
            if not existente:
                await db.nivelcomponente.create(
                    data={
                        "nivel": {"connect": {"id": nivel.id}},
                        "componente": {"connect": {"id": componente.id}},
                        "obrigatorio": True,
                    }
                )
                criados += 1

    print(f"NivelComponente: {criados} vinculos novos")
    for nivel in niveis:
        if _ordem_do_nivel(nivel.nome) is None:
            continue
        vinculos = await db.nivelcomponente.find_many(
            where={"nivelId": nivel.id}, include={"componente": True}
        )
        nomes = sorted(v.componente.nome for v in vinculos)
        print(f"  {nivel.nome} (ordem {_ordem_do_nivel(nivel.nome)}): {nomes}")

    await db.disconnect()


asyncio.run(main())
