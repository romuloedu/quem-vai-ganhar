"""
poisson.py
==========
PrevisorPoisson — calibra Poisson independentes às probabilidades W/D/L
e devolve o placar mais provável consistente com o resultado previsto.
"""

import math
import numpy as np


class PrevisorPoisson:
    """Prevê o placar mais provável a partir de probabilidades (p_home, p_draw, p_away)."""

    def __init__(self, max_gols: int = 7) -> None:
        """Inicializa o cache interno de distribuições Poisson."""
        self._cache: dict[int, tuple] = {}
        self._max = max_gols

    def _obter_distribuicoes(self, max_g: int) -> tuple:
        """Computa (e armazena em cache) as matrizes de probabilidade Poisson."""
        if max_g not in self._cache:
            lam = np.arange(0.05, 5.01, 0.05)
            g   = np.arange(max_g, dtype=float)
            fac = np.array([math.factorial(int(k)) for k in g])
            pmf = np.exp(-lam[:, None]) * (lam[:, None] ** g) / fac
            H, A = np.meshgrid(np.arange(max_g), np.arange(max_g), indexing="ij")
            _pw  = (pmf @ (H > A).astype(float)) @ pmf.T
            _pd  = (pmf @ (H == A).astype(float)) @ pmf.T
            _pa  = (pmf @ (H < A).astype(float)) @ pmf.T
            self._cache[max_g] = (lam, pmf, _pw, _pd, _pa, H, A)
        return self._cache[max_g]

    def calibrar(self, ph: float, pd: float, pa: float,
                 resultado_previsto: str) -> str:
        """Retorna o placar mais provável consistente com `resultado_previsto`.

        `resultado_previsto` deve ser 'home', 'draw' ou 'away'.
        """
        lam, pmf, _pw, _pd_, _pa_, H, A = self._obter_distribuicoes(self._max)
        loss = (_pw - ph) ** 2 + (_pd_ - pd) ** 2 + (_pa_ - pa) ** 2
        i, j = divmod(int(np.argmin(loss)), len(lam))
        joint = pmf[i, :, None] * pmf[j, None, :]

        if resultado_previsto == "home":
            mask = H > A
        elif resultado_previsto == "away":
            mask = H < A
        else:
            mask = H == A

        bh, ba = divmod(int(np.argmax(np.where(mask, joint, 0))), self._max)
        return f"{bh}-{ba}"
