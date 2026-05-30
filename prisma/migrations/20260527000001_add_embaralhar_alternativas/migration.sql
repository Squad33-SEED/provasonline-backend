ALTER TABLE "simulados" ADD COLUMN IF NOT EXISTS "embaralhar_alternativas" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "tentativa_questoes" ADD COLUMN IF NOT EXISTS "alternativas_embaralhadas" JSONB;