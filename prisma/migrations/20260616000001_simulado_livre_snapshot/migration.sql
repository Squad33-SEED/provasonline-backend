-- Simulado Livre passa a guardar SNAPSHOT da questao (origem: API externa de
-- questoes), em vez de FK para a tabela local `questoes`. Mesmo padrao do
-- fluxo principal (tentativa_questoes). Colunas nullable para nao quebrar os
-- itens ja existentes (simulados livres antigos).

ALTER TABLE "itens_simulado_livre" DROP CONSTRAINT IF EXISTS "itens_simulado_livre_id_questao_fkey";

ALTER TABLE "itens_simulado_livre"
  ADD COLUMN "enunciado" TEXT,
  ADD COLUMN "url_imagem" TEXT,
  ADD COLUMN "alternativas" JSONB,
  ADD COLUMN "resposta_correta" CHAR(1),
  ADD COLUMN "assunto" TEXT,
  ADD COLUMN "dificuldade" TEXT;
