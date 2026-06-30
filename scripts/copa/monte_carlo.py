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

    def _simular_pos_grupos(
        self,
        ko_fix: dict,
        ko_order: list,
        expect: dict,
        sim_m,
        all_teams: list,
        n: int,
    ) -> dict:
        """Simula só o mata-mata, partindo dos confrontos reais e fixando resultados.

        • Times eliminados (fora das oitavas) ficam com probabilidade zero.
        • Cada rodada já decidida usa o vencedor real; o que falta é simulado.
        • Quando a próxima rodada já está definida na agenda, usamos os confrontos
          reais; senão, emparelhamos os vencedores na ordem do chaveamento.
        """
        reais = self.repo.ler_json("resultados_reais.json", [])
        real_adv: dict = {}
        for r in reais:
            if not r.get("stage"):
                continue  # só jogos de mata-mata
            h, a = r["home_team"], r["away_team"]
            w = r.get("winner")
            if w == "home":
                real_adv[(h, a)] = h
            elif w == "away":
                real_adv[(h, a)] = a
            else:
                try:
                    hs, as_ = int(r["home_score"]), int(r["away_score"])
                    if hs != as_:
                        real_adv[(h, a)] = h if hs > as_ else a
                except (TypeError, ValueError):
                    pass

        def winner_real(h, a):
            return real_adv.get((h, a)) or real_adv.get((a, h))

        date_of = {
            "LAST_32": DATES["round32"], "LAST_16": DATES["r16"],
            "QUARTER_FINALS": DATES["qf"], "SEMI_FINALS": DATES["sf"],
            "FINAL": DATES["final"],
        }
        ch  = {t: 0 for t in all_teams}
        fn  = {t: 0 for t in all_teams}
        sf  = {t: 0 for t in all_teams}
        qf  = {t: 0 for t in all_teams}
        r16 = {t: 0 for t in all_teams}
        r32 = {t: 0 for t in all_teams}
        ga  = {t: 0 for t in all_teams}
        win = {"LAST_32": r32, "LAST_16": r16, "QUARTER_FINALS": qf,
               "SEMI_FINALS": sf, "FINAL": ch}

        # Times vivos = os 32 das oitavas; todos já saíram da fase de grupos (100%)
        alive = set()
        for m in ko_fix["LAST_32"]:
            alive.add(m["home_team"]); alive.add(m["away_team"])
        for t in alive:
            ga[t] = n

        BR, ARG = "Brasil", "Argentina"
        clasico = {"round32": 0, "round16": 0, "quarter": 0, "semi": 0, "final": 0, "any": 0}
        cl_key  = {"LAST_32": "round32", "LAST_16": "round16", "QUARTER_FINALS": "quarter",
                   "SEMI_FINALS": "semi", "FINAL": "final"}

        for _ in range(n):
            current = [(m["home_team"], m["away_team"]) for m in ko_fix["LAST_32"]]
            for idx, stage in enumerate(ko_order):
                winners = []
                for h, a in current:
                    w = winner_real(h, a) or sim_m(h, a, date_of[stage], True)
                    win[stage][w] += 1
                    if stage == "SEMI_FINALS":
                        fn[w] += 1  # vencer a semi = chegar à final
                    if {h, a} == {BR, ARG}:
                        clasico[cl_key[stage]] += 1; clasico["any"] += 1
                    winners.append(w)
                if stage == "FINAL":
                    break
                nxt = ko_order[idx + 1]
                if len(ko_fix[nxt]) == expect[nxt]:
                    current = [(m["home_team"], m["away_team"]) for m in ko_fix[nxt]]
                else:
                    current = [(winners[i], winners[i + 1])
                               for i in range(0, len(winners) - 1, 2)]

        def pct(d: dict) -> dict:
            return {k: round(v / n * 100, 2) for k, v in d.items()}

        return {
            "champion":         pct(ch),
            "final":            pct(fn),
            "semi":             pct(sf),
            "quarter":          pct(qf),
            "round16":          pct(r16),
            "round32":          pct(r32),
            "group_adv":        pct(ga),
            "brasil_argentina": {k: round(v / n * 100, 2) for k, v in clasico.items()},
            "n_sims":           n,
            "blend_alpha":      BLEND_ALPHA,
        }

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

        # ── Mata-mata em andamento: condiciona ao chaveamento e resultados reais ──
        # Se as oitavas (LAST_32) já estão definidas, a fase de grupos acabou: em vez
        # de re-sortear os grupos (o que ressuscitaria times eliminados), partimos dos
        # 16 confrontos reais e fixamos os resultados que já aconteceram.
        agenda_all = self.repo.ler_json("agenda.json", [])
        KO_ORDER = ["LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]
        EXPECT   = {"LAST_32": 16, "LAST_16": 8, "QUARTER_FINALS": 4, "SEMI_FINALS": 2, "FINAL": 1}

        def _fix(stage: str) -> list:
            ms = [m for m in agenda_all
                  if m.get("stage") == stage and m.get("home_team") and m.get("away_team")]
            return sorted(ms, key=lambda m: (m.get("id") or 0, m.get("utc") or ""))

        ko_fix = {st: _fix(st) for st in KO_ORDER}
        if ko_fix["LAST_32"]:
            resultados = self._simular_pos_grupos(ko_fix, KO_ORDER, EXPECT, sim_m, all_teams, n)
            if salvar:
                self.repo.salvar_json("tournament_simulation.json", resultados)
            print("   ✅ Simulação condicionada ao chaveamento real concluída")
            return resultados

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
