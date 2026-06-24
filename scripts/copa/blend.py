"""
blend.py
========
BlendadorProbabilidades — combina probabilidades do modelo com odds de mercado
para os jogos da fase de grupos.
"""

import pandas as pd
from copa.config import BLEND_ALPHA
from copa.ensemble import ModeloEnsemble
from copa.features import ExtratordeFeaturas
from copa.repositorio import RepositorioDados


class BlendadorProbabilidades:
    """Combina ensemble com odds de mercado usando peso BLEND_ALPHA."""

    def __init__(
        self,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        repositorio: RepositorioDados,
        blend_alpha: float = BLEND_ALPHA,
    ) -> None:
        """Recebe as dependências necessárias para calcular o blend."""
        self.ensemble    = ensemble
        self.extrator    = extrator
        self.repo        = repositorio
        self.blend_alpha = blend_alpha

    def blender(self, market_probs: dict) -> pd.DataFrame:
        """Calcula probabilidades blendadas para todos os jogos da fase de grupos.

        Salva o resultado em all_group_match_probs_blended.csv e o retorna.
        """
        df_matches = self.repo.ler_csv("wc2026_matches.csv")
        rows = []

        for _, m in df_matches[df_matches["stage"] == "group"].iterrows():
            fv = self.extrator.construir_vetor(
                m["home_team"], m["away_team"], m["date"]
            )
            ph_e, pd_e, pa_e = self.ensemble.prever(m["home_team"], m["away_team"], fv)
            mp = {"home_win": ph_e, "draw": pd_e, "away_win": pa_e}

            key  = (m["home_team"], m["away_team"])
            keyI = (m["away_team"], m["home_team"])

            if key in market_probs:
                mk = market_probs[key]
                vals = [mk["p_home"], mk["p_draw"], mk["p_away"]]
                fp = {
                    k: self.blend_alpha * vals[i] + (1 - self.blend_alpha) * list(mp.values())[i]
                    for i, k in enumerate(mp)
                }
                src = "blend"
            elif keyI in market_probs:
                mk  = market_probs[keyI]
                mkA = {"p_home": mk["p_away"], "p_draw": mk["p_draw"], "p_away": mk["p_home"]}
                vals = [mkA["p_home"], mkA["p_draw"], mkA["p_away"]]
                fp = {
                    k: self.blend_alpha * vals[i] + (1 - self.blend_alpha) * list(mp.values())[i]
                    for i, k in enumerate(mp)
                }
                src = "blend"
            else:
                fp  = mp
                src = "model_only"

            tot = sum(fp.values())
            fp  = {k: round(v / tot, 4) for k, v in fp.items()}
            rows.append({
                **m.to_dict(),
                "p_home_win":       fp["home_win"],
                "p_draw":           fp["draw"],
                "p_away_win":       fp["away_win"],
                "p_home_win_model": round(mp["home_win"], 4),
                "source":           src,
                "blend_alpha":      self.blend_alpha if src == "blend" else 0,
            })

        df_bl = pd.DataFrame(rows)
        self.repo.salvar_csv("all_group_match_probs_blended.csv", df_bl)

        blend_n = (df_bl["source"] == "blend").sum()
        print(f"   ✅ {blend_n} blendados | {len(df_bl) - blend_n} só modelo")
        return df_bl
