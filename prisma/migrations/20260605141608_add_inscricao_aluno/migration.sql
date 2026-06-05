-- CreateTable
CREATE TABLE "inscricoes_alunos" (
    "id_simulado" TEXT NOT NULL,
    "id_aluno" TEXT NOT NULL,
    "inscrito_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "inscricoes_alunos_pkey" PRIMARY KEY ("id_simulado","id_aluno")
);

-- AddForeignKey
ALTER TABLE "inscricoes_alunos" ADD CONSTRAINT "inscricoes_alunos_id_simulado_fkey" FOREIGN KEY ("id_simulado") REFERENCES "simulados"("id_simulado") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "inscricoes_alunos" ADD CONSTRAINT "inscricoes_alunos_id_aluno_fkey" FOREIGN KEY ("id_aluno") REFERENCES "alunos"("id_aluno") ON DELETE RESTRICT ON UPDATE CASCADE;
