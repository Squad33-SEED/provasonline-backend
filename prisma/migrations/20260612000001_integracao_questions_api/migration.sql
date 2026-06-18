-- AlterTable: componente aponta para uma matéria (subject) da API Questions
ALTER TABLE "componentes_curriculares" ADD COLUMN     "questions_subject_slug" TEXT;

-- DropForeignKey: tentativa não referencia mais o banco local de questões
ALTER TABLE "tentativa_questoes" DROP CONSTRAINT IF EXISTS "tentativa_questoes_id_questao_fkey";

-- AlterTable: snapshot da questão externa gravado na própria tentativa
ALTER TABLE "tentativa_questoes" ADD COLUMN     "enunciado" TEXT NOT NULL DEFAULT '',
ADD COLUMN     "url_imagem" TEXT,
ADD COLUMN     "alternativas" JSONB NOT NULL DEFAULT '[]',
ADD COLUMN     "resposta_correta" CHAR(1) NOT NULL DEFAULT 'A';

ALTER TABLE "tentativa_questoes" ALTER COLUMN "enunciado" DROP DEFAULT;
ALTER TABLE "tentativa_questoes" ALTER COLUMN "alternativas" DROP DEFAULT;
ALTER TABLE "tentativa_questoes" ALTER COLUMN "resposta_correta" DROP DEFAULT;
