"""
repositorio.py
==============
RepositorioDados — centraliza todas as operações de I/O:
leitura e escrita de JSON, CSV e pickle.
"""

import json
import pickle
from pathlib import Path
from typing import Any

import pandas as pd


class RepositorioDados:
    """Centraliza load/save de todos os arquivos de dados do projeto."""

    def __init__(self, dados: Path) -> None:
        """Recebe o diretório base onde os arquivos de dados estão armazenados."""
        self.dados = dados

    # ── JSON ────────────────────────────────────────────────

    def ler_json(self, nome: str, padrao: Any = None) -> Any:
        """Lê um arquivo JSON; retorna `padrao` se o arquivo não existir."""
        caminho = self.dados / nome
        if not caminho.exists():
            return padrao
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)

    def salvar_json(self, nome: str, dados: Any, *, indent: int = 2,
                    separators: tuple | None = None) -> None:
        """Persiste `dados` como JSON no diretório de dados."""
        caminho = self.dados / nome
        kwargs: dict = {"ensure_ascii": False}
        if separators is not None:
            kwargs["separators"] = separators
        else:
            kwargs["indent"] = indent
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, **kwargs)

    # ── CSV ─────────────────────────────────────────────────

    def ler_csv(self, nome: str, **kwargs) -> pd.DataFrame:
        """Lê um CSV do diretório de dados; repassa kwargs para pd.read_csv."""
        return pd.read_csv(self.dados / nome, **kwargs)

    def salvar_csv(self, nome: str, df: pd.DataFrame) -> None:
        """Persiste um DataFrame como CSV sem índice."""
        df.to_csv(self.dados / nome, index=False)

    # ── Pickle ──────────────────────────────────────────────

    def salvar_pickle(self, nome: str, obj: Any) -> None:
        """Serializa `obj` em pickle no diretório de dados."""
        with open(self.dados / nome, "wb") as f:
            pickle.dump(obj, f)

    # ── Verificações ────────────────────────────────────────

    def existe(self, nome: str) -> bool:
        """Retorna True se o arquivo existe no diretório de dados."""
        return (self.dados / nome).exists()
