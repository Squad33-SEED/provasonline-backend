-- CreateEnum
CREATE TYPE "StatusResultado" AS ENUM ('EM_ANDAMENTO', 'FINALIZADO', 'EXPIRADO');

-- DropIndex (substituída por nova com simuladoId)
DROP INDEX IF EXISTS "resultados_alunos_id_aplicacao_id_aluno_key";

-- AlterTable resultados_alunos
ALTER TABLE "resultados_alunos"
    ADD COLUMN "id_simulado"      TEXT,
    ADD COLUMN "status_resultado" "StatusResultado" NOT NULL DEFAULT 'EM_ANDAMENTO',
    ALTER COLUMN "id_aplicacao"   DROP NOT NULL;

-- AddForeignKey
ALTER TABLE "resultados_alunos"
    ADD CONSTRAINT "resultados_alunos_id_simulado_fkey"
    FOREIGN KEY ("id_simulado") REFERENCES "simulados"("id_simulado")
    ON DELETE RESTRICT ON UPDATE CASCADE;

-- CreateIndex (índice único parcial: só quando simuladoId não é nulo)
CREATE UNIQUE INDEX "resultados_alunos_id_simulado_id_aluno_key"
    ON "resultados_alunos"("id_simulado", "id_aluno")
    WHERE "id_simulado" IS NOT NULL;