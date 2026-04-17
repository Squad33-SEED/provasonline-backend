-- CreateEnum
CREATE TYPE "TipoUsuario" AS ENUM ('ADMIN', 'PROFESSOR', 'ALUNO');

-- CreateEnum
CREATE TYPE "TipoToken" AS ENUM ('ACCESS', 'REFRESH');

-- CreateEnum
CREATE TYPE "TipoQuestao" AS ENUM ('MULTIPLA_ESCOLHA', 'VERDADEIRO_FALSO', 'DISSERTATIVA');

-- CreateEnum
CREATE TYPE "TipoDificuldade" AS ENUM ('FACIL', 'MEDIO', 'DIFICIL');

-- CreateEnum
CREATE TYPE "StatusNotificacao" AS ENUM ('PENDENTE', 'LIDA', 'ARQUIVADA');

-- CreateEnum
CREATE TYPE "ResultadoAcesso" AS ENUM ('SUCESSO', 'FALHA');

-- CreateEnum
CREATE TYPE "TipoSimulado" AS ENUM ('SIMULADO', 'PROVA', 'QUESTIONARIO');

-- CreateEnum
CREATE TYPE "StatusSimulado" AS ENUM ('RASCUNHO', 'PUBLICADO', 'ARQUIVADO');

-- CreateEnum
CREATE TYPE "StatusAplicacao" AS ENUM ('AGENDADA', 'EM_ANDAMENTO', 'ENCERRADA');

-- CreateTable
CREATE TABLE "usuarios" (
    "id_usuario" TEXT NOT NULL,
    "nome" VARCHAR(200) NOT NULL,
    "email" TEXT NOT NULL,
    "cpf" CHAR(11) NOT NULL,
    "senha_hash" TEXT NOT NULL,
    "tipo" "TipoUsuario" NOT NULL DEFAULT 'ALUNO',
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "usuarios_pkey" PRIMARY KEY ("id_usuario")
);

-- CreateTable
CREATE TABLE "tokens_acesso" (
    "id_token" TEXT NOT NULL,
    "id_usuario" TEXT NOT NULL,
    "tipo" "TipoToken" NOT NULL,
    "token_hash" VARCHAR(255) NOT NULL,
    "expira_em" TIMESTAMP(3) NOT NULL,
    "revogado_em" TIMESTAMP(3),
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "tokens_acesso_pkey" PRIMARY KEY ("id_token")
);

-- CreateTable
CREATE TABLE "alunos" (
    "id_aluno" TEXT NOT NULL,
    "id_usuario" TEXT NOT NULL,
    "necessidade_especial" BOOLEAN NOT NULL DEFAULT false,
    "data_nascimento" DATE NOT NULL,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "alunos_pkey" PRIMARY KEY ("id_aluno")
);

-- CreateTable
CREATE TABLE "professores" (
    "id_professor" TEXT NOT NULL,
    "id_usuario" TEXT NOT NULL,
    "especialidade" TEXT,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "professores_pkey" PRIMARY KEY ("id_professor")
);

-- CreateTable
CREATE TABLE "niveis_ensino" (
    "id_nivel" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "descricao" TEXT,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "niveis_ensino_pkey" PRIMARY KEY ("id_nivel")
);

-- CreateTable
CREATE TABLE "modalidades" (
    "id_modalidade" TEXT NOT NULL,
    "id_nivel" TEXT NOT NULL,
    "nome" VARCHAR(50) NOT NULL,
    "supletivo" BOOLEAN NOT NULL DEFAULT false,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "modalidades_pkey" PRIMARY KEY ("id_modalidade")
);

-- CreateTable
CREATE TABLE "componentes_curriculares" (
    "id_componente" TEXT NOT NULL,
    "id_modalidade" TEXT NOT NULL,
    "nome" VARCHAR(100) NOT NULL,
    "codigo" VARCHAR(20) NOT NULL,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "componentes_curriculares_pkey" PRIMARY KEY ("id_componente")
);

-- CreateTable
CREATE TABLE "assuntos" (
    "id_assunto" TEXT NOT NULL,
    "id_componente" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "assuntos_pkey" PRIMARY KEY ("id_assunto")
);

-- CreateTable
CREATE TABLE "questoes" (
    "id_questao" TEXT NOT NULL,
    "id_professor" TEXT NOT NULL,
    "id_componente" TEXT NOT NULL,
    "id_assunto" TEXT NOT NULL,
    "tipo" "TipoQuestao" NOT NULL,
    "dificuldade" "TipoDificuldade" NOT NULL,
    "enunciado" TEXT NOT NULL,
    "url_imagem" TEXT,
    "alternativas" JSONB NOT NULL,
    "resposta_correta" CHAR(1) NOT NULL,
    "ativa" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "questoes_pkey" PRIMARY KEY ("id_questao")
);

-- CreateTable
CREATE TABLE "escolas" (
    "id_escola" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "municipio" TEXT NOT NULL,
    "inep" CHAR(8) NOT NULL,
    "ativo" BOOLEAN NOT NULL DEFAULT true,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "escolas_pkey" PRIMARY KEY ("id_escola")
);

-- CreateTable
CREATE TABLE "turmas" (
    "id_turma" TEXT NOT NULL,
    "id_escola" TEXT NOT NULL,
    "nome" TEXT NOT NULL,
    "ano_letivo" INTEGER NOT NULL,

    CONSTRAINT "turmas_pkey" PRIMARY KEY ("id_turma")
);

-- CreateTable
CREATE TABLE "turmas_alunos" (
    "id_turma" TEXT NOT NULL,
    "id_aluno" TEXT NOT NULL,
    "entrou_em" DATE NOT NULL,
    "saiu_em" DATE,

    CONSTRAINT "turmas_alunos_pkey" PRIMARY KEY ("id_turma","id_aluno")
);

-- CreateTable
CREATE TABLE "faixa_series" (
    "id_faixa" TEXT NOT NULL,
    "nome" VARCHAR(100) NOT NULL,
    "quantidade" INTEGER,

    CONSTRAINT "faixa_series_pkey" PRIMARY KEY ("id_faixa")
);

-- CreateTable
CREATE TABLE "simulados" (
    "id_simulado" TEXT NOT NULL,
    "id_professor" TEXT NOT NULL,
    "id_faixa" TEXT,
    "titulo" VARCHAR(200) NOT NULL,
    "descricao" TEXT,
    "tipo" "TipoSimulado" NOT NULL DEFAULT 'SIMULADO',
    "status" "StatusSimulado" NOT NULL DEFAULT 'RASCUNHO',
    "tempo_limite" INTEGER,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "atualizado_em" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "simulados_pkey" PRIMARY KEY ("id_simulado")
);

-- CreateTable
CREATE TABLE "simulado_questoes" (
    "id_simulado" TEXT NOT NULL,
    "id_questao" TEXT NOT NULL,
    "ordem" INTEGER NOT NULL,

    CONSTRAINT "simulado_questoes_pkey" PRIMARY KEY ("id_simulado","id_questao")
);

-- CreateTable
CREATE TABLE "aplicacoes" (
    "id_aplicacao" TEXT NOT NULL,
    "id_simulado" TEXT NOT NULL,
    "id_turma" TEXT NOT NULL,
    "data_inicio" TIMESTAMP(3) NOT NULL,
    "data_fim" TIMESTAMP(3) NOT NULL,
    "status" "StatusAplicacao" NOT NULL DEFAULT 'AGENDADA',
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "aplicacoes_pkey" PRIMARY KEY ("id_aplicacao")
);

-- CreateTable
CREATE TABLE "resultados_alunos" (
    "id_resultado" TEXT NOT NULL,
    "id_aplicacao" TEXT NOT NULL,
    "id_aluno" TEXT NOT NULL,
    "respostas" JSONB NOT NULL,
    "pontuacao" DOUBLE PRECISION,
    "iniciado_em" TIMESTAMP(3),
    "finalizado_em" TIMESTAMP(3),

    CONSTRAINT "resultados_alunos_pkey" PRIMARY KEY ("id_resultado")
);

-- CreateTable
CREATE TABLE "administradores_escola" (
    "id_admin" TEXT NOT NULL,
    "id_escola" TEXT NOT NULL,
    "id_usuario" TEXT NOT NULL,
    "cargo" VARCHAR(100),
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "administradores_escola_pkey" PRIMARY KEY ("id_admin")
);

-- CreateTable
CREATE TABLE "notificacoes" (
    "id_notificacao" TEXT NOT NULL,
    "id_usuario_dest" TEXT NOT NULL,
    "tipo" TEXT NOT NULL,
    "status" "StatusNotificacao" NOT NULL DEFAULT 'PENDENTE',
    "titulo" TEXT NOT NULL,
    "mensagem" TEXT NOT NULL,
    "referencia_id" TEXT,
    "referencia_tipo" TEXT,
    "lida_em" TIMESTAMP(3),

    CONSTRAINT "notificacoes_pkey" PRIMARY KEY ("id_notificacao")
);

-- CreateTable
CREATE TABLE "log_acesso" (
    "id_log" TEXT NOT NULL,
    "id_usuario" TEXT,
    "cpf_tentado" CHAR(11),
    "ip_origem" VARCHAR(45) NOT NULL,
    "dispositivo" TEXT,
    "resultado" "ResultadoAcesso" NOT NULL,
    "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "log_acesso_pkey" PRIMARY KEY ("id_log")
);

-- CreateIndex
CREATE UNIQUE INDEX "usuarios_email_key" ON "usuarios"("email");

-- CreateIndex
CREATE UNIQUE INDEX "usuarios_cpf_key" ON "usuarios"("cpf");

-- CreateIndex
CREATE UNIQUE INDEX "tokens_acesso_token_hash_key" ON "tokens_acesso"("token_hash");

-- CreateIndex
CREATE UNIQUE INDEX "alunos_id_usuario_key" ON "alunos"("id_usuario");

-- CreateIndex
CREATE UNIQUE INDEX "professores_id_usuario_key" ON "professores"("id_usuario");

-- CreateIndex
CREATE UNIQUE INDEX "escolas_inep_key" ON "escolas"("inep");

-- CreateIndex
CREATE UNIQUE INDEX "resultados_alunos_id_aplicacao_id_aluno_key" ON "resultados_alunos"("id_aplicacao", "id_aluno");

-- CreateIndex
CREATE UNIQUE INDEX "administradores_escola_id_escola_id_usuario_key" ON "administradores_escola"("id_escola", "id_usuario");

-- AddForeignKey
ALTER TABLE "tokens_acesso" ADD CONSTRAINT "tokens_acesso_id_usuario_fkey" FOREIGN KEY ("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "alunos" ADD CONSTRAINT "alunos_id_usuario_fkey" FOREIGN KEY ("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "professores" ADD CONSTRAINT "professores_id_usuario_fkey" FOREIGN KEY ("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "modalidades" ADD CONSTRAINT "modalidades_id_nivel_fkey" FOREIGN KEY ("id_nivel") REFERENCES "niveis_ensino"("id_nivel") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "componentes_curriculares" ADD CONSTRAINT "componentes_curriculares_id_modalidade_fkey" FOREIGN KEY ("id_modalidade") REFERENCES "modalidades"("id_modalidade") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assuntos" ADD CONSTRAINT "assuntos_id_componente_fkey" FOREIGN KEY ("id_componente") REFERENCES "componentes_curriculares"("id_componente") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "questoes" ADD CONSTRAINT "questoes_id_professor_fkey" FOREIGN KEY ("id_professor") REFERENCES "professores"("id_professor") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "questoes" ADD CONSTRAINT "questoes_id_componente_fkey" FOREIGN KEY ("id_componente") REFERENCES "componentes_curriculares"("id_componente") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "questoes" ADD CONSTRAINT "questoes_id_assunto_fkey" FOREIGN KEY ("id_assunto") REFERENCES "assuntos"("id_assunto") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "turmas" ADD CONSTRAINT "turmas_id_escola_fkey" FOREIGN KEY ("id_escola") REFERENCES "escolas"("id_escola") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "turmas_alunos" ADD CONSTRAINT "turmas_alunos_id_turma_fkey" FOREIGN KEY ("id_turma") REFERENCES "turmas"("id_turma") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "turmas_alunos" ADD CONSTRAINT "turmas_alunos_id_aluno_fkey" FOREIGN KEY ("id_aluno") REFERENCES "alunos"("id_aluno") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "simulados" ADD CONSTRAINT "simulados_id_professor_fkey" FOREIGN KEY ("id_professor") REFERENCES "professores"("id_professor") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "simulados" ADD CONSTRAINT "simulados_id_faixa_fkey" FOREIGN KEY ("id_faixa") REFERENCES "faixa_series"("id_faixa") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "simulado_questoes" ADD CONSTRAINT "simulado_questoes_id_simulado_fkey" FOREIGN KEY ("id_simulado") REFERENCES "simulados"("id_simulado") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "simulado_questoes" ADD CONSTRAINT "simulado_questoes_id_questao_fkey" FOREIGN KEY ("id_questao") REFERENCES "questoes"("id_questao") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "aplicacoes" ADD CONSTRAINT "aplicacoes_id_simulado_fkey" FOREIGN KEY ("id_simulado") REFERENCES "simulados"("id_simulado") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "aplicacoes" ADD CONSTRAINT "aplicacoes_id_turma_fkey" FOREIGN KEY ("id_turma") REFERENCES "turmas"("id_turma") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "resultados_alunos" ADD CONSTRAINT "resultados_alunos_id_aplicacao_fkey" FOREIGN KEY ("id_aplicacao") REFERENCES "aplicacoes"("id_aplicacao") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "resultados_alunos" ADD CONSTRAINT "resultados_alunos_id_aluno_fkey" FOREIGN KEY ("id_aluno") REFERENCES "alunos"("id_aluno") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "administradores_escola" ADD CONSTRAINT "administradores_escola_id_escola_fkey" FOREIGN KEY ("id_escola") REFERENCES "escolas"("id_escola") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "administradores_escola" ADD CONSTRAINT "administradores_escola_id_usuario_fkey" FOREIGN KEY ("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notificacoes" ADD CONSTRAINT "notificacoes_id_usuario_dest_fkey" FOREIGN KEY ("id_usuario_dest") REFERENCES "usuarios"("id_usuario") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "log_acesso" ADD CONSTRAINT "log_acesso_id_usuario_fkey" FOREIGN KEY ("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE SET NULL ON UPDATE CASCADE;
