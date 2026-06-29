"""
pipeline.py
===========
PipelineAtualizacao — orquestra todos os passos da atualização pós-rodada:
congelamento, calibração, retreinamento, blend, Monte Carlo e HTML.
"""

import random
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from copa.config import DADOS, SEED, CONF_STRENGTH
from copa.repositorio import RepositorioDados
from copa.historico import HistoricoPartidas
from copa.limiar_empate import CalibradorLimiarEmpate, PrevisorResultado
from copa.features import ExtratordeFeaturas
from copa.dixon_coles import ModeloDixonColes
from copa.logit_ordenado import ModeloLogitOrdenado
from copa.ensemble import ModeloEnsemble
from copa.odds import ClienteOdds, ParseadorOdds
from copa.blend import BlendadorProbabilidades
from copa.monte_carlo import SimuladorMonteCarlo
from copa.mata_mata import ConstrutorMataMata
from copa.html import AtualizadorHTML


class PipelineAtualizacao:
    """Executa a sequência completa de atualização da Copa 2026."""

    def __init__(self) -> None:
        """Inicializa com o repositório apontando para o diretório de dados."""
        self.repo = RepositorioDados(DADOS)

    # ── Passo 0 ─────────────────────────────────────────────

    def step0_freeze_probs(self, previsor: PrevisorResultado) -> None:
        """Congela probabilidades pré-jogo ANTES de retreinar o modelo."""
        if not self.repo.existe("all_group_match_probs_blended.csv") or \
           not self.repo.existe("resultados_reais.json"):
            return

        real_results   = self.repo.ler_json("resultados_reais.json", [])
        finished_keys  = {(r["home_team"], r["away_team"]) for r in real_results}
        frozen: dict   = self.repo.ler_json("frozen_probs.json", {})

        import pandas as pd
        df = self.repo.ler_csv("all_group_match_probs_blended.csv")
        adicionados = 0
        for _, row in df.iterrows():
            h, a = row["home_team"], row["away_team"]
            fkey = f"{h}|{a}"
            if (h, a) in finished_keys and fkey not in frozen:
                ph  = round(float(row["p_home_win"]) * 100, 2)
                pd_ = round(float(row["p_draw"])     * 100, 2)
                pa  = round(float(row["p_away_win"]) * 100, 2)
                pp  = previsor.placar_previsto(
                    float(row["p_home_win"]), float(row["p_draw"]), float(row["p_away_win"])
                )
                frozen[fkey] = {"ph": ph, "pd": pd_, "pa": pa, "placar_prev": pp}
                adicionados += 1

        if adicionados:
            self.repo.salvar_json("frozen_probs.json", frozen)
            print(f"🧊 Passo 0: {adicionados} jogo(s) com probabilidades pré-jogo congeladas")
        else:
            print("ℹ️  Passo 0: nenhum jogo novo para congelar")

    # ── Calibração do limiar ─────────────────────────────────

    def _calibrar_limiar(self) -> PrevisorResultado:
        """Calibra o limiar de empate e persiste em draw_threshold.json."""
        print("📐 Calibrando limiar de empate...")
        frozen = self.repo.ler_json("frozen_probs.json", {})
        reais  = self.repo.ler_json("resultados_reais.json", [])
        k = CalibradorLimiarEmpate().calibrar(frozen, reais)
        self.repo.salvar_json(
            "draw_threshold.json",
            {"k": k, "n_games": len(reais)},
        )
        return PrevisorResultado(k)

    # ── Passo 1 ─────────────────────────────────────────────

    def step1_update_history(self) -> None:
        """Incorpora os resultados reais ao histórico de partidas."""
        if not self.repo.existe("resultados_reais.json"):
            print("ℹ️  dados/resultados_reais.json não encontrado — pulando atualização do histórico")
            return

        new_results = self.repo.ler_json("resultados_reais.json", [])
        if not new_results:
            print("ℹ️  resultados_reais.json está vazio — nada a incorporar")
            return

        import pandas as pd
        df     = self.repo.ler_csv("historical_wc_teams.csv", parse_dates=["date"])
        adicionados = 0

        for r in new_results:
            existe = (
                (df["home_team"] == r["home_team"]) &
                (df["away_team"] == r["away_team"]) &
                (df["date"]      == r["date"])
            ).any()
            if existe:
                continue
            new_row = {
                "date":       pd.Timestamp(r["date"]),
                "home_team":  r["home_team"],
                "away_team":  r["away_team"],
                "home_score": r["home_score"],
                "away_score": r["away_score"],
                "tournament": r.get("tournament", "FIFA World Cup"),
                "city":       r.get("city", ""),
                "country":    r.get("country", "USA"),
                "neutral":    True,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            adicionados += 1

        if adicionados:
            df = df.sort_values("date").reset_index(drop=True)
            self.repo.salvar_csv("historical_wc_teams.csv", df)
            print(f"✅ Passo 1: {adicionados} resultado(s) adicionado(s) ao histórico")
        else:
            print("ℹ️  Passo 1: resultados já estavam no histórico")

    # ── Passo 2 ─────────────────────────────────────────────

    def step2_retrain(self) -> tuple[ModeloEnsemble, ExtratordeFeaturas]:
        """Retreina XGBoost, RF, Dixon-Coles e Logit ordenado; persiste artefatos."""
        print("🔧 Passo 2: Retreinando modelo...")
        from sklearn.model_selection import StratifiedKFold
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.ensemble import RandomForestClassifier
        import xgboost as xgb
        import numpy as np

        df_hist  = self.repo.ler_csv("historical_wc_teams.csv", parse_dates=["date"])
        df_teams = self.repo.ler_csv("wc2026_groups.csv")
        df_static = self.repo.ler_csv("wc2026_team_static.csv")

        df_hist  = df_hist.dropna(subset=["home_score", "away_score"]).copy()
        df_hist["home_score"] = df_hist["home_score"].astype(int)
        df_hist["away_score"] = df_hist["away_score"].astype(int)

        rank_map        = dict(zip(df_teams["team"], df_teams["fifa_rank"]))
        elo_map         = dict(zip(df_teams["team"], df_teams["elo_approx"]))
        conf_map        = {r["team"]: CONF_STRENGTH.get(r["confederation"], 3) for _, r in df_teams.iterrows()}
        squad_value_map = {t: float(np.log1p(v)) for t, v in zip(df_static["team"], df_static["squad_value_m"])}
        wc_apps_map     = dict(zip(df_static["team"], df_static["wc_appearances"]))
        squad_age_map   = dict(zip(df_static["team"], df_static["squad_avg_age"]))

        log      = HistoricoPartidas.build_log(df_hist)
        historico = HistoricoPartidas(log)
        extrator  = ExtratordeFeaturas(
            historico, rank_map, elo_map, conf_map,
            squad_value_map, wc_apps_map, squad_age_map,
        )

        wc_teams = set(df_teams["team"])
        df_src   = df_hist[
            df_hist["home_team"].isin(wc_teams) &
            df_hist["away_team"].isin(wc_teams) &
            (df_hist["date"] >= "2018-01-01")
        ].sort_values("date").reset_index(drop=True)

        X_rows, y_rows = [], []
        for _, r in df_src.iterrows():
            fv = extrator.construir_vetor(r["home_team"], r["away_team"], r["date"],
                                          neutral=int(r["neutral"]))
            X_rows.append(fv)
            hg, ag = r["home_score"], r["away_score"]
            y_rows.append(2 if hg > ag else (1 if hg == ag else 0))

        X = np.array(X_rows, dtype=np.float32)
        y = np.array(y_rows)

        cv2 = StratifiedKFold(n_splits=2, shuffle=True, random_state=SEED)

        xgb_model = CalibratedClassifierCV(
            xgb.XGBClassifier(
                objective="multi:softprob", num_class=3, n_estimators=400,
                learning_rate=0.04, max_depth=4, subsample=0.8, colsample_bytree=0.75,
                min_child_weight=3, gamma=0.1, use_label_encoder=False,
                eval_metric="mlogloss", random_state=SEED, verbosity=0,
                nthread=1, tree_method="hist",
            ),
            method="isotonic", cv=cv2,
        )
        xgb_model.fit(X, y)

        rf_model = CalibratedClassifierCV(
            RandomForestClassifier(
                n_estimators=100, max_depth=8, min_samples_leaf=3,
                max_features="sqrt", random_state=SEED, n_jobs=1,
            ),
            method="isotonic", cv=cv2,
        )
        rf_model.fit(X, y)

        print("   🌲 Dixon-Coles treinando...")
        dc = ModeloDixonColes()
        dc.treinar(df_hist, wc_teams)

        ordinal = ModeloLogitOrdenado(seed=SEED)
        ordinal.treinar(X, y)

        # Persistir artefatos
        self.repo.salvar_pickle("model_calibrated.pkl", xgb_model)
        self.repo.salvar_pickle("rf_model.pkl", rf_model)
        self.repo.salvar_pickle("dc_params.pkl", (dc.attack_map, dc.defense_map, dc.rho))
        self.repo.salvar_pickle("feat_cols_v2.pkl", extrator.feat_cols)
        self.repo.salvar_pickle("ordinal_model.pkl", ordinal.serializar())
        log.to_pickle(DADOS / "_log_cache.pkl")

        ensemble = ModeloEnsemble(xgb_model, rf_model, dc, ordinal)

        print(f"   ✅ Ensemble treinado ({len(X)} jogos): XGBoost + RF + Dixon-Coles + Logit ordenado (ρ={dc.rho:.3f})")
        return ensemble, extrator

    # ── Passo 2b ────────────────────────────────────────────

    def step2b_retrofreeze(
        self,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        previsor: PrevisorResultado,
    ) -> None:
        """Recomputa probs ensemble para jogos já realizados e atualiza frozen_probs.json."""
        if not self.repo.existe("resultados_reais.json") or not self.repo.existe("wc2026_matches.csv"):
            print("ℹ️  Passo 2b: sem jogos realizados para retrocongelar")
            return

        real_results  = self.repo.ler_json("resultados_reais.json", [])
        finished_keys = {(r["home_team"], r["away_team"]) for r in real_results}

        if not finished_keys:
            print("ℹ️  Passo 2b: nenhum jogo realizado ainda")
            return

        frozen: dict   = self.repo.ler_json("frozen_probs.json", {})
        df_matches = self.repo.ler_csv("wc2026_matches.csv")
        atualizado = 0

        for _, m in df_matches[df_matches["stage"] == "group"].iterrows():
            h, a = m["home_team"], m["away_team"]
            if (h, a) not in finished_keys:
                continue
            fkey = f"{h}|{a}"
            fv   = extrator.construir_vetor(h, a, m["date"])
            ph, pd_, pa = ensemble.prever(h, a, fv)
            pp = previsor.placar_previsto(ph, pd_, pa)
            frozen[fkey] = {
                "ph":          round(ph  * 100, 2),
                "pd":          round(pd_ * 100, 2),
                "pa":          round(pa  * 100, 2),
                "placar_prev": pp,
            }
            atualizado += 1

        self.repo.salvar_json("frozen_probs.json", frozen)
        print(f"🔄 Passo 2b: {atualizado} jogo(s) passado(s) retrocongelados com ensemble")

    # ── Passos 3 e 4 ────────────────────────────────────────

    def step3_fetch_odds(self) -> tuple:
        """Busca odds de mercado via API (se ODDS_API_KEY estiver definida)."""
        from copa.config import ODDS_KEY
        if not ODDS_KEY:
            print("ℹ️  Passo 3: ODDS_API_KEY não definida — pulando busca de odds")
            return None, None
        print("🌐 Passo 3: Buscando odds de mercado...")
        client = ClienteOdds()
        games_data, outrights_raw = client.buscar()
        if games_data:
            self.repo.salvar_json("odds_raw_games.json", games_data)
        if outrights_raw:
            self.repo.salvar_json("odds_raw_winner.json", outrights_raw)
        return games_data, outrights_raw

    def step4_parse_odds(self, games_data, outrights_raw) -> tuple:
        """Parseia as odds brutas e retorna (market_probs, mkt_champion)."""
        parser = ParseadorOdds(self.repo)
        return parser.parsear(games_data, outrights_raw)

    # ── Passo 5 ─────────────────────────────────────────────

    def step5_blend(
        self,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        market_probs: dict,
    ):
        """Calcula probabilidades blendadas (modelo + mercado) para a fase de grupos."""
        print("🔀 Passo 5: Calculando probabilidades blendadas (ensemble)...")
        blendador = BlendadorProbabilidades(ensemble, extrator, self.repo)
        return blendador.blender(market_probs)

    # ── Passo 6 ─────────────────────────────────────────────

    def step6_monte_carlo(
        self,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        df_bl,
    ) -> dict:
        """Executa a simulação Monte Carlo do torneio completo."""
        simulador = SimuladorMonteCarlo(ensemble, extrator, self.repo)
        return simulador.simular(df_bl)

    # ── Passo 6b ────────────────────────────────────────────

    def step6b_mata_mata(
        self,
        ensemble: ModeloEnsemble,
        extrator: ExtratordeFeaturas,
        previsor: PrevisorResultado,
        market_probs: dict,
    ) -> None:
        """Monta os jogos do mata-mata (probabilidades blendadas + chance de avanço)."""
        from copa.config import BANDEIRAS
        print("🏆 Passo 6b: Montando jogos do mata-mata...")
        construtor = ConstrutorMataMata(self.repo, ensemble, extrator, previsor)
        jogos = construtor.construir(BANDEIRAS, market_probs)
        self.repo.salvar_json("knockout_games.json", jogos)
        print(f"   ✅ {len(jogos)} confronto(s) de mata-mata definido(s)")

    # ── Passo 7 ─────────────────────────────────────────────

    def step7_update_html(
        self, results: dict, df_bl, mkt_champion: dict, previsor: PrevisorResultado
    ) -> None:
        """Atualiza index.html e resultados.html com os novos dados."""
        atualizador = AtualizadorHTML(self.repo, previsor)
        atualizador.atualizar_index(results, df_bl, mkt_champion)

    # ── Ponto de entrada ────────────────────────────────────

    def executar(self) -> None:
        """Executa o pipeline completo de atualização pós-rodada."""
        random.seed(SEED)
        np.random.seed(SEED)
        print("\n🚀 ATUALIZAÇÃO COPA 2026\n")

        # Passo 0: precisa de um PrevisorResultado com k fallback para congelar
        previsor_fallback = PrevisorResultado(k=0.75)
        self.step0_freeze_probs(previsor_fallback)

        previsor = self._calibrar_limiar()

        self.step1_update_history()

        ensemble, extrator = self.step2_retrain()
        self.step2b_retrofreeze(ensemble, extrator, previsor)

        games_data, outrights_raw = self.step3_fetch_odds()
        market_probs, mkt_champion = self.step4_parse_odds(games_data, outrights_raw)

        df_bl = self.step5_blend(ensemble, extrator, market_probs)

        results = self.step6_monte_carlo(ensemble, extrator, df_bl)

        self.step6b_mata_mata(ensemble, extrator, previsor, market_probs)

        self.step7_update_html(results, df_bl, mkt_champion, previsor)

        print("\n✅ Pronto! Faça git add . && git commit -m 'Atualiza rodada' && git push\n")
