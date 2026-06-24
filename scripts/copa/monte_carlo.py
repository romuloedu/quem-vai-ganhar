"""
monte_carlo.py
==============
SimuladorMonteCarlo — simula a Copa do Mundo inteira N vezes usando Monte Carlo,
com pré-computação em batch de todos os pares das fases eliminatórias.
"""

import numpy as np
import pandas as pd

from copa.config import N_SIMS, SEED, BLEND_ALPHA
from copa.ensemble import ModeloEnsemble
from copa.features import ExtratordeFeaturas
from copa.repositorio import RepositorioDados

DATES = {
    "group":   "2026-06-20",
    "round32": "2026-06-29",
    "r16":     "2026-07-05",
    "qf":      "2026-07-11",
    "sf":      "2026-07-15",
    "final":   "2026-07-19",
}


class SimuladorMonteCarlo:
    """Executa simulações completas do torneio (fase de grupos + mata-mata)."""

    def __init__(
        self,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        repositorio: RepositorioDados,
    ) -> None:
        """Recebe as dependências para previsão e dados."""
        self.ensemble   = ensemble
        self.extrator   = extrator
        self.repo       = repositorio

    def simular(
        self,
        df_bl: pd.DataFrame,
        n_sims: int | None = None,
        salvar: bool = True,
    ) -> dict:
        """Roda `n_sims` simulações e retorna o dicionário de probabilidades por fase."""
        n = n_sims if n_sims is not None else N_SIMS
        print(f"🎲 Passo 6: Monte Carlo ({n:,} simulações, ensemble)...")
        if salvar:
            np.random.seed(SEED)

        df_teams = self.repo.ler_csv("wc2026_groups.csv")
        GROUP_TEAMS   = {g: list(sub["team"]) for g, sub in df_teams.groupby("group")}
        GROUP_MATCHES = {}
        for g, t in GROUP_TEAMS.items():
            t1, t2, t3, t4 = t
            GROUP_MATCHES[g] = [(t1, t2), (t3, t4), (t1, t3), (t2, t4), (t4, t1), (t2, t3)]

        # Cache de probabilidades dos jogos de grupo (do blend)
        prob_cache: dict = {}
        for _, r in df_bl.iterrows():
            prob_cache[(r["home_team"], r["away_team"])] = (
                r["p_home_win"], r["p_draw"], r["p_away_win"]
            )

        # Pré-computar todas as combinações possíveis de pares KO em batch
        all_teams = df_teams["team"].tolist()
        ko_dates  = [DATES["round32"], DATES["r16"], DATES["qf"], DATES["sf"], DATES["final"]]

        # Aquece cache de forma antes de montar os vetores KO
        self.extrator.historico.aquecer_cache(all_teams, ko_dates)

        ko_chaves: list[tuple[str, str, str]] = []
        ko_vetores: list[list] = []
        for date_str in ko_dates:
            for home in all_teams:
                for away in all_teams:
                    if home == away:
                        continue
                    fv = self.extrator.construir_vetor(home, away, date_str)
                    ko_chaves.append((home, away, date_str))
                    ko_vetores.append(fv)

        _ko = self.ensemble.prever_lote(ko_chaves, np.array(ko_vetores, dtype=np.float32))
        print(f"   ✅ {len(ko_chaves):,} pares KO pré-computados em batch", flush=True)

        def pred_ko(home: str, away: str, date: str) -> tuple[float, float, float]:
            return _ko.get((home, away, date), (1 / 3, 1 / 3, 1 / 3))

        def sim_m(home: str, away: str, date: str, ko: bool = False) -> str:
            key = (home, away)
            if key in prob_cache:
                pw, pd_, pa = prob_cache[key]
            elif (away, home) in prob_cache:
                pa, pd_, pw = prob_cache[(away, home)]
            else:
                pw, pd_, pa = pred_ko(home, away, date)
            r = np.random.random()
            if r < pw:
                return home
            elif r < pw + pd_:
                return home if (ko and np.random.random() < 0.5) else ("draw" if not ko else away)
            else:
                return away

        def sim_g(g: str) -> tuple[list, dict, dict]:
            teams = GROUP_TEAMS[g]
            pts = {t: 0 for t in teams}
            gd  = {t: 0 for t in teams}
            gfd = {t: 0 for t in teams}
            for h, a in GROUP_MATCHES[g]:
                key = (h, a)
                if key in prob_cache:
                    ph, pd_, pa = prob_cache[key]
                elif (a, h) in prob_cache:
                    pa, pd_, ph = prob_cache[(a, h)]
                else:
                    ph, pd_, pa = pred_ko(h, a, DATES["group"])
                r = np.random.random()
                if r < ph:
                    hg = int(np.random.poisson(1.8))
                    ag = max(0, hg - int(np.random.poisson(0.8) + 1))
                    if ag >= hg:
                        ag = hg - 1
                    pts[h] += 3
                elif r < ph + pd_:
                    hg = int(np.random.poisson(1.2))
                    ag = hg
                else:
                    ag = int(np.random.poisson(1.8))
                    hg = max(0, ag - int(np.random.poisson(0.8) + 1))
                    if hg >= ag:
                        hg = ag - 1
                    pts[a] += 3
                gd[h]  += hg - ag;  gd[a]  += ag - hg
                gfd[h] += hg;       gfd[a] += ag
            ranking = sorted(teams, key=lambda t: (pts[t], gd[t], gfd[t]), reverse=True)
            return ranking, pts, gd

        # Contadores de avanço
        ch    = {t: 0 for t in all_teams}
        fn    = {t: 0 for t in all_teams}
        sf    = {t: 0 for t in all_teams}
        qf    = {t: 0 for t in all_teams}
        r16   = {t: 0 for t in all_teams}
        r32   = {t: 0 for t in all_teams}
        ga    = {t: 0 for t in all_teams}
        clasico = {"round32": 0, "round16": 0, "quarter": 0, "semi": 0, "final": 0, "any": 0}
        BR, ARG = "Brasil", "Argentina"

        for _ in range(n):
            gr: dict = {}
            thirds: list = []
            for g in "ABCDEFGHIJKL":
                ranked, pts, gd_ = sim_g(g)
                gr[g] = ranked
                thirds.append((g, ranked[2], pts[ranked[2]], gd_[ranked[2]]))
                ga[ranked[0]] += 1
                ga[ranked[1]] += 1

            t8 = {x[1] for x in sorted(thirds, key=lambda x: (x[2], x[3]), reverse=True)[:8]}
            for t in t8:
                ga[t] += 1

            pairs = [
                (gr["A"][0], gr["B"][1]), (gr["B"][0], gr["A"][1]),
                (gr["C"][0], gr["D"][1]), (gr["D"][0], gr["C"][1]),
                (gr["E"][0], gr["F"][1]), (gr["F"][0], gr["E"][1]),
                (gr["G"][0], gr["H"][1]), (gr["H"][0], gr["G"][1]),
                (gr["I"][0], gr["J"][1]), (gr["J"][0], gr["I"][1]),
                (gr["K"][0], gr["L"][1]), (gr["L"][0], gr["K"][1]),
            ]
            tl = list(t8); np.random.shuffle(tl)
            rf_ = [gr[g][0] for g in "ACEGIK"]; np.random.shuffle(rf_)
            for i in range(min(4, len(tl), len(rf_))):
                pairs.append((rf_[i], tl[i]))
            et = [t for t in t8 if t not in [p[1] for p in pairs[-4:]]]
            ef = [gr[g][0] for g in "BDFHJL" if gr[g][0] not in [p[0] for p in pairs]]
            while len(pairs) < 16 and et and ef:
                pairs.append((ef.pop(), et.pop()))

            rw = []
            for h, a in pairs[:16]:
                w = sim_m(h, a, DATES["round32"], True)
                rw.append(w); r32[w] += 1
                if {h, a} == {BR, ARG}:
                    clasico["round32"] += 1; clasico["any"] += 1

            lw = []
            for i in range(0, 16, 2):
                if i + 1 < len(rw):
                    w = sim_m(rw[i], rw[i + 1], DATES["r16"], True)
                    lw.append(w); r16[w] += 1
                    if {rw[i], rw[i + 1]} == {BR, ARG}:
                        clasico["round16"] += 1; clasico["any"] += 1

            qw = []
            for i in range(0, len(lw), 2):
                if i + 1 < len(lw):
                    w = sim_m(lw[i], lw[i + 1], DATES["qf"], True)
                    qw.append(w); qf[w] += 1
                    if {lw[i], lw[i + 1]} == {BR, ARG}:
                        clasico["quarter"] += 1; clasico["any"] += 1

            sw = []
            for i in range(0, len(qw), 2):
                if i + 1 < len(qw):
                    w = sim_m(qw[i], qw[i + 1], DATES["sf"], True)
                    sw.append(w); sf[w] += 1; fn[w] += 1
                    if {qw[i], qw[i + 1]} == {BR, ARG}:
                        clasico["semi"] += 1; clasico["any"] += 1

            if len(sw) >= 2:
                c = sim_m(sw[0], sw[1], DATES["final"], True)
                ch[c] += 1
                if {sw[0], sw[1]} == {BR, ARG}:
                    clasico["final"] += 1; clasico["any"] += 1

        def pct(d: dict) -> dict:
            return {k: round(v / n * 100, 2) for k, v in d.items()}

        clasico_pct = {k: round(v / n * 100, 2) for k, v in clasico.items()}
        resultados = {
            "champion":       pct(ch),
            "final":          pct(fn),
            "semi":           pct(sf),
            "quarter":        pct(qf),
            "round16":        pct(r16),
            "round32":        pct(r32),
            "group_adv":      pct(ga),
            "brasil_argentina": clasico_pct,
            "n_sims":         n,
            "blend_alpha":    BLEND_ALPHA,
        }

        if salvar:
            self.repo.salvar_json("tournament_simulation.json", resultados)

        print("   ✅ Simulação concluída")
        return resultados
