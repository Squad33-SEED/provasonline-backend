-- DropForeignKey
ALTER TABLE "resultados_alunos" DROP CONSTRAINT "resultados_alunos_id_aplicacao_fkey";

-- DropForeignKey
ALTER TABLE "resultados_alunos" DROP CONSTRAINT "resultados_alunos_id_simulado_fkey";

-- AddForeignKey
ALTER TABLE "resultados_alunos" ADD CONSTRAINT "resultados_alunos_id_simulado_fkey" FOREIGN KEY ("id_simulado") REFERENCES "simulados"("id_simulado") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "resultados_alunos" ADD CONSTRAINT "resultados_alunos_id_aplicacao_fkey" FOREIGN KEY ("id_aplicacao") REFERENCES "aplicacoes"("id_aplicacao") ON DELETE SET NULL ON UPDATE CASCADE;
