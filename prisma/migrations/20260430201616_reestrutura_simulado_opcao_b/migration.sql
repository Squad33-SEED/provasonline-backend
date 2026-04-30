/*
  Warnings:

  - You are about to drop the column `respostas` on the `resultados_alunos` table. All the data in the column will be lost.
  - You are about to drop the column `tempo_limite` on the `simulados` table. All the data in the column will be lost.
  - You are about to drop the `simulado_questoes` table. If the table is not empty, all the data it contains will be lost.
  - A unique constraint covering the columns `[id_escola,nome,ano_letivo]` on the table `turmas` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `duracao_minutos` to the `simulados` table without a default value. This is not possible if the table is not empty.
  - Added the required column `id_componente` to the `simulados` table without a default value. This is not possible if the table is not empty.
  - Added the required column `janela_fim` to the `simulados` table without a default value. This is not possible if the table is not empty.
  - Added the required column `janela_inicio` to the `simulados` table without a default value. This is not possible if the table is not empty.
  - Added the required column `vagas` to the `simulados` table without a default value. This is not possible if the table is not empty.
  - Added the required column `id_modalidade` to the `turmas` table without a default value. This is not possible if the table is not empty.

*/
-- DropForeignKey
ALTER TABLE "simulado_questoes" DROP CONSTRAINT "simulado_questoes_id_questao_fkey";

-- DropForeignKey
ALTER TABLE "simulado_questoes" DROP CONSTRAINT "simulado_questoes_id_simulado_fkey";

-- AlterTable
ALTER TABLE "resultados_alunos" DROP COLUMN "respostas";

-- AlterTable
ALTER TABLE "simulados" DROP COLUMN "tempo_limite",
ADD COLUMN     "duracao_minutos" INTEGER NOT NULL,
ADD COLUMN     "id_componente" TEXT NOT NULL,
ADD COLUMN     "janela_fim" TIMESTAMP(3) NOT NULL,
ADD COLUMN     "janela_inicio" TIMESTAMP(3) NOT NULL,
ADD COLUMN     "qtd_dificil" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "qtd_facil" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "qtd_medio" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "vagas" INTEGER NOT NULL;

-- AlterTable
ALTER TABLE "turmas" ADD COLUMN     "id_modalidade" TEXT NOT NULL;

-- AlterTable
ALTER TABLE "usuarios" ADD COLUMN     "senha_provisoria" BOOLEAN NOT NULL DEFAULT true,
ALTER COLUMN "email" DROP NOT NULL;

-- DropTable
DROP TABLE "simulado_questoes";

-- CreateTable
CREATE TABLE "tentativa_questoes" (
    "id_resultado" TEXT NOT NULL,
    "id_questao" TEXT NOT NULL,
    "ordem" INTEGER NOT NULL,
    "alternativa_marcada" CHAR(1),
    "respondido_em" TIMESTAMP(3),

    CONSTRAINT "tentativa_questoes_pkey" PRIMARY KEY ("id_resultado","id_questao")
);

-- CreateIndex
CREATE UNIQUE INDEX "turmas_id_escola_nome_ano_letivo_key" ON "turmas"("id_escola", "nome", "ano_letivo");

-- AddForeignKey
ALTER TABLE "turmas" ADD CONSTRAINT "turmas_id_modalidade_fkey" FOREIGN KEY ("id_modalidade") REFERENCES "modalidades"("id_modalidade") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "simulados" ADD CONSTRAINT "simulados_id_componente_fkey" FOREIGN KEY ("id_componente") REFERENCES "componentes_curriculares"("id_componente") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tentativa_questoes" ADD CONSTRAINT "tentativa_questoes_id_resultado_fkey" FOREIGN KEY ("id_resultado") REFERENCES "resultados_alunos"("id_resultado") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "tentativa_questoes" ADD CONSTRAINT "tentativa_questoes_id_questao_fkey" FOREIGN KEY ("id_questao") REFERENCES "questoes"("id_questao") ON DELETE RESTRICT ON UPDATE CASCADE;
