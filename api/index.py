"""Entrypoint serverless para o Vercel.

O Vercel detecta arquivos em /api como funcoes serverless. Expor `app`
(uma aplicacao ASGI do FastAPI) faz o runtime @vercel/python executa-la.
Subimos um nivel no sys.path para importar `main` e o pacote `src` da raiz.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402

__all__ = ["app"]
