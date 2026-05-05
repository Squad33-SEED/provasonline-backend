import asyncio
import sys

from prisma import Prisma
from prisma.errors import PrismaError


QUESTOES_DEMO = [
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Resolva a equação: 2x + 5 = 13. Qual é o valor de x?",
        "alternativas": [
            ("A", "x = 3"),
            ("B", "x = 4"),
            ("C", "x = 5"),
            ("D", "x = 9"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Calcule 15% de 200.",
        "alternativas": [
            ("A", "20"),
            ("B", "25"),
            ("C", "30"),
            ("D", "35"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Uma loja tem 120 camisetas e vendeu 1/4 delas. Quantas camisetas restam?",
        "alternativas": [
            ("A", "30"),
            ("B", "60"),
            ("C", "80"),
            ("D", "90"),
        ],
        "respostaCorreta": "D",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Qual é o resultado de 8² ÷ 4?",
        "alternativas": [
            ("A", "8"),
            ("B", "16"),
            ("C", "24"),
            ("D", "32"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "A área de um quadrado de lado 7 cm é igual a:",
        "alternativas": [
            ("A", "14 cm²"),
            ("B", "28 cm²"),
            ("C", "49 cm²"),
            ("D", "56 cm²"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Resolva o sistema: { x + y = 10; 2x - y = 5 }. Determine x e y.",
        "alternativas": [
            ("A", "x = 4, y = 6"),
            ("B", "x = 5, y = 5"),
            ("C", "x = 6, y = 4"),
            ("D", "x = 7, y = 3"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Uma progressão aritmética tem primeiro termo 4 e razão 3. Qual é o décimo termo?",
        "alternativas": [
            ("A", "27"),
            ("B", "30"),
            ("C", "31"),
            ("D", "34"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Calcule log₁₀(1000).",
        "alternativas": [
            ("A", "1"),
            ("B", "2"),
            ("C", "3"),
            ("D", "10"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Uma esfera tem raio 3 cm. Qual é o seu volume aproximado? (use π ≈ 3,14)",
        "alternativas": [
            ("A", "84,78 cm³"),
            ("B", "100,48 cm³"),
            ("C", "113,04 cm³"),
            ("D", "150,72 cm³"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Quantos números pares de 3 algarismos distintos podem ser formados com os dígitos 1, 2, 3, 4 e 5?",
        "alternativas": [
            ("A", "20"),
            ("B", "24"),
            ("C", "30"),
            ("D", "60"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Determine as raízes da equação x² - 8x + 12 = 0.",
        "alternativas": [
            ("A", "x = 1 e x = 12"),
            ("B", "x = 2 e x = 6"),
            ("C", "x = 3 e x = 4"),
            ("D", "x = -2 e x = -6"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "O limite quando x tende a 2 da função f(x) = (x² - 4)/(x - 2) é:",
        "alternativas": [
            ("A", "0"),
            ("B", "2"),
            ("C", "4"),
            ("D", "indefinido"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Matemática",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Em um triângulo retângulo, os catetos medem 6 cm e 8 cm. Qual é a hipotenusa?",
        "alternativas": [
            ("A", "10 cm"),
            ("B", "12 cm"),
            ("C", "14 cm"),
            ("D", "√50 cm"),
        ],
        "respostaCorreta": "A",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Qual das frases abaixo está corretamente acentuada?",
        "alternativas": [
            ("A", "O voo do pássaro é veloz."),
            ("B", "O vôo do passaro é veloz."),
            ("C", "O voo do passáro é veloz."),
            ("D", "O vôo do pássaro é veloz."),
        ],
        "respostaCorreta": "A",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Indique a palavra escrita corretamente:",
        "alternativas": [
            ("A", "exceção"),
            ("B", "excessão"),
            ("C", "esceção"),
            ("D", "excecao"),
        ],
        "respostaCorreta": "A",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Em 'Maria comprou flores para a vovó', o sujeito da oração é:",
        "alternativas": [
            ("A", "flores"),
            ("B", "Maria"),
            ("C", "para a vovó"),
            ("D", "comprou"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Identifique o substantivo coletivo correspondente a 'conjunto de cães':",
        "alternativas": [
            ("A", "cardume"),
            ("B", "matilha"),
            ("C", "rebanho"),
            ("D", "manada"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Qual figura de linguagem está presente em 'Seus olhos são duas estrelas'?",
        "alternativas": [
            ("A", "metáfora"),
            ("B", "antítese"),
            ("C", "ironia"),
            ("D", "hipérbole"),
        ],
        "respostaCorreta": "A",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Em qual das alternativas a vírgula está usada corretamente?",
        "alternativas": [
            ("A", "Pedro, comprou um livro novo."),
            ("B", "Pedro comprou, um livro novo."),
            ("C", "Pedro, meu irmão, comprou um livro novo."),
            ("D", "Pedro comprou um livro, novo."),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Em 'Os alunos estudaram para a prova', identifique o tempo verbal:",
        "alternativas": [
            ("A", "presente do indicativo"),
            ("B", "pretérito perfeito do indicativo"),
            ("C", "pretérito imperfeito do subjuntivo"),
            ("D", "futuro do presente"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Qual escola literária brasileira tem como característica principal o sentimento, o subjetivismo e o nacionalismo?",
        "alternativas": [
            ("A", "Realismo"),
            ("B", "Romantismo"),
            ("C", "Modernismo"),
            ("D", "Parnasianismo"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Em 'Espero que ele venha amanhã', o modo verbal de 'venha' é:",
        "alternativas": [
            ("A", "indicativo"),
            ("B", "subjuntivo"),
            ("C", "imperativo"),
            ("D", "infinitivo"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Em 'Embora estivesse cansado, terminou o trabalho', a oração subordinada expressa ideia de:",
        "alternativas": [
            ("A", "causa"),
            ("B", "concessão"),
            ("C", "consequência"),
            ("D", "finalidade"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Identifique a regência verbal correta:",
        "alternativas": [
            ("A", "Aspiro o cargo de gerente."),
            ("B", "Aspiro ao cargo de gerente."),
            ("C", "Aspiro pelo cargo de gerente."),
            ("D", "Aspiro do cargo de gerente."),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Língua Portuguesa",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Em 'Fazem dez anos que ela mudou', o verbo 'fazem' está:",
        "alternativas": [
            ("A", "correto, concorda com 'anos'"),
            ("B", "incorreto, deveria ser 'faz' (verbo impessoal)"),
            ("C", "correto em qualquer contexto"),
            ("D", "incorreto, deveria ser 'fizeram'"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Qual é o gás mais abundante na atmosfera terrestre?",
        "alternativas": [
            ("A", "oxigênio"),
            ("B", "nitrogênio"),
            ("C", "gás carbônico"),
            ("D", "hidrogênio"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "A fotossíntese é o processo pelo qual as plantas:",
        "alternativas": [
            ("A", "absorvem oxigênio e liberam gás carbônico"),
            ("B", "produzem alimento usando luz solar, água e gás carbônico"),
            ("C", "transformam gordura em proteína"),
            ("D", "expelem água pelas folhas"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Qual é a unidade de medida da força no Sistema Internacional?",
        "alternativas": [
            ("A", "joule"),
            ("B", "watt"),
            ("C", "newton"),
            ("D", "pascal"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "A célula que possui núcleo verdadeiro é chamada de:",
        "alternativas": [
            ("A", "procarionte"),
            ("B", "eucarionte"),
            ("C", "vegetal apenas"),
            ("D", "animal apenas"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Um carro percorre 180 km em 2 horas. Qual sua velocidade média em km/h?",
        "alternativas": [
            ("A", "60 km/h"),
            ("B", "75 km/h"),
            ("C", "90 km/h"),
            ("D", "120 km/h"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "Qual é a fórmula química da água?",
        "alternativas": [
            ("A", "CO₂"),
            ("B", "H₂O"),
            ("C", "O₂"),
            ("D", "NaCl"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "O processo de divisão celular que origina células sexuais é chamado de:",
        "alternativas": [
            ("A", "mitose"),
            ("B", "meiose"),
            ("C", "fissão binária"),
            ("D", "brotamento"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "A Primeira Lei de Newton trata:",
        "alternativas": [
            ("A", "do princípio da inércia"),
            ("B", "da relação entre força e aceleração"),
            ("C", "da ação e reação"),
            ("D", "da gravitação universal"),
        ],
        "respostaCorreta": "A",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Em uma reação química, a soma das massas dos reagentes é igual à soma das massas dos produtos. Esse é o enunciado da Lei de:",
        "alternativas": [
            ("A", "Proust (proporções definidas)"),
            ("B", "Lavoisier (conservação das massas)"),
            ("C", "Dalton (proporções múltiplas)"),
            ("D", "Avogadro (volumes iguais)"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências da Natureza",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "A energia potencial gravitacional de um corpo de massa 5 kg a 10 m de altura é (g = 10 m/s²):",
        "alternativas": [
            ("A", "50 J"),
            ("B", "150 J"),
            ("C", "500 J"),
            ("D", "5000 J"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Em que ano o Brasil declarou independência de Portugal?",
        "alternativas": [
            ("A", "1500"),
            ("B", "1808"),
            ("C", "1822"),
            ("D", "1889"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "Qual é a capital de Sergipe?",
        "alternativas": [
            ("A", "Maceió"),
            ("B", "Aracaju"),
            ("C", "Salvador"),
            ("D", "Recife"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "O continente com a maior população do mundo é:",
        "alternativas": [
            ("A", "Europa"),
            ("B", "África"),
            ("C", "Ásia"),
            ("D", "América"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "FACIL",
        "enunciado": "A Proclamação da República no Brasil ocorreu em:",
        "alternativas": [
            ("A", "1822"),
            ("B", "1888"),
            ("C", "1889"),
            ("D", "1930"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "A Revolução Industrial teve início no século XVIII em qual país?",
        "alternativas": [
            ("A", "França"),
            ("B", "Inglaterra"),
            ("C", "Alemanha"),
            ("D", "Estados Unidos"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "O bioma predominante na região Norte do Brasil é:",
        "alternativas": [
            ("A", "Cerrado"),
            ("B", "Caatinga"),
            ("C", "Amazônia"),
            ("D", "Mata Atlântica"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "A Era Vargas no Brasil compreende o período de:",
        "alternativas": [
            ("A", "1889 a 1930"),
            ("B", "1930 a 1945"),
            ("C", "1945 a 1964"),
            ("D", "1964 a 1985"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "MEDIO",
        "enunciado": "O sistema econômico baseado na propriedade privada e na livre concorrência é o:",
        "alternativas": [
            ("A", "feudalismo"),
            ("B", "socialismo"),
            ("C", "capitalismo"),
            ("D", "comunismo"),
        ],
        "respostaCorreta": "C",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "Marque a alternativa que corresponde à Conferência que dividiu a África entre potências europeias no século XIX:",
        "alternativas": [
            ("A", "Conferência de Yalta"),
            ("B", "Conferência de Berlim"),
            ("C", "Conferência de Versalhes"),
            ("D", "Conferência de Bandung"),
        ],
        "respostaCorreta": "B",
    },
    {
        "componente": "Ciências Humanas",
        "modalidade": "Regular",
        "nivel": "Ensino Médio",
        "dificuldade": "DIFICIL",
        "enunciado": "O movimento iluminista do século XVIII tinha como princípio fundamental:",
        "alternativas": [
            ("A", "o absolutismo monárquico"),
            ("B", "o uso da razão como guia para o conhecimento"),
            ("C", "o retorno aos valores medievais"),
            ("D", "a centralização religiosa"),
        ],
        "respostaCorreta": "B",
    },
]


async def buscar_componente(db: Prisma, nome_componente: str, nome_modalidade: str, nome_nivel: str):
    componentes = await db.componentecurricular.find_many(
        where={
            "nome": nome_componente,
            "ativo": True,
        },
        include={"modalidade": {"include": {"nivel": True}}},
    )

    for c in componentes:
        if (
            c.modalidade
            and c.modalidade.nome == nome_modalidade
            and c.modalidade.nivel
            and c.modalidade.nivel.nome == nome_nivel
        ):
            return c

    return None


async def buscar_ou_criar_assunto(db: Prisma, componente_id: str, nome_assunto: str):
    assunto = await db.assunto.find_first(
        where={
            "componenteId": componente_id,
            "nome": nome_assunto,
        }
    )
    if assunto:
        return assunto

    return await db.assunto.create(
        data={
            "componenteId": componente_id,
            "nome": nome_assunto,
            "ativo": True,
        }
    )


async def upsert_questao(db: Prisma, dados: dict, professor_id: str) -> tuple[bool, str]:
    componente = await buscar_componente(
        db,
        dados["componente"],
        dados["modalidade"],
        dados["nivel"],
    )
    if not componente:
        return (
            False,
            f"componente não encontrado: {dados['componente']} "
            f"({dados['modalidade']} / {dados['nivel']})",
        )

    assunto = await buscar_ou_criar_assunto(db, componente.id, "Geral — Demo")

    existente = await db.questao.find_first(
        where={
            "componenteId": componente.id,
            "enunciado": dados["enunciado"],
        }
    )
    if existente:
        return (True, "já existia")

    alternativas_json = [
        {"letra": letra, "texto": texto} for letra, texto in dados["alternativas"]
    ]

    try:
        await db.questao.create(
            data={
                "professorId": professor_id,
                "componenteId": componente.id,
                "assuntoId": assunto.id,
                "tipo": "MULTIPLA_ESCOLHA",
                "dificuldade": dados["dificuldade"],
                "enunciado": dados["enunciado"],
                "alternativas": alternativas_json,
                "respostaCorreta": dados["respostaCorreta"],
                "ativa": True,
            }
        )
        return (True, "criada")
    except PrismaError as e:
        return (False, f"prisma: {type(e).__name__} — {str(e)[:120]}")


async def main() -> int:
    db = Prisma()
    await db.connect()

    print("\n=== SEED QUESTÕES DEMO — SEED-SE ===\n")

    professor_user = await db.usuario.find_unique(where={"cpf": "98765432100"})
    if not professor_user:
        print("✗ Professor demo (Ana Paula, CPF 98765432100) não encontrado.")
        print("  Rode primeiro: python seed_catalogo.py")
        await db.disconnect()
        return 1

    professor_record = await db.professor.find_unique(
        where={"usuarioId": professor_user.id}
    )
    if not professor_record:
        print(f"✗ Registro Professor não encontrado para Usuario id={professor_user.id}.")
        print("  Verifique o seed_catalogo.py — deve criar Professor vinculado.")
        await db.disconnect()
        return 1

    print(f"→ Professor responsável: {professor_user.nome} (id: {professor_record.id})")
    print(f"→ Populando {len(QUESTOES_DEMO)} questões com 4 alternativas cada\n")

    contadores: dict[str, dict[str, int]] = {}
    falhas = 0

    for dados in QUESTOES_DEMO:
        comp = dados["componente"]
        dif = dados["dificuldade"]
        if comp not in contadores:
            contadores[comp] = {"FACIL": 0, "MEDIO": 0, "DIFICIL": 0}

        sucesso, msg = await upsert_questao(db, dados, professor_record.id)
        if sucesso:
            contadores[comp][dif] += 1
        else:
            falhas += 1
            print(f"   ✗ {dados['componente']} / {dados['dificuldade']}: {msg}")

    print("\n→ Resumo por componente (Ensino Médio Regular):")
    for comp, dist in contadores.items():
        total = sum(dist.values())
        print(
            f"   [ok] {comp:30s} → "
            f"F:{dist['FACIL']:2d}  M:{dist['MEDIO']:2d}  D:{dist['DIFICIL']:2d}  "
            f"(total {total})"
        )

    if falhas > 0:
        print(f"\n⚠ {falhas} questões falharam. Verifique os erros acima.")
        await db.disconnect()
        return 1

    print("\n=== SEED CONCLUÍDO ===\n")
    await db.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))