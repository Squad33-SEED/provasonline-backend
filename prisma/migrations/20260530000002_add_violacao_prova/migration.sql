-- CreateTable
CREATE TABLE "violacoes_prova" (
    "id_violacao" TEXT NOT NULL,
    "id_resultado" TEXT NOT NULL,
    "tipo" TEXT NOT NULL,
    "detalhe" TEXT,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "violacoes_prova_pkey" PRIMARY KEY ("id_violacao")
);

-- AddForeignKey
ALTER TABLE "violacoes_prova" ADD CONSTRAINT "violacoes_prova_id_resultado_fkey" FOREIGN KEY ("id_resultado") REFERENCES "resultados_alunos"("id_resultado") ON DELETE CASCADE ON UPDATE CASCADE;
