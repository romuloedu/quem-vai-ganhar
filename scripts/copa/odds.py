"""
odds.py
=======
ClienteOdds — busca odds de mercado via The Odds API.
ParseadorOdds — converte a resposta bruta em probabilidades normalizadas.
"""

import json
import numpy as np
import requests
from pathlib import Path

from copa.config import NAME_MAP, ODDS_KEY
from copa.repositorio import RepositorioDados


class ClienteOdds:
    """Realiza requisições à The Odds API para odds de jogos e outright."""

    def __init__(self, api_key: str = "") -> None:
        """Usa `api_key` ou fallback para variável de ambiente ODDS_API_KEY."""
        self.api_key = api_key or ODDS_KEY

    def _buscar(self, sport: str, market: str) -> dict | None:
        """Faz a requisição HTTP e retorna o JSON ou None em caso de erro."""
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            "apiKey": self.api_key,
            "regions": "eu",
            "markets": market,
            "oddsFormat": "decimal",
        }
        r = requests.get(url, params=params, timeout=15)
        restantes = r.headers.get("x-requests-remaining", "?")
        print(f"   {sport}/{market} → HTTP {r.status_code} | requests restantes: {restantes}")
        if r.status_code != 200:
            print(f"   ⚠ Erro: {r.text[:100]}")
            return None
        return r.json()

    def buscar(self) -> tuple[dict | None, dict | None]:
        """Retorna (games_data, outrights_raw) da API de odds da Copa do Mundo."""
        games_data    = self._buscar("soccer_fifa_world_cup", "h2h")
        outrights_raw = self._buscar("soccer_fifa_world_cup_winner", "outrights")
        return games_data, outrights_raw


class ParseadorOdds:
    """Converte a resposta bruta da The Odds API em probabilidades de mercado."""

    def __init__(self, repositorio: RepositorioDados) -> None:
        """Recebe o repositório para leitura/escrita de arquivos de odds."""
        self.repo = repositorio

    def parsear(
        self, games_data: dict | None, outrights_raw: dict | None
    ) -> tuple[dict, dict]:
        """Retorna (market_probs, mkt_champion) com probabilidades normalizadas.

        Lê de arquivo salvo quando games_data é None, ou usa parsed anterior.
        """
        if games_data is None:
            if self.repo.existe("odds_raw_games.json"):
                games_data = self.repo.ler_json("odds_raw_games.json")
                print("   ℹ️  Usando odds salvas de chamada anterior")
            else:
                parsed_path_exists = self.repo.existe("market_probs_parsed.json")
                if parsed_path_exists:
                    parsed = self.repo.ler_json("market_probs_parsed.json")
                    market_probs = {
                        tuple(k.split("|")): v
                        for k, v in parsed.get("match_odds", {}).items()
                    }
                    mkt_champion = parsed.get("champion_odds", {})
                    print(f"   ℹ️  Usando odds parseadas salvas ({len(market_probs)} jogos)")
                    return market_probs, mkt_champion
                print("ℹ️  Passo 4: sem odds disponíveis — blend usará apenas modelo")
                return {}, {}

        print("🔀 Passo 4: Parseando odds...")

        # Odds h2h por partida
        market_probs: dict = {}
        for g in games_data:
            home_en = g.get("home_team", "")
            away_en = g.get("away_team", "")
            if not home_en or not away_en:
                continue
            home_pt = NAME_MAP.get(home_en, home_en)
            away_pt = NAME_MAP.get(away_en, away_en)
            ho, dr, ao = [], [], []
            for bm in g.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    if mkt["key"] != "h2h":
                        continue
                    for o in mkt["outcomes"]:
                        n, p = o["name"], o["price"]
                        if n == home_en:
                            ho.append(p)
                        elif n == away_en:
                            ao.append(p)
                        elif n == "Draw":
                            dr.append(p)
            if not ho:
                continue
            raw = [1 / np.mean(ho), 1 / np.mean(dr) if dr else 0, 1 / np.mean(ao)]
            tot = sum(raw)
            market_probs[(home_pt, away_pt)] = {
                "p_home": round(raw[0] / tot, 4),
                "p_draw": round(raw[1] / tot, 4),
                "p_away": round(raw[2] / tot, 4),
                "n_bm":   len(ho),
            }

        # Odds outright (campeão)
        mkt_champion: dict = {}
        if outrights_raw:
            all_odds: dict = {}
            for entry in outrights_raw:
                for bm in entry.get("bookmakers", []):
                    for mkt in bm.get("markets", []):
                        if mkt["key"] != "outrights":
                            continue
                        for o in mkt["outcomes"]:
                            name_pt = NAME_MAP.get(o["name"], o["name"])
                            all_odds.setdefault(name_pt, []).append(o["price"])
            raw_p = {t: 1 / np.mean(v) for t, v in all_odds.items()}
            tot = sum(raw_p.values())
            mkt_champion = {t: round(p / tot * 100, 2) for t, p in raw_p.items()}

        self.repo.salvar_json(
            "market_probs_parsed.json",
            {
                "match_odds": {f"{k[0]}|{k[1]}": v for k, v in market_probs.items()},
                "champion_odds": mkt_champion,
            },
        )

        print(f"   ✅ {len(market_probs)} jogos com odds | {len(mkt_champion)} times com odds de campeão")
        return market_probs, mkt_champion
