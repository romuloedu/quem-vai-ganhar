#!/usr/bin/env python3
"""
atualizar.py
════════════
Script principal de atualização. Rode após cada rodada da Copa.

Uso:
    # Após instalar dependências (só na primeira vez):
    pip install -r requirements.txt

    # A cada rodada:
    python scripts/atualizar.py

    # Com odds de mercado (recomendado):
    ODDS_API_KEY=sua_chave python scripts/atualizar.py

O script faz tudo em sequência:
    1. Lê os resultados que você adicionou em dados/resultados_reais.json
    2. Atualiza o histórico (historical_wc_teams.csv)
    3. Retreina o modelo com os novos dados
    4. Busca odds atualizadas da API (se tiver chave)
    5. Aplica blend modelo + mercado
    6. Roda Monte Carlo (60k simulações)
    7. Atualiza o index.html com os novos números
    8. Imprime o que mudou

Após rodar:
    git add .
    git commit -m "Atualiza após rodada X"
    git push

O GitHub Pages atualiza automaticamente em ~1 minuto.
"""

import os, sys, json, re, pickle, subprocess, warnings, datetime, math
from pathlib import Path
import pandas as pd
import numpy as np
import requests

# ─────────────────────────────────────────────────────────
# Previsão de placar via Poisson calibrado às probabilidades W/D/L
# ─────────────────────────────────────────────────────────
_POISSON_CACHE: dict = {}

def _calibrate_poisson(ph: float, pd: float, pa: float, _max: int = 7) -> str:
    """Retorna o placar mais provável consistente com o resultado previsto.
    Calibra Poisson independentes às probabilidades W/D/L, depois busca o placar
    mais provável dentro da categoria vencedora (home/draw/away)."""
    if _max not in _POISSON_CACHE:
        lam = np.arange(0.05, 5.01, 0.05)
        g   = np.arange(_max, dtype=float)
        fac = np.array([math.factorial(int(k)) for k in g])
        pmf = np.exp(-lam[:, None]) * (lam[:, None] ** g) / fac  # (100, max_g)
        H, A = np.meshgrid(np.arange(_max), np.arange(_max), indexing='ij')
        _pw  = (pmf @ (H > A).astype(float)) @ pmf.T
        _pd_ = (pmf @ (H == A).astype(float)) @ pmf.T
        _pa_ = (pmf @ (H < A).astype(float)) @ pmf.T
        _POISSON_CACHE[_max] = (lam, pmf, _pw, _pd_, _pa_, H, A)
    lam, pmf, _pw, _pd_, _pa_, H, A = _POISSON_CACHE[_max]
    loss = (_pw - ph)**2 + (_pd_ - pd)**2 + (_pa_ - pa)**2
    i, j = divmod(int(np.argmin(loss)), len(lam))
    joint = pmf[i, :, None] * pmf[j, None, :]  # (max_g, max_g)
    # Restringir ao resultado previsto para evitar contradições
    if ph >= pd and ph >= pa:
        mask = H > A      # vitória do mandante
    elif pa > ph and pa >= pd:
        mask = H < A      # vitória do visitante
    else:
        mask = H == A     # empate
    bh, ba = divmod(int(np.argmax(np.where(mask, joint, 0))), _max)
    return f"{bh}-{ba}"

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
DADOS       = ROOT / "dados"
ODDS_KEY    = os.getenv("ODDS_API_KEY", "")
BLEND_ALPHA = 0.65   # peso do mercado (0 = só modelo, 1 = só mercado)
N_SIMS      = 100_000  # simulações Monte Carlo

NAME_MAP = {
    "Brazil":"Brasil","Morocco":"Marrocos","Scotland":"Escócia","Haiti":"Haiti",
    "France":"França","Spain":"Espanha","Belgium":"Bélgica","Netherlands":"Holanda",
    "Argentina":"Argentina","Portugal":"Portugal","Mexico":"México","Norway":"Noruega",
    "Croatia":"Croácia","Germany":"Alemanha","England":"Inglaterra","Colombia":"Colômbia",
    "Switzerland":"Suíça","Ecuador":"Equador","South Korea":"Coreia do Sul","Japan":"Japão",
    "Iran":"Irã","Senegal":"Senegal","Tunisia":"Tunísia","Italy":"Itália",
    "Austria":"Áustria","Egypt":"Egito","Czech Republic":"República Tcheca",
    "United States":"Estados Unidos","USA":"Estados Unidos","Uruguay":"Uruguai",
    "Canada":"Canadá","Turkey":"Turquia","Ukraine":"Ucrânia","Australia":"Austrália",
    "Qatar":"Catar","DR Congo":"RD Congo","New Zealand":"Nova Zelândia","Algeria":"Argélia",
    "South Africa":"África do Sul","Paraguay":"Paraguai","Saudi Arabia":"Arábia Saudita",
    "Ivory Coast":"Costa do Marfim","Curaçao":"Curaçao","Uzbekistan":"Uzbequistão",
    "Cape Verde":"Cabo Verde","Panama":"Panamá","Ghana":"Gana","Iraq":"Iraque",
    "Jordan":"Jordânia","Bosnia and Herzegovina":"Bósnia e Herzegovina","Sweden":"Suécia",
}


# ─────────────────────────────────────────────────────────
# PASSO 1 — Incorporar resultados reais ao histórico
# ─────────────────────────────────────────────────────────
def step1_update_history():
    results_path = DADOS / "resultados_reais.json"
    if not results_path.exists():
        print("ℹ️  dados/resultados_reais.json não encontrado — pulando atualização do histórico")
        return

    with open(results_path) as f:
        new_results = json.load(f)

    if not new_results:
        print("ℹ️  resultados_reais.json está vazio — nada a incorporar")
        return

    df = pd.read_csv(DADOS / "historical_wc_teams.csv", parse_dates=["date"])
    added = 0

    for r in new_results:
        # Evitar duplicatas
        exists = ((df["home_team"] == r["home_team"]) &
                  (df["away_team"] == r["away_team"]) &
                  (df["date"]      == r["date"])).any()
        if exists:
            continue

        new_row = {
            "date":       r["date"],
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
        added += 1

    if added:
        df = df.sort_values("date").reset_index(drop=True)
        df.to_csv(DADOS / "historical_wc_teams.csv", index=False)
        print(f"✅ Passo 1: {added} resultado(s) adicionado(s) ao histórico")
    else:
        print("ℹ️  Passo 1: resultados já estavam no histórico")


# ─────────────────────────────────────────────────────────
# PASSO 2 — Retreinar modelo
# ─────────────────────────────────────────────────────────
def step2_retrain():
    print("🔧 Passo 2: Retreinando modelo...")
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import log_loss
    import xgboost as xgb

    df_hist  = pd.read_csv(DADOS / "historical_wc_teams.csv", parse_dates=["date"])
    df_teams = pd.read_csv(DADOS / "wc2026_groups.csv")

    df_hist  = df_hist.dropna(subset=["home_score","away_score"]).copy()
    df_hist["home_score"] = df_hist["home_score"].astype(int)
    df_hist["away_score"] = df_hist["away_score"].astype(int)

    rank_map = dict(zip(df_teams["team"], df_teams["fifa_rank"]))
    elo_map  = dict(zip(df_teams["team"], df_teams["elo_approx"]))

    def build_log(df):
        rows = []
        for _, r in df.iterrows():
            for side in ["home","away"]:
                t  = r["home_team"] if side=="home" else r["away_team"]
                o  = r["away_team"] if side=="home" else r["home_team"]
                gf = int(r["home_score"] if side=="home" else r["away_score"])
                ga = int(r["away_score"] if side=="home" else r["home_score"])
                res = "W" if gf>ga else ("D" if gf==ga else "L")
                rows.append({"date":r["date"],"team":t,"opponent":o,
                             "goals_for":gf,"goals_against":ga,"result":res,
                             "neutral":r["neutral"]})
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    log = build_log(df_hist)

    def rolling_feats(log, team, before, N=10):
        past = log[(log["team"]==team) & (log["date"]<before)].tail(N)
        if len(past)==0: return None
        n=len(past); w=(past["result"]=="W").sum(); d=(past["result"]=="D").sum()
        wts=np.exp(np.linspace(-1,0,n)); wts/=wts.sum()
        gf=past["goals_for"].values; ga=past["goals_against"].values
        return {"win_rate":w/n,"draw_rate":d/n,
                "goals_scored_avg":np.average(gf,weights=wts),
                "goals_conceded_avg":np.average(ga,weights=wts),
                "clean_sheets_rate":(ga==0).sum()/n,
                "goal_diff_avg":np.average(gf-ga,weights=wts),
                "form_pts":(w*3+d)/(n*3),"games_played":n}

    def h2h_feats(log, a, b, before, wy=5):
        cut=pd.Timestamp(before)-pd.DateOffset(years=wy)
        h=log[(log["team"]==a)&(log["opponent"]==b)&
              (log["date"]>=cut)&(log["date"]<before)]
        if len(h)==0: return {"h2h_win_rate":0.5,"h2h_goal_diff":0.0,"h2h_games":0}
        return {"h2h_win_rate":(h["result"]=="W").sum()/len(h),
                "h2h_goal_diff":(h["goals_for"]-h["goals_against"]).mean(),
                "h2h_games":len(h)}

    def elo_exp(ea,eb): return 1/(1+10**((eb-ea)/400))

    FEAT_COLS = [
        "h_win_rate","h_draw_rate","h_goals_scored_avg","h_goals_conceded_avg",
        "h_clean_sheets_rate","h_goal_diff_avg","h_form_pts","h_fifa_rank","h_elo",
        "h_elo_expected","a_win_rate","a_draw_rate","a_goals_scored_avg",
        "a_goals_conceded_avg","a_clean_sheets_rate","a_goal_diff_avg","a_form_pts",
        "a_fifa_rank","a_elo","rank_diff","elo_diff","elo_expected_home",
        "h2h_win_rate","h2h_goal_diff","h2h_games","neutral",
    ]

    wc_teams = set(df_teams["team"])
    df_src = df_hist[
        df_hist["home_team"].isin(wc_teams) &
        df_hist["away_team"].isin(wc_teams) &
        (df_hist["date"] >= "2018-01-01")
    ].sort_values("date").reset_index(drop=True)

    X_rows, y_rows = [], []
    for _, r in df_src.iterrows():
        fh = rolling_feats(log, r["home_team"], r["date"]) or {
            "win_rate":0.5,"draw_rate":0.25,"goals_scored_avg":1.5,"goals_conceded_avg":1.2,
            "clean_sheets_rate":0.3,"goal_diff_avg":0.3,"form_pts":0.5,"games_played":1}
        fa = rolling_feats(log, r["away_team"], r["date"]) or {
            "win_rate":0.5,"draw_rate":0.25,"goals_scored_avg":1.5,"goals_conceded_avg":1.2,
            "clean_sheets_rate":0.3,"goal_diff_avg":0.3,"form_pts":0.5,"games_played":1}
        hh = h2h_feats(log, r["home_team"], r["away_team"], r["date"])
        eh=elo_map.get(r["home_team"],1550); ea=elo_map.get(r["away_team"],1550)
        rh=rank_map.get(r["home_team"],80);  ra=rank_map.get(r["away_team"],80)
        row = {
            "h_win_rate":fh["win_rate"],"h_draw_rate":fh["draw_rate"],
            "h_goals_scored_avg":fh["goals_scored_avg"],"h_goals_conceded_avg":fh["goals_conceded_avg"],
            "h_clean_sheets_rate":fh["clean_sheets_rate"],"h_goal_diff_avg":fh["goal_diff_avg"],
            "h_form_pts":fh["form_pts"],"h_fifa_rank":rh,"h_elo":eh,"h_elo_expected":elo_exp(eh,ea),
            "a_win_rate":fa["win_rate"],"a_draw_rate":fa["draw_rate"],
            "a_goals_scored_avg":fa["goals_scored_avg"],"a_goals_conceded_avg":fa["goals_conceded_avg"],
            "a_clean_sheets_rate":fa["clean_sheets_rate"],"a_goal_diff_avg":fa["goal_diff_avg"],
            "a_form_pts":fa["form_pts"],"a_fifa_rank":ra,"a_elo":ea,
            "rank_diff":rh-ra,"elo_diff":eh-ea,"elo_expected_home":elo_exp(eh,ea),
            "h2h_win_rate":hh["h2h_win_rate"],"h2h_goal_diff":hh["h2h_goal_diff"],
            "h2h_games":hh["h2h_games"],"neutral":int(r["neutral"]),
        }
        X_rows.append([row[c] for c in FEAT_COLS])
        hg,ag = r["home_score"],r["away_score"]
        y_rows.append(2 if hg>ag else (1 if hg==ag else 0))

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_rows)

    model = CalibratedClassifierCV(
        xgb.XGBClassifier(
            objective="multi:softprob",num_class=3,n_estimators=400,
            learning_rate=0.04,max_depth=4,subsample=0.8,colsample_bytree=0.75,
            min_child_weight=3,gamma=0.1,use_label_encoder=False,
            eval_metric="mlogloss",random_state=42,verbosity=0,
        ),
        method="isotonic", cv=5
    )
    model.fit(X, y)

    with open(DADOS / "model_calibrated.pkl","wb") as f: pickle.dump(model, f)
    with open(DADOS / "feat_cols_v2.pkl","wb") as f:    pickle.dump(FEAT_COLS, f)

    # Salvar log para uso nos próximos passos
    log.to_pickle(DADOS / "_log_cache.pkl")

    print(f"   ✅ Modelo retreinado com {len(X)} jogos")
    return model, FEAT_COLS, log, rank_map, elo_map


# ─────────────────────────────────────────────────────────
# PASSO 3 — Buscar odds da API
# ─────────────────────────────────────────────────────────
def step3_fetch_odds():
    if not ODDS_KEY:
        print("ℹ️  Passo 3: ODDS_API_KEY não definida — pulando busca de odds")
        return None, None

    print("🌐 Passo 3: Buscando odds de mercado...")

    def fetch(sport, market):
        url  = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {"apiKey":ODDS_KEY,"regions":"eu","markets":market,"oddsFormat":"decimal"}
        r = requests.get(url, params=params, timeout=15)
        remaining = r.headers.get("x-requests-remaining","?")
        print(f"   {sport}/{market} → HTTP {r.status_code} | requests restantes: {remaining}")
        if r.status_code != 200:
            print(f"   ⚠ Erro: {r.text[:100]}")
            return None
        return r.json()

    games_data    = fetch("soccer_fifa_world_cup", "h2h")
    outrights_raw = fetch("soccer_fifa_world_cup_winner", "outrights")

    if games_data:
        with open(DADOS / "odds_raw_games.json","w",encoding="utf-8") as f:
            json.dump(games_data, f, ensure_ascii=False, indent=2)
    if outrights_raw:
        with open(DADOS / "odds_raw_winner.json","w",encoding="utf-8") as f:
            json.dump(outrights_raw, f, ensure_ascii=False, indent=2)

    return games_data, outrights_raw


# ─────────────────────────────────────────────────────────
# PASSO 4 — Parsear odds e montar probs de mercado
# ─────────────────────────────────────────────────────────
def step4_parse_odds(games_data, outrights_raw):
    # Se não veio da API, tentar carregar arquivo salvo anteriormente
    if games_data is None:
        path = DADOS / "odds_raw_games.json"
        if path.exists():
            with open(path) as f: games_data = json.load(f)
            print("   ℹ️  Usando odds salvas de chamada anterior")
        else:
            parsed_path = DADOS / "market_probs_parsed.json"
            if parsed_path.exists():
                with open(parsed_path) as f: parsed = json.load(f)
                market_probs = {tuple(k.split("|")): v
                                for k, v in parsed.get("match_odds", {}).items()}
                mkt_champion = parsed.get("champion_odds", {})
                print(f"   ℹ️  Usando odds parseadas salvas ({len(market_probs)} jogos)")
                return market_probs, mkt_champion
            print("ℹ️  Passo 4: sem odds disponíveis — blend usará apenas modelo")
            return {}, {}

    print("🔀 Passo 4: Parseando odds...")

    # h2h
    market_probs = {}
    for g in games_data:
        home_en = g.get("home_team",""); away_en = g.get("away_team","")
        if not home_en or not away_en: continue
        home_pt = NAME_MAP.get(home_en, home_en)
        away_pt = NAME_MAP.get(away_en, away_en)
        ho, dr, ao = [], [], []
        for bm in g.get("bookmakers",[]):
            for mkt in bm.get("markets",[]):
                if mkt["key"] != "h2h": continue
                for o in mkt["outcomes"]:
                    n,p = o["name"], o["price"]
                    if n==home_en: ho.append(p)
                    elif n==away_en: ao.append(p)
                    elif n=="Draw": dr.append(p)
        if not ho: continue
        raw = [1/np.mean(ho), 1/np.mean(dr) if dr else 0, 1/np.mean(ao)]
        tot = sum(raw)
        market_probs[(home_pt, away_pt)] = {
            "p_home": round(raw[0]/tot,4),
            "p_draw": round(raw[1]/tot,4),
            "p_away": round(raw[2]/tot,4),
            "n_bm":   len(ho),
        }

    # outrights
    mkt_champion = {}
    if outrights_raw:
        all_odds = {}
        for entry in outrights_raw:
            for bm in entry.get("bookmakers",[]):
                for mkt in bm.get("markets",[]):
                    if mkt["key"] != "outrights": continue
                    for o in mkt["outcomes"]:
                        name_pt = NAME_MAP.get(o["name"], o["name"])
                        all_odds.setdefault(name_pt,[]).append(o["price"])
        raw_p = {t: 1/np.mean(v) for t,v in all_odds.items()}
        tot = sum(raw_p.values())
        mkt_champion = {t: round(p/tot*100,2) for t,p in raw_p.items()}

    with open(DADOS / "market_probs_parsed.json","w",encoding="utf-8") as f:
        json.dump({"match_odds":{f"{k[0]}|{k[1]}":v for k,v in market_probs.items()},
                   "champion_odds":mkt_champion}, f, ensure_ascii=False, indent=2)

    blend_count = len(market_probs)
    print(f"   ✅ {blend_count} jogos com odds | {len(mkt_champion)} times com odds de campeão")
    return market_probs, mkt_champion


# ─────────────────────────────────────────────────────────
# PASSO 5 — Blend modelo + mercado para fase de grupos
# ─────────────────────────────────────────────────────────
def step5_blend(model, FEAT_COLS, log, rank_map, elo_map, market_probs):
    print("🔀 Passo 5: Calculando probabilidades blendadas...")

    df_matches = pd.read_csv(DADOS / "wc2026_matches.csv")
    df_teams   = pd.read_csv(DADOS / "wc2026_groups.csv")

    def build_row(home, away, date, neutral=1):
        def elo_exp(ea,eb): return 1/(1+10**((eb-ea)/400))
        def rf(team, before):
            past=log[(log["team"]==team)&(log["date"]<before)].tail(10)
            if len(past)==0: return {"win_rate":0.5,"draw_rate":0.25,"goals_scored_avg":1.5,"goals_conceded_avg":1.2,"clean_sheets_rate":0.3,"goal_diff_avg":0.3,"form_pts":0.5,"games_played":1}
            n=len(past); w=(past["result"]=="W").sum(); d=(past["result"]=="D").sum()
            wts=np.exp(np.linspace(-1,0,n)); wts/=wts.sum()
            gf=past["goals_for"].values; ga=past["goals_against"].values
            return {"win_rate":w/n,"draw_rate":d/n,"goals_scored_avg":np.average(gf,weights=wts),"goals_conceded_avg":np.average(ga,weights=wts),"clean_sheets_rate":(ga==0).sum()/n,"goal_diff_avg":np.average(gf-ga,weights=wts),"form_pts":(w*3+d)/(n*3),"games_played":n}
        def h2h(a,b,before):
            cut=pd.Timestamp(before)-pd.DateOffset(years=5)
            h=log[(log["team"]==a)&(log["opponent"]==b)&(log["date"]>=cut)&(log["date"]<before)]
            if len(h)==0: return {"h2h_win_rate":0.5,"h2h_goal_diff":0.0,"h2h_games":0}
            return {"h2h_win_rate":(h["result"]=="W").sum()/len(h),"h2h_goal_diff":(h["goals_for"]-h["goals_against"]).mean(),"h2h_games":len(h)}
        d=pd.Timestamp(date); fh=rf(home,d); fa=rf(away,d); hh=h2h(home,away,d)
        eh=elo_map.get(home,1550); ea=elo_map.get(away,1550)
        rh=rank_map.get(home,80);  ra=rank_map.get(away,80)
        row={"h_win_rate":fh["win_rate"],"h_draw_rate":fh["draw_rate"],"h_goals_scored_avg":fh["goals_scored_avg"],"h_goals_conceded_avg":fh["goals_conceded_avg"],"h_clean_sheets_rate":fh["clean_sheets_rate"],"h_goal_diff_avg":fh["goal_diff_avg"],"h_form_pts":fh["form_pts"],"h_fifa_rank":rh,"h_elo":eh,"h_elo_expected":elo_exp(eh,ea),"a_win_rate":fa["win_rate"],"a_draw_rate":fa["draw_rate"],"a_goals_scored_avg":fa["goals_scored_avg"],"a_goals_conceded_avg":fa["goals_conceded_avg"],"a_clean_sheets_rate":fa["clean_sheets_rate"],"a_goal_diff_avg":fa["goal_diff_avg"],"a_form_pts":fa["form_pts"],"a_fifa_rank":ra,"a_elo":ea,"rank_diff":rh-ra,"elo_diff":eh-ea,"elo_expected_home":elo_exp(eh,ea),"h2h_win_rate":hh["h2h_win_rate"],"h2h_goal_diff":hh["h2h_goal_diff"],"h2h_games":hh["h2h_games"],"neutral":neutral}
        return [row[c] for c in FEAT_COLS]

    rows = []
    for _, m in df_matches[df_matches["stage"]=="group"].iterrows():
        raw_proba = model.predict_proba([build_row(m["home_team"],m["away_team"],m["date"])])[0]
        mp = {"home_win":float(raw_proba[2]),"draw":float(raw_proba[1]),"away_win":float(raw_proba[0])}
        key=(m["home_team"],m["away_team"]); keyI=(m["away_team"],m["home_team"])
        if key in market_probs:
            mk=market_probs[key]
            fp={k:BLEND_ALPHA*mk[f'p_{["home","draw","away"][i]}']+(1-BLEND_ALPHA)*list(mp.values())[i] for i,k in enumerate(mp)}
            src="blend"
        elif keyI in market_probs:
            mk=market_probs[keyI]; mkA={"p_home":mk["p_away"],"p_draw":mk["p_draw"],"p_away":mk["p_home"]}
            fp={k:BLEND_ALPHA*mkA[f'p_{["home","draw","away"][i]}']+(1-BLEND_ALPHA)*list(mp.values())[i] for i,k in enumerate(mp)}
            src="blend"
        else:
            fp=mp; src="model_only"
        tot=sum(fp.values())
        fp={k:round(v/tot,4) for k,v in fp.items()}
        rows.append({**m.to_dict(),"p_home_win":fp["home_win"],"p_draw":fp["draw"],"p_away_win":fp["away_win"],
                     "p_home_win_model":round(mp["home_win"],4),"source":src,"blend_alpha":BLEND_ALPHA if src=="blend" else 0})

    df_bl = pd.DataFrame(rows)
    df_bl.to_csv(DADOS / "all_group_match_probs_blended.csv", index=False)

    blend_n = (df_bl["source"]=="blend").sum()
    print(f"   ✅ {blend_n} blendados | {len(df_bl)-blend_n} só modelo")
    return df_bl


# ─────────────────────────────────────────────────────────
# PASSO 6 — Monte Carlo completo
# ─────────────────────────────────────────────────────────
def step6_monte_carlo(model, FEAT_COLS, log, rank_map, elo_map, df_bl, n_sims=None, save=True):
    n = n_sims if n_sims is not None else N_SIMS
    print(f"🎲 Passo 6: Monte Carlo ({n:,} simulações)...")
    if save:
        np.random.seed(42)

    df_teams = pd.read_csv(DADOS / "wc2026_groups.csv")
    GROUP_TEAMS = {g: list(sub["team"]) for g, sub in df_teams.groupby("group")}
    GROUP_MATCHES = {}
    for g, t in GROUP_TEAMS.items():
        t1,t2,t3,t4=t
        GROUP_MATCHES[g]=[(t1,t2),(t3,t4),(t1,t3),(t2,t4),(t4,t1),(t2,t3)]
    DATES={"group":"2026-06-20","round32":"2026-06-29","r16":"2026-07-05","qf":"2026-07-11","sf":"2026-07-15","final":"2026-07-19"}

    prob_cache={}
    for _,r in df_bl.iterrows():
        prob_cache[(r["home_team"],r["away_team"])]=(r["p_home_win"],r["p_draw"],r["p_away_win"])

    _ko={}
    def pred_ko(home,away,date):
        k=(home,away,date)
        if k not in _ko:
            def elo_exp(ea,eb): return 1/(1+10**((eb-ea)/400))
            def rf(team, before):
                past=log[(log["team"]==team)&(log["date"]<before)].tail(10)
                if len(past)==0: return {"win_rate":0.5,"draw_rate":0.25,"goals_scored_avg":1.5,"goals_conceded_avg":1.2,"clean_sheets_rate":0.3,"goal_diff_avg":0.3,"form_pts":0.5,"games_played":1}
                n=len(past); w=(past["result"]=="W").sum(); d=(past["result"]=="D").sum()
                wts=np.exp(np.linspace(-1,0,n)); wts/=wts.sum()
                gf=past["goals_for"].values; ga=past["goals_against"].values
                return {"win_rate":w/n,"draw_rate":d/n,"goals_scored_avg":np.average(gf,weights=wts),"goals_conceded_avg":np.average(ga,weights=wts),"clean_sheets_rate":(ga==0).sum()/n,"goal_diff_avg":np.average(gf-ga,weights=wts),"form_pts":(w*3+d)/(n*3),"games_played":n}
            def h2h(a,b,before):
                cut=pd.Timestamp(before)-pd.DateOffset(years=5)
                h=log[(log["team"]==a)&(log["opponent"]==b)&(log["date"]>=cut)&(log["date"]<before)]
                if len(h)==0: return {"h2h_win_rate":0.5,"h2h_goal_diff":0.0,"h2h_games":0}
                return {"h2h_win_rate":(h["result"]=="W").sum()/len(h),"h2h_goal_diff":(h["goals_for"]-h["goals_against"]).mean(),"h2h_games":len(h)}
            d2=pd.Timestamp(date); fh=rf(home,d2); fa=rf(away,d2); hh=h2h(home,away,d2)
            eh=elo_map.get(home,1550); ea=elo_map.get(away,1550)
            rh=rank_map.get(home,80);  ra=rank_map.get(away,80)
            row={"h_win_rate":fh["win_rate"],"h_draw_rate":fh["draw_rate"],"h_goals_scored_avg":fh["goals_scored_avg"],"h_goals_conceded_avg":fh["goals_conceded_avg"],"h_clean_sheets_rate":fh["clean_sheets_rate"],"h_goal_diff_avg":fh["goal_diff_avg"],"h_form_pts":fh["form_pts"],"h_fifa_rank":rh,"h_elo":eh,"h_elo_expected":elo_exp(eh,ea),"a_win_rate":fa["win_rate"],"a_draw_rate":fa["draw_rate"],"a_goals_scored_avg":fa["goals_scored_avg"],"a_goals_conceded_avg":fa["goals_conceded_avg"],"a_clean_sheets_rate":fa["clean_sheets_rate"],"a_goal_diff_avg":fa["goal_diff_avg"],"a_form_pts":fa["form_pts"],"a_fifa_rank":ra,"a_elo":ea,"rank_diff":rh-ra,"elo_diff":eh-ea,"elo_expected_home":elo_exp(eh,ea),"h2h_win_rate":hh["h2h_win_rate"],"h2h_goal_diff":hh["h2h_goal_diff"],"h2h_games":hh["h2h_games"],"neutral":1}
            proba=model.predict_proba([[row[c] for c in FEAT_COLS]])[0]
            _ko[k]=(float(proba[2]),float(proba[1]),float(proba[0]))
        return _ko[k]

    def sim_m(home,away,date,ko=False):
        key=(home,away)
        if key in prob_cache: pw,pd_,pa=prob_cache[key]
        elif (away,home) in prob_cache: pa,pd_,pw=prob_cache[(away,home)]
        else: pw,pd_,pa=pred_ko(home,away,date)
        r=np.random.random()
        if r<pw: return home
        elif r<pw+pd_:
            if ko: return home if np.random.random()<0.5 else away
            return "draw"
        else: return away

    def sim_g(g):
        teams=GROUP_TEAMS[g]; pts={t:0 for t in teams}; gd={t:0 for t in teams}; gfd={t:0 for t in teams}
        for h,a in GROUP_MATCHES[g]:
            key=(h,a)
            if key in prob_cache: ph,pd_,pa=prob_cache[key]
            elif (a,h) in prob_cache: pa,pd_,ph=prob_cache[(a,h)]
            else: ph,pd_,pa=pred_ko(h,a,DATES["group"])
            r=np.random.random()
            if r<ph:
                hg=int(np.random.poisson(1.8)); ag=max(0,hg-int(np.random.poisson(0.8)+1))
                if ag>=hg: ag=hg-1; pts[h]+=3
            elif r<ph+pd_: hg=int(np.random.poisson(1.2)); ag=hg
            else:
                ag=int(np.random.poisson(1.8)); hg=max(0,ag-int(np.random.poisson(0.8)+1))
                if hg>=ag: hg=ag-1; pts[a]+=3
            gd[h]+=hg-ag; gd[a]+=ag-hg; gfd[h]+=hg; gfd[a]+=ag
        return sorted(teams,key=lambda t:(pts[t],gd[t],gfd[t]),reverse=True), pts, gd

    ch={t:0 for t in df_teams["team"]}; fn={t:0 for t in df_teams["team"]}
    sf={t:0 for t in df_teams["team"]}; qf={t:0 for t in df_teams["team"]}
    r16={t:0 for t in df_teams["team"]}; r32={t:0 for t in df_teams["team"]}
    ga={t:0 for t in df_teams["team"]}
    clasico={"round32":0,"round16":0,"quarter":0,"semi":0,"final":0,"any":0}
    BR,ARG="Brasil","Argentina"

    for _ in range(n):
        gr={}; thirds=[]
        for g in "ABCDEFGHIJKL":
            ranked,pts,gd=sim_g(g); gr[g]=ranked
            thirds.append((g,ranked[2],pts[ranked[2]],gd[ranked[2]]))
            ga[ranked[0]]+=1; ga[ranked[1]]+=1
        t8={x[1] for x in sorted(thirds,key=lambda x:(x[2],x[3]),reverse=True)[:8]}
        for t in t8: ga[t]+=1
        pairs=[(gr["A"][0],gr["B"][1]),(gr["B"][0],gr["A"][1]),(gr["C"][0],gr["D"][1]),(gr["D"][0],gr["C"][1]),(gr["E"][0],gr["F"][1]),(gr["F"][0],gr["E"][1]),(gr["G"][0],gr["H"][1]),(gr["H"][0],gr["G"][1]),(gr["I"][0],gr["J"][1]),(gr["J"][0],gr["I"][1]),(gr["K"][0],gr["L"][1]),(gr["L"][0],gr["K"][1])]
        tl=list(t8); np.random.shuffle(tl)
        rf_=[gr[g][0] for g in "ACEGIK"]; np.random.shuffle(rf_)
        for i in range(min(4,len(tl),len(rf_))): pairs.append((rf_[i],tl[i]))
        et=[t for t in t8 if t not in [p[1] for p in pairs[-4:]]]; ef=[gr[g][0] for g in "BDFHJL" if gr[g][0] not in [p[0] for p in pairs]]
        while len(pairs)<16 and et and ef: pairs.append((ef.pop(),et.pop()))
        rw=[]
        for h,a in pairs[:16]:
            w=sim_m(h,a,DATES["round32"],True); rw.append(w); r32[w]+=1
            if {h,a}=={BR,ARG}: clasico["round32"]+=1; clasico["any"]+=1
        lw=[]
        for i in range(0,16,2):
            if i+1<len(rw):
                w=sim_m(rw[i],rw[i+1],DATES["r16"],True); lw.append(w); r16[w]+=1
                if {rw[i],rw[i+1]}=={BR,ARG}: clasico["round16"]+=1; clasico["any"]+=1
        qw=[]
        for i in range(0,len(lw),2):
            if i+1<len(lw):
                w=sim_m(lw[i],lw[i+1],DATES["qf"],True); qw.append(w); qf[w]+=1
                if {lw[i],lw[i+1]}=={BR,ARG}: clasico["quarter"]+=1; clasico["any"]+=1
        sw=[]
        for i in range(0,len(qw),2):
            if i+1<len(qw):
                # fn conta os dois finalistas (vencedores das semis)
                w=sim_m(qw[i],qw[i+1],DATES["sf"],True); sw.append(w); sf[w]+=1; fn[w]+=1
                if {qw[i],qw[i+1]}=={BR,ARG}: clasico["semi"]+=1; clasico["any"]+=1
        if len(sw)>=2:
            c=sim_m(sw[0],sw[1],DATES["final"],True); ch[c]+=1
            if {sw[0],sw[1]}=={BR,ARG}: clasico["final"]+=1; clasico["any"]+=1

    def pct(d): return {k:round(v/n*100,2) for k,v in d.items()}
    clasico_pct={k:round(v/n*100,2) for k,v in clasico.items()}
    results={"champion":pct(ch),"final":pct(fn),"semi":pct(sf),"quarter":pct(qf),"round16":pct(r16),"round32":pct(r32),"group_adv":pct(ga),"brasil_argentina":clasico_pct,"n_sims":n,"blend_alpha":BLEND_ALPHA}
    if save:
        with open(DADOS / "tournament_simulation.json","w",encoding="utf-8") as f:
            json.dump(results,f,ensure_ascii=False,indent=2)
    print(f"   ✅ Simulação concluída")
    return results


# ─────────────────────────────────────────────────────────
# PASSO 7 — Montar slim_data e atualizar index.html
# ─────────────────────────────────────────────────────────
def step7_update_html(results, df_bl, mkt_champion):
    print("🖥️  Passo 7: Atualizando index.html...")

    df_teams = pd.read_csv(DADOS / "wc2026_groups.csv")
    flags = {"Brasil":"🇧🇷","Marrocos":"🇲🇦","Haiti":"🇭🇹","Escócia":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","França":"🇫🇷","Espanha":"🇪🇸","Bélgica":"🇧🇪","Holanda":"🇳🇱","Argentina":"🇦🇷","Portugal":"🇵🇹","México":"🇲🇽","Noruega":"🇳🇴","Croácia":"🇭🇷","Alemanha":"🇩🇪","Inglaterra":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","Colômbia":"🇨🇴","Suíça":"🇨🇭","Equador":"🇪🇨","Coreia do Sul":"🇰🇷","Japão":"🇯🇵","Irã":"🇮🇷","Senegal":"🇸🇳","Tunísia":"🇹🇳","Itália":"🇮🇹","Áustria":"🇦🇹","Egito":"🇪🇬","República Tcheca":"🇨🇿","Estados Unidos":"🇺🇸","Uruguai":"🇺🇾","Canadá":"🇨🇦","Turquia":"🇹🇷","Ucrânia":"🇺🇦","Austrália":"🇦🇺","Catar":"🇶🇦","RD Congo":"🇨🇩","Nova Zelândia":"🇳🇿","Argélia":"🇩🇿","África do Sul":"🇿🇦","Paraguai":"🇵🇾","Arábia Saudita":"🇸🇦","Costa do Marfim":"🇨🇮","Curaçao":"🇨🇼","Uzbequistão":"🇺🇿","Cabo Verde":"🇨🇻","Panamá":"🇵🇦","Gana":"🇬🇭","Iraque":"🇮🇶","Jordânia":"🇯🇴","Bósnia e Herzegovina":"🇧🇦","Suécia":"🇸🇪"}

    teams_list = []
    for _, t in df_teams.iterrows():
        name = t["team"]
        teams_list.append({
            "team": name, "group": t["group"], "confederation": t["confederation"],
            "fifa_rank": int(t["fifa_rank"]),
            "flag": flags.get(name,"🏳️"),
            "p_champion":  results["champion"].get(name,0),
            "p_final":     results["final"].get(name,0),
            "p_semi":      results["semi"].get(name,0),
            "p_quarter":   results["quarter"].get(name,0),
            "p_round16":   results["round16"].get(name,0),
            "p_round32":   results["round32"].get(name,0),
            "p_group_adv": results["group_adv"].get(name,0),
        })
    teams_list.sort(key=lambda x: x["p_champion"], reverse=True)

    groups_info = {}
    for letter, sub in df_teams.groupby("group"):
        groups_info[letter] = [
            {"team":t["team"],"flag":flags.get(t["team"],"🏳️"),
             "p_champion":results["champion"].get(t["team"],0),
             "p_group_adv":results["group_adv"].get(t["team"],0),
             "fifa_rank":int(t["fifa_rank"])}
            for _, t in sub.iterrows()
        ]

    brasil_games = []
    for _, row in df_bl[(df_bl["home_team"]=="Brasil")|(df_bl["away_team"]=="Brasil")].iterrows():
        is_home = row["home_team"]=="Brasil"
        opp = row["away_team"] if is_home else row["home_team"]
        brasil_games.append({
            "date": row["date"], "home_team": row["home_team"], "away_team": row["away_team"],
            "venue": row.get("venue",""), "opponent": opp,
            "p_brasil_win":  round((row["p_home_win"] if is_home else row["p_away_win"])*100,1),
            "p_draw":        round(row["p_draw"]*100,1),
            "p_brasil_lose": round((row["p_away_win"] if is_home else row["p_home_win"])*100,1),
        })

    brasil_path = {k: results[k].get("Brasil",0) if k != "round16" else results["round16"].get("Brasil",0)
                   for k in ["group_adv","round32","round16","quarter","semi","final","champion"]}

    from collections import defaultdict
    conf_tot = defaultdict(float)
    for t in teams_list: conf_tot[t["confederation"]] += t["p_champion"]
    conf_colors={"UEFA":"#4fc3f7","CONMEBOL":"#81c784","CONCACAF":"#ffb74d","CAF":"#f06292","AFC":"#ce93d8","OFC":"#90a4ae"}
    conf_teams_n={"UEFA":16,"CONMEBOL":6,"CONCACAF":6,"CAF":10,"AFC":9,"OFC":1}
    conf_continents={"UEFA":"Europa","CONMEBOL":"América do Sul","CONCACAF":"América do Norte/Central","CAF":"África","AFC":"Ásia","OFC":"Oceania"}
    conf_summary=sorted([{"name":k,"continent":conf_continents.get(k,""),"teams":conf_teams_n.get(k,0),"p_total":round(v,1),"color":conf_colors.get(k,"#aaa")} for k,v in conf_tot.items()],key=lambda x:-x["p_total"])

    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    slim = {"teams":teams_list,"groups_info":groups_info,"brasil_games":brasil_games,
            "brasil_path":brasil_path,"conf_summary":conf_summary,
            "clasico_final":results.get("brasil_argentina",{}).get("final",0),
            "updated_at":updated_at}

    with open(DADOS / "slim_data.json","w",encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, separators=(",",":"))

    # Injetar no index.html
    html_path = ROOT / "index.html"
    with open(html_path, encoding="utf-8") as f: html = f.read()
    new_data = json.dumps(slim, ensure_ascii=False, separators=(",",":"))
    new_html = re.sub(r'(const D=)(\{.*?\})(;)', lambda m: m.group(1)+new_data+m.group(3), html, flags=re.DOTALL)
    with open(html_path,"w",encoding="utf-8") as f: f.write(new_html)

    print(f"   ✅ index.html atualizado")

    # ── Injetar JOGOS em resultados.html ──
    results_path = DADOS / "resultados_reais.json"
    real_results = []
    if results_path.exists():
        with open(results_path) as f:
            real_results = json.load(f)

    result_map = {}
    for r in real_results:
        key = (r["home_team"], r["away_team"])
        hs, as_ = int(r["home_score"]), int(r["away_score"])
        result_map[key] = {
            "res": "home" if hs > as_ else ("draw" if hs == as_ else "away"),
            "placar": f"{hs}-{as_}"
        }

    # Horários oficiais (UTC) vindos da football-data.org, se já buscados
    agenda_path = DADOS / "agenda.json"
    agenda = {}
    if agenda_path.exists():
        with open(agenda_path) as f:
            for m in json.load(f):
                agenda[frozenset((m["home_team"], m["away_team"]))] = m["utc"]

    group_counter = {}
    group_games = []
    for _, row in df_bl.iterrows():
        h, a = row["home_team"], row["away_team"]
        g = row["group"]
        group_counter[g] = group_counter.get(g, 0) + 1
        r_num = (group_counter[g] + 1) // 2
        real = result_map.get((h, a), {})
        placar_prev = _calibrate_poisson(
            row["p_home_win"], row["p_draw"], row["p_away_win"]
        )
        group_games.append({
            "id": int(row["match_id"]),
            "g": g, "s": row["stage"], "r": r_num,
            "date": row["date"], "venue": row.get("venue", ""),
            "home": h, "hf": flags.get(h, "🏳️"),
            "away": a, "af": flags.get(a, "🏳️"),
            "ph": round(row["p_home_win"] * 100, 1),
            "pd": round(row["p_draw"] * 100, 1),
            "pa": round(row["p_away_win"] * 100, 1),
            "res": real.get("res"),
            "placar": real.get("placar"),
            "placar_prev": placar_prev,
            "time": row.get("kickoff_brt", ""),
            "utc": agenda.get(frozenset((h, a)), ""),
        })

    html_res_path = ROOT / "resultados.html"
    if html_res_path.exists():
        with open(html_res_path, encoding="utf-8") as f:
            html_res = f.read()
        jogos_json = json.dumps(group_games, ensure_ascii=False, separators=(",", ":"))
        # [^\n] evita engolir linhas seguintes quando o ]; está em outra linha
        html_res = re.sub(r'const JOGOS=\[[^\n]*\];', lambda m: f'const JOGOS={jogos_json};', html_res)

        teams_arr = []
        for t in df_teams.to_dict("records"):
            name = t["team"]
            teams_arr.append({
                "t": name,
                "f": flags.get(name, "🏳️"),
                "ga": round(results["group_adv"].get(name, 0), 2),
                "r32": round(results["round32"].get(name, 0), 2),
                "r16": round(results["round16"].get(name, 0), 2),
                "qt": round(results["quarter"].get(name, 0), 2),
                "sm": round(results["semi"].get(name, 0), 2),
                "fn": round(results["final"].get(name, 0), 2),
                "ch": round(results["champion"].get(name, 0), 2),
            })
        teams_json = json.dumps(teams_arr, ensure_ascii=False, separators=(",", ":"))
        html_res = re.sub(r'const TEAMS=\[[^\n]*\];', lambda m: f'const TEAMS={teams_json};', html_res)

        html_res = re.sub(r'const D_UPDATED_AT="[^"]*";', f'const D_UPDATED_AT="{updated_at}";', html_res)
        with open(html_res_path, "w", encoding="utf-8") as f:
            f.write(html_res)
        print(f"   ✅ resultados.html atualizado ({len(group_games)} jogos)")

    # Resumo
    br = results["champion"].get("Brasil",0)
    bro_path = DADOS / "_prev_simulation.json"
    prev_br = 0
    if bro_path.exists():
        with open(bro_path) as f: prev_br = json.load(f).get("champion",{}).get("Brasil",0)
    with open(bro_path,"w") as f: json.dump(results,f)

    print(f"\n{'='*50}")
    print(f"🇧🇷 Brasil: {prev_br:.2f}% → {br:.2f}% ({'↑' if br>=prev_br else '↓'}{abs(br-prev_br):.2f}%)")
    print(f"   Fase de grupos:  {brasil_path['group_adv']:.1f}%")
    print(f"   Rodada de 32:    {brasil_path['round32']:.1f}%")
    print(f"   Oitavas:         {brasil_path['round16']:.1f}%")
    print(f"   Final:           {brasil_path['final']:.1f}%")
    print(f"\n🏆 Top 5 campeões:")
    for t in teams_list[:5]:
        mkt_p = mkt_champion.get(t["team"],0)
        mkt_str = f" (mercado: {mkt_p:.1f}%)" if mkt_p else ""
        print(f"   {t['flag']} {t['team']:<18}: {t['p_champion']:.2f}%{mkt_str}")
    print(f"{'='*50}")


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀 ATUALIZAÇÃO COPA 2026\n")
    step1_update_history()
    model, FEAT_COLS, log, rank_map, elo_map = step2_retrain()
    games_data, outrights_raw = step3_fetch_odds()
    market_probs, mkt_champion = step4_parse_odds(games_data, outrights_raw)
    df_bl = step5_blend(model, FEAT_COLS, log, rank_map, elo_map, market_probs)
    results = step6_monte_carlo(model, FEAT_COLS, log, rank_map, elo_map, df_bl)
    step7_update_html(results, df_bl, mkt_champion)
    print("\n✅ Pronto! Faça git add . && git commit -m 'Atualiza rodada' && git push\n")
