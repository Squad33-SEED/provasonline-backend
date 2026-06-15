CREATE TABLE "ips_autorizados" (
  "id_ip_autorizado" TEXT NOT NULL,
  "ip" VARCHAR(45) NOT NULL,
  "descricao" TEXT,
  "ativo" BOOLEAN NOT NULL DEFAULT true,
  "criado_em" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "atualizado_em" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "ips_autorizados_pkey" PRIMARY KEY ("id_ip_autorizado")
);