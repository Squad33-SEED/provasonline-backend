-- CreateTable
CREATE TABLE "professores_turmas" (
    "id_professor" TEXT NOT NULL,
    "id_turma"     TEXT NOT NULL,
    CONSTRAINT "professores_turmas_pkey" PRIMARY KEY ("id_professor","id_turma")
);

-- AddForeignKey
ALTER TABLE "professores_turmas"
    ADD CONSTRAINT "professores_turmas_id_professor_fkey"
    FOREIGN KEY ("id_professor") REFERENCES "professores"("id_professor")
    ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "professores_turmas"
    ADD CONSTRAINT "professores_turmas_id_turma_fkey"
    FOREIGN KEY ("id_turma") REFERENCES "turmas"("id_turma")
    ON DELETE CASCADE ON UPDATE CASCADE;