-- AlterTable: cada questão da tentativa guarda seu componente curricular,
-- permitindo pontuar por componente e agrupar o gabarito (certificação ENEM).
-- Coluna aditiva e anulável: tentativas antigas permanecem válidas (NULL).
ALTER TABLE "tentativa_questoes" ADD COLUMN "id_componente" TEXT;
