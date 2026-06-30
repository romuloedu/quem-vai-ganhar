#!/usr/bin/env python3
"""
tunar_blend.py
══════════════
Varre o peso do blend (α = peso do mercado) usando os jogos de mata-mata já
disputados, com as probabilidades de modelo e mercado congeladas ANTES de cada
jogo (gravadas em dados/knockout_probs.json) e os resultados reais.

Para cada α, mistura  blend = α·mercado + (1-α)·modelo  e mede a qualidade da
previsão 3-vias (vitória / empate / derrota no tempo normal) contra o que
aconteceu — Brier score, log loss e acurácia. Aponta o α com menor Brier.

Uso:
    python scripts/tunar_blend.py
"""
import json
import math
from pathlib import Path

DADOS = Path(__file__).parent.parent / "dados"


def _outcome(r: dict) -> str:
    hs, as_ = int(r["home_score"]), int(r["away_score"])
    return "home" if hs > as_ else ("draw" if hs == as_ else "away")


def carregar_amostra() -> list[dict]:
    """Junta probs congeladas (modelo+mercado) com o resultado real de cada jogo."""
    snap  = json.loads((DADOS / "knockout_probs.json").read_text())
    reais = json.loads((DADOS / "resultados_reais.json").read_text())
    result = {(r["home_team"], r["away_team"]): _outcome(r) for r in reais}

    amostra = []
    for chave, s in snap.items():
        if not s.get("modelo") or not s.get("mercado"):
            continue  # jogo sem modelo+mercado separados (formato antigo)
        h, a = chave.split("|", 1)
        o = result.get((h, a))
        if o is None:
            continue  # ainda não disputado
        amostra.append({
            "jogo":    f"{h} x {a}",
            "modelo":  [v / 100 for v in s["modelo"]],   # [ph, pd, pa]
            "mercado": [v / 100 for v in s["mercado"]],
            "resultado": o,
        })
    return amostra


def avaliar(amostra: list[dict], alpha: float) -> dict:
    idx = {"home": 0, "draw": 1, "away": 2}
    n = acc = brier = ll = 0
    for g in amostra:
        mo, mk = g["modelo"], g["mercado"]
        p = [alpha * mk[i] + (1 - alpha) * mo[i] for i in range(3)]
        tot = sum(p); p = [x / tot for x in p]
        o = idx[g["resultado"]]
        if max(range(3), key=lambda i: p[i]) == o:
            acc += 1
        for i in range(3):
            y = 1.0 if i == o else 0.0
            brier += (p[i] - y) ** 2
            ll    -= y * math.log(max(p[i], 1e-9))
        n += 1
    return {"n": n, "acc": acc / n, "brier": brier / n, "ll": ll / n} if n else {"n": 0}


def main() -> None:
    amostra = carregar_amostra()
    if len(amostra) < 3:
        print(f"Amostra insuficiente: {len(amostra)} jogo(s) com modelo+mercado+resultado.")
        print("O log começa a acumular conforme o mata-mata avança — rode de novo mais tarde.")
        return

    print(f"Varredura do α (peso do mercado) em {len(amostra)} jogos de mata-mata\n")
    print(f"  {'α (mercado)':>12} {'Brier':>8} {'LogLoss':>9} {'Acurácia':>9}")
    melhor = None
    for k in range(0, 21):
        alpha = k / 20
        m = avaliar(amostra, alpha)
        marca = ""
        if melhor is None or m["brier"] < melhor[1]:
            melhor = (alpha, m["brier"]);
        print(f"  {alpha*100:>10.0f}% {m['brier']:>8.4f} {m['ll']:>9.4f} {m['acc']*100:>8.1f}%")
    print(f"\n★ Menor Brier em α = {melhor[0]*100:.0f}% de mercado (Brier {melhor[1]:.4f})")
    print("  (atual em produção: 65% mercado)")


if __name__ == "__main__":
    main()
