-- CreateEnum
CREATE TYPE "TipoCandidato" AS ENUM ('REGULAR', 'EXTERNO');

-- CreateEnum
CREATE TYPE "TipoCertificado" AS ENUM ('CONCLUSAO', 'PROFICIENCIA_PARCIAL');

-- AlterTable
ALTER TABLE "niveis_ensino" ADD COLUMN     "ordem" INTEGER NOT NULL DEFAULT 0;

-- AlterTable
ALTER TABLE "simulados" ADD COLUMN     "gera_certificado" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "id_nivel" TEXT,
ADD COLUMN     "nota_minima_certificacao" DOUBLE PRECISION;

-- AlterTable
ALTER TABLE "usuarios" ADD COLUMN     "prereq_documento" TEXT,
ADD COLUMN     "prereq_validado" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "prereq_validado_em" TIMESTAMP(3),
ADD COLUMN     "prereq_validado_por" TEXT,
ADD COLUMN     "tipo_candidato" "TipoCandidato" NOT NULL DEFAULT 'REGULAR';

-- CreateTable
CREATE TABLE "niveis_componentes" (
    "id_nivel" TEXT NOT NULL,
    "id_componente" TEXT NOT NULL,
    "obrigatorio" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "niveis_componentes_pkey" PRIMARY KEY ("id_nivel","id_componente")
);

-- CreateTable
CREATE TABLE "aproveitamentos_candidato" (
    "id_aproveitamento" TEXT NOT NULL,
    "id_aluno" TEXT NOT NULL,
    "id_componente" TEXT NOT NULL,
    "id_nivel" TEXT NOT NULL,
    "ano_referencia" INTEGER NOT NULL,
    "aprovado" BOOLEAN NOT NULL DEFAULT true,
    "nota_obtida" DOUBLE PRECISION NOT NULL,
    "id_resultado" TEXT NOT NULL,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "aproveitamentos_candidato_pkey" PRIMARY KEY ("id_aproveitamento")
);

-- CreateTable
CREATE TABLE "certificados" (
    "id_certificado" TEXT NOT NULL,
    "id_aluno" TEXT NOT NULL,
    "id_nivel" TEXT NOT NULL,
    "ano_referencia" INTEGER NOT NULL,
    "tipo" "TipoCertificado" NOT NULL DEFAULT 'CONCLUSAO',
    "codigo_verificacao" TEXT NOT NULL,
    "assinatura_hash" TEXT NOT NULL,
    "componentes_aprovados" JSONB NOT NULL,
    "emitido_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "certificados_pkey" PRIMARY KEY ("id_certificado")
);

-- CreateIndex
CREATE UNIQUE INDEX "aproveitamentos_candidato_id_aluno_id_componente_id_nivel_a_key" ON "aproveitamentos_candidato"("id_aluno", "id_componente", "id_nivel", "ano_referencia");

-- CreateIndex
CREATE UNIQUE INDEX "certificados_codigo_verificacao_key" ON "certificados"("codigo_verificacao");

-- CreateIndex
CREATE UNIQUE INDEX "certificados_id_aluno_id_nivel_ano_referencia_tipo_key" ON "certificados"("id_aluno", "id_nivel", "ano_referencia", "tipo");

-- AddForeignKey
ALTER TABLE "simulados" ADD CONSTRAINT "simulados_id_nivel_fkey" FOREIGN KEY ("id_nivel") REFERENCES "niveis_ensino"("id_nivel") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "niveis_componentes" ADD CONSTRAINT "niveis_componentes_id_nivel_fkey" FOREIGN KEY ("id_nivel") REFERENCES "niveis_ensino"("id_nivel") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "niveis_componentes" ADD CONSTRAINT "niveis_componentes_id_componente_fkey" FOREIGN KEY ("id_componente") REFERENCES "componentes_curriculares"("id_componente") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "aproveitamentos_candidato" ADD CONSTRAINT "aproveitamentos_candidato_id_aluno_fkey" FOREIGN KEY ("id_aluno") REFERENCES "alunos"("id_aluno") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "aproveitamentos_candidato" ADD CONSTRAINT "aproveitamentos_candidato_id_componente_fkey" FOREIGN KEY ("id_componente") REFERENCES "componentes_curriculares"("id_componente") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "aproveitamentos_candidato" ADD CONSTRAINT "aproveitamentos_candidato_id_nivel_fkey" FOREIGN KEY ("id_nivel") REFERENCES "niveis_ensino"("id_nivel") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "aproveitamentos_candidato" ADD CONSTRAINT "aproveitamentos_candidato_id_resultado_fkey" FOREIGN KEY ("id_resultado") REFERENCES "resultados_alunos"("id_resultado") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "certificados" ADD CONSTRAINT "certificados_id_aluno_fkey" FOREIGN KEY ("id_aluno") REFERENCES "alunos"("id_aluno") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "certificados" ADD CONSTRAINT "certificados_id_nivel_fkey" FOREIGN KEY ("id_nivel") REFERENCES "niveis_ensino"("id_nivel") ON DELETE RESTRICT ON UPDATE CASCADE;
