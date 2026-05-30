"""Entrypoint serverless para o Vercel.

O Vercel procura por funções dentro da pasta /api. Ao expor a variável
`app` (uma aplicação ASGI do FastAPI), o runtime @vercel/python a executa
diretamente. Subimos um nível no sys.path para conseguir importar `main`
e o pacote `src` que vivem na raiz do projeto.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402

# Vercel usa esta variável como handler ASGI.
__all__ = ["app"]
