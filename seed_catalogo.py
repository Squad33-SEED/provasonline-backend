import asyncio
from datetime import datetime, date
 
from prisma import Prisma
 
from src.security import hash_password
 
 
CONTAS_DEMO = [
    {
        "nome": "Ricardo Menezes",
        "email": "ricardo.admin@seed.se.gov.br",
        "cpf": "12345678909",
        "tipo": "ADMIN",
    },
    {
        "nome": "Ana Paula Santos",
        "email": "ana.professor@seed.se.gov.br",
        "cpf": "98765432100",
        "tipo": "PROFESSOR",
        "especialidade": "Matemática",
    },
    {
        "nome": "Lucas Silva",
        "email": "lucas.aluno@seed.se.gov.br",
        "cpf": "11122233396",
        "tipo": "ALUNO",
        "dataNascimento": date(2006, 5, 12),
    },
]
 
 
NIVEIS = [
    {"nome": "Ensino Fundamental II", "descricao": "6º ao 9º ano"},
    {"nome": "Ensino Médio", "descricao": "1ª, 2ª e 3ª série"},
]
 
 
MODALIDADES_POR_NIVEL = {
    "Ensino Fundamental II": [
        {"nome": "Regular", "supletivo": False},
        {"nome": "Supletivo", "supletivo": True},
    ],
    "Ensino Médio": [
        {"nome": "Regular", "supletivo": False},
        {"nome": "Supletivo", "supletivo": True},
    ],
}
 
 
COMPONENTES_POR_MODALIDADE = {
    ("Ensino Médio", "Regular"): [
        {"nome": "Matemática", "codigo": "MAT-EM-REG"},
        {"nome": "Língua Portuguesa", "codigo": "POR-EM-REG"},
        {"nome": "Ciências da Natureza", "codigo": "CN-EM-REG"},
        {"nome": "Ciências Humanas", "codigo": "CH-EM-REG"},
    ],
    ("Ensino Médio", "Supletivo"): [
        {"nome": "Matemática", "codigo": "MAT-EM-SUP"},
        {"nome": "Língua Portuguesa", "codigo": "POR-EM-SUP"},
    ],
    ("Ensino Fundamental II", "Regular"): [
        {"nome": "Matemática", "codigo": "MAT-EF-REG"},
        {"nome": "Língua Portuguesa", "codigo": "POR-EF-REG"},
        {"nome": "Ciências", "codigo": "CIE-EF-REG"},
        {"nome": "História e Geografia", "codigo": "HG-EF-REG"},
    ],
    ("Ensino Fundamental II", "Supletivo"): [
        {"nome": "Matemática", "codigo": "MAT-EF-SUP"},
        {"nome": "Língua Portuguesa", "codigo": "POR-EF-SUP"},
    ],
}
 
 
ASSUNTOS_POR_COMPONENTE_NOME = {
    "Matemática": ["Geometria", "Álgebra", "Trigonometria", "Estatística"],
    "Língua Portuguesa": ["Interpretação de Texto", "Gramática", "Literatura"],
    "Ciências da Natureza": ["Biologia", "Física", "Química"],
    "Ciências Humanas": ["História", "Geografia", "Filosofia", "Sociologia"],
    "Ciências": ["Biologia", "Física", "Química"],
    "História e Geografia": ["História", "Geografia"],
}
 
 
ESCOLAS = [
    {
        "nome": "CEAS — Centro Estadual de Atividades Suplementares",
        "municipio": "Aracaju",
        "inep": "28010001",
    },
    {
        "nome": "Colégio Estadual Murilo Braga",
        "municipio": "Itabaiana",
        "inep": "28010002",
    },
    {
        "nome": "CESAJ — Centro de Excelência Atheneu Sergipense",
        "municipio": "Aracaju",
        "inep": "28010003",
    },
]
 
 
async def seed_contas_demo(db: Prisma) -> None:
    print("→ Contas demo (senha: admin123, senhaProvisoria=False)")
    senha_hash = hash_password("admin123")
 
    for conta in CONTAS_DEMO:
        existing = await db.usuario.find_unique(where={"cpf": conta["cpf"]})
 
        dados_base = {
            "nome": conta["nome"],
            "email": conta["email"],
            "tipo": conta["tipo"],
            "senhaHash": senha_hash,
            "senhaProvisoria": False,
            "ativo": True,
        }
 
        if existing:
            usuario = await db.usuario.update(
                where={"id": existing.id},
                data=dados_base,
            )
            usuario_id = usuario.id
        else:
            usuario = await db.usuario.create(
                data={**dados_base, "cpf": conta["cpf"]},
            )
            usuario_id = usuario.id
 
        if conta["tipo"] == "PROFESSOR":
            await db.professor.upsert(
                where={"usuarioId": usuario_id},
                data={
                    "create": {
                        "usuarioId": usuario_id,
                        "especialidade": conta.get("especialidade"),
                    },
                    "update": {"especialidade": conta.get("especialidade")},
                },
            )
 
        if conta["tipo"] == "ALUNO":
            data_nasc = datetime.combine(conta["dataNascimento"], datetime.min.time())
            await db.aluno.upsert(
                where={"usuarioId": usuario_id},
                data={
                    "create": {
                        "usuarioId": usuario_id,
                        "dataNascimento": data_nasc,
                    },
                    "update": {"dataNascimento": data_nasc},
                },
            )
 
        print(f"   [ok] {conta['tipo']:<9} {conta['nome']}")
 
 
async def seed_niveis(db: Prisma) -> dict:
    print("→ Níveis de ensino")
    mapa = {}
    for nivel_data in NIVEIS:
        existing = await db.nivelensino.find_first(where={"nome": nivel_data["nome"]})
        if existing:
            registro = await db.nivelensino.update(
                where={"id": existing.id},
                data={"descricao": nivel_data["descricao"], "ativo": True},
            )
        else:
            registro = await db.nivelensino.create(data=nivel_data)
        mapa[nivel_data["nome"]] = registro.id
        print(f"   [ok] {nivel_data['nome']}")
    return mapa
 
 
async def seed_modalidades(db: Prisma, niveis: dict) -> dict:
    print("→ Modalidades")
    mapa = {}
    for nivel_nome, modalidades in MODALIDADES_POR_NIVEL.items():
        nivel_id = niveis[nivel_nome]
        for mod_data in modalidades:
            existing = await db.modalidade.find_first(
                where={"nivelId": nivel_id, "nome": mod_data["nome"]},
            )
            if existing:
                registro = await db.modalidade.update(
                    where={"id": existing.id},
                    data={"supletivo": mod_data["supletivo"], "ativo": True},
                )
            else:
                registro = await db.modalidade.create(
                    data={**mod_data, "nivelId": nivel_id},
                )
            mapa[(nivel_nome, mod_data["nome"])] = registro.id
            print(f"   [ok] {nivel_nome} → {mod_data['nome']}")
    return mapa
 
 
async def seed_componentes(db: Prisma, modalidades: dict) -> dict:
    print("→ Componentes curriculares")
    mapa = {}
    for chave, componentes in COMPONENTES_POR_MODALIDADE.items():
        modalidade_id = modalidades[chave]
        for comp_data in componentes:
            existing = await db.componentecurricular.find_first(
                where={"codigo": comp_data["codigo"]},
            )
            if existing:
                registro = await db.componentecurricular.update(
                    where={"id": existing.id},
                    data={
                        "nome": comp_data["nome"],
                        "modalidadeId": modalidade_id,
                        "ativo": True,
                    },
                )
            else:
                registro = await db.componentecurricular.create(
                    data={**comp_data, "modalidadeId": modalidade_id},
                )
            mapa[comp_data["codigo"]] = (registro.id, comp_data["nome"])
            print(f"   [ok] {chave[0]} / {chave[1]} → {comp_data['nome']}")
    return mapa
 
 
async def seed_assuntos(db: Prisma, componentes: dict) -> None:
    print("→ Assuntos")
    total = 0
    for codigo, (componente_id, nome_componente) in componentes.items():
        assuntos = ASSUNTOS_POR_COMPONENTE_NOME.get(nome_componente, [])
        for nome_assunto in assuntos:
            existing = await db.assunto.find_first(
                where={"componenteId": componente_id, "nome": nome_assunto},
            )
            if not existing:
                await db.assunto.create(
                    data={"componenteId": componente_id, "nome": nome_assunto},
                )
            total += 1
    print(f"   [ok] {total} assuntos populados")
 
 
async def seed_escolas(db: Prisma) -> None:
    print("→ Escolas reais de Sergipe")
    for escola in ESCOLAS:
        existing = await db.escola.find_unique(where={"inep": escola["inep"]})
        if existing:
            await db.escola.update(
                where={"id": existing.id},
                data={
                    "nome": escola["nome"],
                    "municipio": escola["municipio"],
                    "ativo": True,
                },
            )
        else:
            await db.escola.create(data=escola)
        print(f"   [ok] {escola['nome']} ({escola['municipio']})")
 
 
async def main() -> None:
    db = Prisma()
    await db.connect()
 
    print("\n=== SEED CATÁLOGO — SEED-SE ===\n")
    await seed_contas_demo(db)
    print()
    niveis = await seed_niveis(db)
    print()
    modalidades = await seed_modalidades(db, niveis)
    print()
    componentes = await seed_componentes(db, modalidades)
    print()
    await seed_assuntos(db, componentes)
    print()
    await seed_escolas(db)
    print("\n=== SEED CONCLUÍDO ===\n")
 
    await db.disconnect()
 
 
if __name__ == "__main__":
    asyncio.run(main())