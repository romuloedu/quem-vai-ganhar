#!/usr/bin/env python3
"""
atualizar.py
════════════
Ponto de entrada do pipeline de atualização pós-rodada da Copa 2026.

Uso:
    python scripts/atualizar.py
    ODDS_API_KEY=sua_chave python scripts/atualizar.py

Após rodar:
    git add .
    git commit -m "Atualiza após rodada X"
    git push
"""

import sys
from pathlib import Path

# Garante que o diretório scripts/ esteja no path para importar o pacote copa
sys.path.insert(0, str(Path(__file__).parent))

from copa.pipeline import PipelineAtualizacao

if __name__ == "__main__":
    PipelineAtualizacao().executar()
