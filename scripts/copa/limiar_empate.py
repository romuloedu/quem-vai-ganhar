"""
limiar_empate.py
================
CalibradorLimiarEmpate — encontra o limiar k ótimo nos jogos já disputados.
PrevisorResultado — prevê o resultado (home/draw/away) usando o limiar calibrado.
"""

import numpy as np
from copa.poisson import PrevisorPoisson


class CalibradorLimiarEmpate:
    """Calibra o limiar k que maximiza a acurácia de previsão de empates."""

    def calibrar(self, frozen: dict, reais: list,
                 fallback: float = 0.75, min_jogos: int = 10) -> float:
        """Varre k ∈ [0.30, 1.00] e retorna o que maximiza acurácia nos jogos da Copa.

        Usa `fallback` se houver menos de `min_jogos` com resultado disponível.
        """
        result_map = {}
        for r in reais:
            key = f"{r['home_team']}|{r['away_team']}"
            hs, as_ = r["home_score"], r["away_score"]
            result_map[key] = "home" if hs > as_ else ("away" if as_ > hs else "draw")

        jogos = [
            {"ph": v["ph"] / 100, "pd": v["pd"] / 100, "pa": v["pa"] / 100,
             "res": result_map[k]}
            for k, v in frozen.items() if k in result_map
        ]

        if len(jogos) < min_jogos:
            print(f"   ⚠️  Apenas {len(jogos)} jogo(s) com resultado — usando k={fallback} (fallback)")
            return fallback

        best_k, best_acc = fallback, -1.0
        for k in np.arange(0.30, 1.01, 0.05):
            corretos = sum(
                1 for g in jogos
                if (
                    ("draw" if g["pd"] >= k * max(g["ph"], g["pa"])
                     else ("home" if g["ph"] >= g["pa"] else "away"))
                    == g["res"]
                )
            )
            acc = corretos / len(jogos)
            if acc > best_acc:
                best_acc, best_k = acc, round(float(k), 2)

        taxa_empate = sum(1 for g in jogos if g["res"] == "draw") / len(jogos)
        print(
            f"   📐 k={best_k:.2f} (acc={best_acc * 100:.1f}%, "
            f"{len(jogos)} jogos, {taxa_empate * 100:.1f}% empates na Copa)"
        )
        return best_k


class PrevisorResultado:
    """Prevê o resultado de uma partida usando o limiar k calibrado."""

    def __init__(self, k: float) -> None:
        """Recebe o limiar k calibrado por CalibradorLimiarEmpate."""
        self.k = k
        self._poisson = PrevisorPoisson()

    def prever(self, ph: float, pd: float, pa: float) -> str:
        """Retorna 'home', 'draw' ou 'away' com base nas probabilidades e no limiar k."""
        if pd >= self.k * max(ph, pa):
            return "draw"
        return "home" if ph >= pa else "away"

    def placar_previsto(self, ph: float, pd: float, pa: float) -> str:
        """Retorna o placar mais provável consistente com o resultado previsto."""
        resultado = self.prever(ph, pd, pa)
        return self._poisson.calibrar(ph, pd, pa, resultado)
