"""
dixon_coles.py
==============
ModeloDixonColes — treina e prevê probabilidades 3-way usando o modelo
Dixon-Coles com pesos temporais exponenciais (time-decay).
"""

import math
import numpy as np
import pandas as pd
from scipy.stats import poisson as _poi
from scipy.optimize import minimize as _minimize


class ModeloDixonColes:
    """Implementa o modelo Dixon-Coles para previsão de resultados de futebol."""

    def __init__(self) -> None:
        """Inicializa os parâmetros do modelo como não treinados."""
        self.attack_map:  dict[str, float] = {}
        self.defense_map: dict[str, float] = {}
        self.rho: float = 0.0

    @staticmethod
    def _tau(x: int, y: int, lh: float, la: float, rho: float) -> float:
        """Fator de correção de Dixon-Coles para baixos placares (0-0, 0-1, 1-0, 1-1)."""
        if x == 0 and y == 0:
            return max(1e-9, 1 - lh * la * rho)
        if x == 0 and y == 1:
            return max(1e-9, 1 + lh * rho)
        if x == 1 and y == 0:
            return max(1e-9, 1 + la * rho)
        if x == 1 and y == 1:
            return max(1e-9, 1 - rho)
        return 1.0

    def prever(self, home: str, away: str, max_gols: int = 7) -> tuple[float, float, float]:
        """Retorna (p_home, p_draw, p_away) para a partida em campo neutro."""
        lh = max(0.01, self.attack_map.get(home, 1.0) * self.defense_map.get(away, 1.0))
        la = max(0.01, self.attack_map.get(away, 1.0) * self.defense_map.get(home, 1.0))
        gols = np.arange(max_gols)
        pmf_h = _poi.pmf(gols, lh)
        pmf_a = _poi.pmf(gols, la)
        grid  = np.outer(pmf_h, pmf_a)
        grid[0, 0] *= self._tau(0, 0, lh, la, self.rho)
        grid[0, 1] *= self._tau(0, 1, lh, la, self.rho)
        grid[1, 0] *= self._tau(1, 0, lh, la, self.rho)
        grid[1, 1] *= self._tau(1, 1, lh, la, self.rho)
        p_home = float(np.sum(np.tril(grid, -1)))
        p_draw = float(np.trace(grid))
        p_away = float(np.sum(np.triu(grid, 1)))
        tot = p_home + p_draw + p_away
        if tot <= 0:
            return 1 / 3, 1 / 3, 1 / 3
        return p_home / tot, p_draw / tot, p_away / tot

    def treinar(
        self,
        df_hist: pd.DataFrame,
        wc_teams: set,
        decay_days: int = 365,
    ) -> None:
        """Treina o modelo Dixon-Coles por MLE com pesos de decaimento temporal."""
        df = df_hist[
            df_hist["home_team"].isin(wc_teams) &
            df_hist["away_team"].isin(wc_teams) &
            (df_hist["date"] >= "2018-01-01")
        ].dropna(subset=["home_score", "away_score"]).copy()
        df["home_score"] = df["home_score"].astype(int)
        df["away_score"] = df["away_score"].astype(int)

        teams = sorted(wc_teams & (set(df["home_team"]) | set(df["away_team"])))
        t_idx = {t: i for i, t in enumerate(teams)}
        n     = len(teams)

        max_d = df["date"].max()
        df["days_ago"] = (max_d - df["date"]).dt.days
        w = np.exp(-df["days_ago"].values / decay_days)

        hi   = np.array([t_idx.get(t, -1) for t in df["home_team"]])
        ai   = np.array([t_idx.get(t, -1) for t in df["away_team"]])
        gh   = df["home_score"].values.astype(int)
        ga   = df["away_score"].values.astype(int)
        neut = df["neutral"].values.astype(bool)
        valido = (hi >= 0) & (ai >= 0)
        hi, ai, gh, ga, w, neut = (
            hi[valido], ai[valido], gh[valido], ga[valido], w[valido], neut[valido]
        )

        fac = np.array([math.lgamma(g + 1) for g in range(gh.max() + 1)])

        def nll(params):
            att  = np.exp(params[:n])
            dfs  = np.exp(params[n:2 * n])
            rho  = params[2 * n]
            hadv = np.exp(params[2 * n + 1])
            hm   = np.where(neut, 1.0, hadv)
            lh_v = np.maximum(1e-6, hm * att[hi] * dfs[ai])
            la_v = np.maximum(1e-6, att[ai] * dfs[hi])
            tau  = np.ones(len(gh))
            m00 = (gh == 0) & (ga == 0); tau[m00] = np.maximum(1e-9, 1 - lh_v[m00] * la_v[m00] * rho)
            m01 = (gh == 0) & (ga == 1); tau[m01] = np.maximum(1e-9, 1 + lh_v[m01] * rho)
            m10 = (gh == 1) & (ga == 0); tau[m10] = np.maximum(1e-9, 1 + la_v[m10] * rho)
            m11 = (gh == 1) & (ga == 1); tau[m11] = np.maximum(1e-9, 1 - rho)
            log_p = (
                np.log(tau)
                + gh * np.log(lh_v) - lh_v - fac[gh]
                + ga * np.log(la_v) - la_v - fac[ga]
            )
            return -float(np.dot(w, log_p))

        x0  = np.zeros(2 * n + 2)
        bds = [(-3, 3)] * n + [(-3, 3)] * n + [(-0.99, 0.5)] + [(-1, 1)]
        res = _minimize(nll, x0, method="L-BFGS-B", bounds=bds,
                        options={"maxiter": 300, "ftol": 1e-7})
        p = res.x
        self.attack_map  = {t: float(np.exp(p[i]))     for i, t in enumerate(teams)}
        self.defense_map = {t: float(np.exp(p[n + i])) for i, t in enumerate(teams)}
        self.rho         = float(p[2 * n])
