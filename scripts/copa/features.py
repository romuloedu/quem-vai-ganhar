"""
features.py
===========
ExtratordeFeaturas — constrói o vetor de features para uma partida
a partir do histórico, rankings, elo e dados estáticos.
"""

import numpy as np
import pandas as pd
from typing import Any

from copa.config import FEAT_COLS
from copa.historico import HistoricoPartidas


def elo_expected(ea: float, eb: float) -> float:
    """Probabilidade esperada de `ea` vencer `eb` pelo sistema Elo."""
    return 1 / (1 + 10 ** ((eb - ea) / 400))


class ExtratordeFeaturas:
    """Constrói vetores de features para uso nos modelos de ML."""

    def __init__(
        self,
        historico: HistoricoPartidas,
        rank_map: dict,
        elo_map: dict,
        conf_map: dict,
        squad_value_map: dict,
        wc_apps_map: dict,
        squad_age_map: dict,
        feat_cols: list[str] | None = None,
    ) -> None:
        """Recebe os mapas de dados estáticos e o histórico de partidas."""
        self.historico = historico
        self.rank_map = rank_map
        self.elo_map  = elo_map
        self.conf_map = conf_map
        self.squad_value_map = squad_value_map
        self.wc_apps_map = wc_apps_map
        self.squad_age_map = squad_age_map
        self.feat_cols = feat_cols or FEAT_COLS

    def construir_vetor(
        self, home: str, away: str, date: Any, neutral: int = 1
    ) -> list[float]:
        """Retorna o vetor de features (lista ordenada por FEAT_COLS) para a partida."""
        fh = self.historico.forma_recente(home, date)
        fa = self.historico.forma_recente(away, date)
        hh = self.historico.confronto_direto(home, away, date)

        eh  = self.elo_map.get(home, 1550)
        ea  = self.elo_map.get(away, 1550)
        rh  = self.rank_map.get(home, 80)
        ra  = self.rank_map.get(away, 80)
        sv_h = self.squad_value_map.get(home, float(np.log1p(200)))
        sv_a = self.squad_value_map.get(away, float(np.log1p(200)))

        row = {
            "h_win_rate":          fh["win_rate"],
            "h_draw_rate":         fh["draw_rate"],
            "h_goals_scored_avg":  fh["goals_scored_avg"],
            "h_goals_conceded_avg": fh["goals_conceded_avg"],
            "h_clean_sheets_rate": fh["clean_sheets_rate"],
            "h_goal_diff_avg":     fh["goal_diff_avg"],
            "h_form_pts":          fh["form_pts"],
            "h_fifa_rank":         rh,
            "h_elo":               eh,
            "h_elo_expected":      elo_expected(eh, ea),
            "a_win_rate":          fa["win_rate"],
            "a_draw_rate":         fa["draw_rate"],
            "a_goals_scored_avg":  fa["goals_scored_avg"],
            "a_goals_conceded_avg": fa["goals_conceded_avg"],
            "a_clean_sheets_rate": fa["clean_sheets_rate"],
            "a_goal_diff_avg":     fa["goal_diff_avg"],
            "a_form_pts":          fa["form_pts"],
            "a_fifa_rank":         ra,
            "a_elo":               ea,
            "rank_diff":           rh - ra,
            "elo_diff":            eh - ea,
            "elo_expected_home":   elo_expected(eh, ea),
            "h2h_win_rate":        hh["h2h_win_rate"],
            "h2h_goal_diff":       hh["h2h_goal_diff"],
            "h2h_games":           hh["h2h_games"],
            "neutral":             neutral,
            "h_confederation":     self.conf_map.get(home, 3),
            "a_confederation":     self.conf_map.get(away, 3),
            "h_squad_value":       sv_h,
            "a_squad_value":       sv_a,
            "h_wc_appearances":    self.wc_apps_map.get(home, 5),
            "a_wc_appearances":    self.wc_apps_map.get(away, 5),
            "h_squad_age":         self.squad_age_map.get(home, 27.0),
            "a_squad_age":         self.squad_age_map.get(away, 27.0),
            "squad_value_diff":    sv_h - sv_a,
            "wc_exp_diff":         self.wc_apps_map.get(home, 5) - self.wc_apps_map.get(away, 5),
            "draw_rate_product":   fh["draw_rate"] * fa["draw_rate"],
            "elo_closeness":       float(np.exp(-abs(eh - ea) / 300)),
        }
        return [row[c] for c in self.feat_cols]

    def construir_matriz(
        self,
        pares: list[tuple[str, str, Any]],
        neutral: int = 1,
    ) -> np.ndarray:
        """Constrói a matriz de features para uma lista de (home, away, date)."""
        return np.array(
            [self.construir_vetor(h, a, d, neutral) for h, a, d in pares],
            dtype=np.float32,
        )
