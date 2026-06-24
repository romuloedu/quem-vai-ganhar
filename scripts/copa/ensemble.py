"""
ensemble.py
===========
ModeloEnsemble — combina XGBoost, RandomForest, Dixon-Coles e Logit ordenado
para produzir probabilidades finais (p_home, p_draw, p_away).
"""

import numpy as np
from copa.dixon_coles import ModeloDixonColes
from copa.logit_ordenado import ModeloLogitOrdenado


class ModeloEnsemble:
    """Ensemble de quatro modelos que produz probabilidades calibradas."""

    def __init__(
        self,
        xgb_model,
        rf_model,
        dixon_coles: ModeloDixonColes,
        ordinal: ModeloLogitOrdenado | None = None,
    ) -> None:
        """Recebe os modelos treinados; `ordinal` é opcional."""
        self.xgb     = xgb_model
        self.rf      = rf_model
        self.dc      = dixon_coles
        self.ordinal = ordinal

    def prever(
        self, home: str, away: str, feat_vec: list
    ) -> tuple[float, float, float]:
        """Retorna (p_home, p_draw, p_away) para uma única partida."""
        xp = self.xgb.predict_proba([feat_vec])[0]   # [p_away, p_draw, p_home]
        rp = self.rf.predict_proba([feat_vec])[0]     # [p_away, p_draw, p_home]
        ph_dc, pd_dc, pa_dc = self.dc.prever(home, away)

        if self.ordinal is not None:
            po = self.ordinal.prever_lote([feat_vec])[0]  # [p_away, p_draw, p_home]
            p_h = (xp[2] + rp[2] + ph_dc + po[2]) / 4
            p_d = (xp[1] + rp[1] + pd_dc + po[1]) / 4
            p_a = (xp[0] + rp[0] + pa_dc + po[0]) / 4
        else:
            p_h = (xp[2] + rp[2] + ph_dc) / 3
            p_d = (xp[1] + rp[1] + pd_dc) / 3
            p_a = (xp[0] + rp[0] + pa_dc) / 3

        tot = p_h + p_d + p_a
        return p_h / tot, p_d / tot, p_a / tot

    def prever_lote(
        self,
        chaves: list[tuple[str, str, str]],
        vetores: np.ndarray,
    ) -> dict[tuple[str, str, str], tuple[float, float, float]]:
        """Prevê (p_home, p_draw, p_away) para um lote de partidas em batch.

        `chaves` é lista de (home, away, date_str); `vetores` é a matriz de features.
        Retorna dicionário indexado pelas mesmas chaves.
        """
        X = np.asarray(vetores, dtype=np.float32)
        xgb_proba = self.xgb.predict_proba(X)       # (N, 3): [p_away, p_draw, p_home]
        rf_proba  = self.rf.predict_proba(X)
        ord_proba = self.ordinal.prever_lote(X) if self.ordinal is not None else None

        resultado: dict = {}
        for i, (home, away, date_str) in enumerate(chaves):
            xp = xgb_proba[i]
            rp = rf_proba[i]
            ph_dc, pd_dc, pa_dc = self.dc.prever(home, away)

            if ord_proba is not None:
                po = ord_proba[i]
                ph = (xp[2] + rp[2] + ph_dc + po[2]) / 4
                pd_ = (xp[1] + rp[1] + pd_dc + po[1]) / 4
                pa  = (xp[0] + rp[0] + pa_dc + po[0]) / 4
            else:
                ph  = (xp[2] + rp[2] + ph_dc) / 3
                pd_ = (xp[1] + rp[1] + pd_dc) / 3
                pa  = (xp[0] + rp[0] + pa_dc) / 3

            s = ph + pd_ + pa
            resultado[(home, away, date_str)] = (ph / s, pd_ / s, pa / s)

        return resultado
