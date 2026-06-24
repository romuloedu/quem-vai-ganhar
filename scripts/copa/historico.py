"""
historico.py
============
HistoricoPartidas — constrói o log de partidas e computa features de forma
recente e confronto direto com cache interno para evitar reprocessamento.
"""

import pandas as pd
import numpy as np
from typing import Any


class HistoricoPartidas:
    """Mantém o log de partidas e fornece métricas de forma e confronto direto."""

    def __init__(self, log: pd.DataFrame) -> None:
        """Recebe o log já construído (via build_log) e inicializa o cache."""
        self.log = log
        # cache: {(equipe, before_ts): dict_de_features}
        self._cache_forma: dict[tuple, dict] = {}

    @staticmethod
    def build_log(df_hist: pd.DataFrame) -> pd.DataFrame:
        """Constrói o log de partidas — uma linha por time por jogo."""
        rows = []
        for _, r in df_hist.iterrows():
            for side in ["home", "away"]:
                t  = r["home_team"] if side == "home" else r["away_team"]
                o  = r["away_team"] if side == "home" else r["home_team"]
                gf = int(r["home_score"] if side == "home" else r["away_score"])
                ga = int(r["away_score"] if side == "home" else r["home_score"])
                res = "W" if gf > ga else ("D" if gf == ga else "L")
                rows.append({
                    "date": r["date"], "team": t, "opponent": o,
                    "goals_for": gf, "goals_against": ga, "result": res,
                    "neutral": r["neutral"],
                })
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    def forma_recente(self, team: str, before, n: int = 10) -> dict:
        """Retorna métricas dos últimos `n` jogos do time antes de `before`.

        Usa cache interno para evitar varreduras repetidas no log.
        Retorna valores neutros se não houver jogos suficientes.
        """
        before_ts = pd.Timestamp(before)
        chave = (team, before_ts)
        if chave in self._cache_forma:
            return self._cache_forma[chave]

        past = self.log[(self.log["team"] == team) & (self.log["date"] < before_ts)].tail(n)

        if len(past) == 0:
            resultado = {
                "win_rate": 0.5, "draw_rate": 0.25, "goals_scored_avg": 1.5,
                "goals_conceded_avg": 1.2, "clean_sheets_rate": 0.3,
                "goal_diff_avg": 0.3, "form_pts": 0.5, "games_played": 0,
            }
        else:
            _n   = len(past)
            wins  = (past["result"] == "W").sum()
            draws = (past["result"] == "D").sum()
            wts   = np.exp(np.linspace(-1, 0, _n))
            wts  /= wts.sum()
            gf    = past["goals_for"].values
            ga    = past["goals_against"].values
            resultado = {
                "win_rate": wins / _n,
                "draw_rate": draws / _n,
                "goals_scored_avg": float(np.average(gf, weights=wts)),
                "goals_conceded_avg": float(np.average(ga, weights=wts)),
                "clean_sheets_rate": (ga == 0).sum() / _n,
                "goal_diff_avg": float(np.average(gf - ga, weights=wts)),
                "form_pts": (wins * 3 + draws) / (_n * 3),
                "games_played": _n,
            }

        self._cache_forma[chave] = resultado
        return resultado

    def confronto_direto(self, time_a: str, time_b: str, before, anos: int = 5) -> dict:
        """Retorna métricas de confronto direto entre dois times nos últimos `anos` anos."""
        before_ts = pd.Timestamp(before)
        cut = before_ts - pd.DateOffset(years=anos)
        h = self.log[
            (self.log["team"] == time_a) &
            (self.log["opponent"] == time_b) &
            (self.log["date"] >= cut) &
            (self.log["date"] < before_ts)
        ]
        if len(h) == 0:
            return {"h2h_win_rate": 0.5, "h2h_goal_diff": 0.0, "h2h_games": 0}
        return {
            "h2h_win_rate": (h["result"] == "W").sum() / len(h),
            "h2h_goal_diff": float((h["goals_for"] - h["goals_against"]).mean()),
            "h2h_games": len(h),
        }

    def aquecer_cache(self, teams: list[str], datas: list[str]) -> None:
        """Pré-aquece o cache de forma para todos os times e datas fornecidos."""
        for date_str in datas:
            for team in teams:
                self.forma_recente(team, date_str)
