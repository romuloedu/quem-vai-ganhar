"""
logit_ordenado.py
=================
ModeloLogitOrdenado — regressão logística ordenada (Frank-Hall) para resultados
de futebol tratados como variável ordinal: fora < empate < casa.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


class ModeloLogitOrdenado:
    """Logit ordenado que produz P(fora), P(empate), P(casa) por partida."""

    def __init__(self, C: float = 0.5, seed: int = 42) -> None:
        """Inicializa com parâmetro de regularização C e semente aleatória."""
        self.C    = C
        self.seed = seed
        self.scaler: StandardScaler | None = None
        self.clf_gt0: LogisticRegression | None = None   # P(y > fora)
        self.clf_gt1: LogisticRegression | None = None   # P(y = casa)

    def treinar(self, X: np.ndarray, y: np.ndarray) -> None:
        """Ajusta o scaler e os dois classificadores binários."""
        self.scaler = StandardScaler().fit(X)
        Xs = self.scaler.transform(X)
        self.clf_gt0 = LogisticRegression(
            C=self.C, max_iter=1000, random_state=self.seed
        ).fit(Xs, (y > 0).astype(int))
        self.clf_gt1 = LogisticRegression(
            C=self.C, max_iter=1000, random_state=self.seed
        ).fit(Xs, (y > 1).astype(int))

    def prever_lote(self, X: np.ndarray) -> np.ndarray:
        """Retorna array (N, 3) com [p_away, p_draw, p_home] normalizado por linha."""
        Xs      = self.scaler.transform(np.asarray(X, dtype=np.float32))
        p_gt0   = self.clf_gt0.predict_proba(Xs)[:, 1]
        p_gt1   = self.clf_gt1.predict_proba(Xs)[:, 1]
        p_away  = np.clip(1 - p_gt0, 1e-6, None)
        p_draw  = np.clip(p_gt0 - p_gt1, 1e-6, None)
        p_home  = np.clip(p_gt1, 1e-6, None)
        P = np.vstack([p_away, p_draw, p_home]).T
        return P / P.sum(axis=1, keepdims=True)

    def serializar(self) -> tuple:
        """Retorna tupla (scaler, clf_gt0, clf_gt1) para persistência em pickle."""
        return (self.scaler, self.clf_gt0, self.clf_gt1)

    @classmethod
    def de_tupla(cls, tupla: tuple) -> "ModeloLogitOrdenado":
        """Reconstrói o modelo a partir de uma tupla serializada em pickle."""
        obj = cls()
        obj.scaler, obj.clf_gt0, obj.clf_gt1 = tupla
        return obj
