-- CreateEnum
CREATE TYPE "StatusImportacao" AS ENUM ('PENDENTE', 'PROCESSANDO', 'CONCLUIDA', 'FALHA');

-- CreateTable
CREATE TABLE "importacoes_alunos" (
    "id_importacao" TEXT NOT NULL,
    "arquivo_nome" TEXT NOT NULL,
    "status" "StatusImportacao" NOT NULL DEFAULT 'PENDENTE',
    "total_linhas" INTEGER NOT NULL DEFAULT 0,
    "processadas" INTEGER NOT NULL DEFAULT 0,
    "importados" INTEGER NOT NULL DEFAULT 0,
    "ignorados" INTEGER NOT NULL DEFAULT 0,
    "linhas" JSONB NOT NULL,
    "erros" JSONB NOT NULL DEFAULT '[]',
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "importacoes_alunos_pkey" PRIMARY KEY ("id_importacao")
);
