-- CreateEnum
CREATE TYPE "StatusSimuladoLivre" AS ENUM ('EM_ANDAMENTO', 'FINALIZADO');

-- CreateTable
CREATE TABLE "simulados_livres" (
    "id_simulado_livre" TEXT NOT NULL,
    "id_aluno" TEXT NOT NULL,
    "titulo" VARCHAR(200) NOT NULL,
    "componente_ids" JSONB NOT NULL,
    "duracao_minutos" INTEGER NOT NULL,
    "status" "StatusSimuladoLivre" NOT NULL DEFAULT 'EM_ANDAMENTO',
    "pontuacao" DOUBLE PRECISION,
    "iniciado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finalizado_em" TIMESTAMP(3),
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "simulados_livres_pkey" PRIMARY KEY ("id_simulado_livre")
);

-- CreateTable
CREATE TABLE "itens_simulado_livre" (
    "id_simulado_livre" TEXT NOT NULL,
    "id_questao" TEXT NOT NULL,
    "ordem" INTEGER NOT NULL,
    "alternativa_marcada" CHAR(1),
    "respondido_em" TIMESTAMP(3),

    CONSTRAINT "itens_simulado_livre_pkey" PRIMARY KEY ("id_simulado_livre","id_questao")
);

-- AddForeignKey
ALTER TABLE "simulados_livres" ADD CONSTRAINT "simulados_livres_id_aluno_fkey" FOREIGN KEY ("id_aluno") REFERENCES "alunos"("id_aluno") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "itens_simulado_livre" ADD CONSTRAINT "itens_simulado_livre_id_simulado_livre_fkey" FOREIGN KEY ("id_simulado_livre") REFERENCES "simulados_livres"("id_simulado_livre") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "itens_simulado_livre" ADD CONSTRAINT "itens_simulado_livre_id_questao_fkey" FOREIGN KEY ("id_questao") REFERENCES "questoes"("id_questao") ON DELETE RESTRICT ON UPDATE CASCADE;
