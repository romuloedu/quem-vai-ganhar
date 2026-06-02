#!/usr/bin/env python3
"""
Busca resultados finalizados da football-data.org e atualiza resultados_reais.json.
Seta o output 'new_results=true' quando encontra jogos novos (para o GitHub Actions).
"""
import os, sys, json, datetime, requests
from pathlib import Path

COPA_INICIO = datetime.date(2026, 6, 11)
COPA_FIM    = datetime.date(2026, 7, 20)  # dia após a final (19/jul)

ROOT  = Path(__file__).parent.parent
DADOS = ROOT / "dados"

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
API_URL = "https://api.football-data.org/v4/competitions/WC/matches"

NAME_MAP = {
    "Brazil": "Brasil", "Morocco": "Marrocos", "Scotland": "Escócia",
    "Haiti": "Haiti", "France": "França", "Spain": "Espanha",
    "Belgium": "Bélgica", "Netherlands": "Holanda", "Argentina": "Argentina",
    "Portugal": "Portugal", "Mexico": "México", "Norway": "Noruega",
    "Croatia": "Croácia", "Germany": "Alemanha", "England": "Inglaterra",
    "Colombia": "Colômbia", "Switzerland": "Suíça", "Ecuador": "Equador",
    "South Korea": "Coreia do Sul", "Korea Republic": "Coreia do Sul",
    "Japan": "Japão", "Iran": "Irã", "Senegal": "Senegal",
    "Tunisia": "Tunísia", "Italy": "Itália", "Austria": "Áustria",
    "Egypt": "Egito", "Czech Republic": "República Tcheca",
    "Czechia": "República Tcheca",
    "United States": "Estados Unidos", "USA": "Estados Unidos",
    "Uruguay": "Uruguai", "Canada": "Canadá", "Turkey": "Turquia",
    "Ukraine": "Ucrânia", "Australia": "Austrália", "Qatar": "Catar",
    "DR Congo": "RD Congo", "New Zealand": "Nova Zelândia",
    "Algeria": "Argélia", "South Africa": "África do Sul",
    "Paraguay": "Paraguai", "Saudi Arabia": "Arábia Saudita",
    "Ivory Coast": "Costa do Marfim", "Curaçao": "Curaçao",
    "Uzbekistan": "Uzbequistão", "Cape Verde": "Cabo Verde",
    "Panama": "Panamá", "Ghana": "Gana", "Iraq": "Iraque",
    "Jordan": "Jordânia",
}


def set_gha_output(key, value):
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")


def fetch_finished_matches():
    resp = requests.get(
        API_URL,
        headers={"X-Auth-Token": API_KEY},
        params={"status": "FINISHED"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("matches", [])


def parse_match(m):
    date   = m["utcDate"][:10]
    home   = NAME_MAP.get(m["homeTeam"]["name"], m["homeTeam"]["name"])
    away   = NAME_MAP.get(m["awayTeam"]["name"], m["awayTeam"]["name"])
    score  = m["score"]["fullTime"]
    return {
        "date":       date,
        "home_team":  home,
        "away_team":  away,
        "home_score": score["home"],
        "away_score": score["away"],
        "tournament": "FIFA World Cup",
        "country":    "USA",
    }


def main():
    hoje = datetime.date.today()
    if hoje < COPA_INICIO or hoje > COPA_FIM:
        print(f"Fora do período da Copa ({hoje}). Nada a fazer.")
        set_gha_output("new_results", "false")
        return

    if not API_KEY:
        print("FOOTBALL_DATA_API_KEY não definida — abortando.")
        sys.exit(2)

    results_path = DADOS / "resultados_reais.json"
    with open(results_path) as f:
        existing = json.load(f)

    existing_keys = {(r["home_team"], r["away_team"], r["date"]) for r in existing}

    finished = fetch_finished_matches()
    new_entries = []
    for m in finished:
        score = m.get("score", {}).get("fullTime", {})
        if score.get("home") is None or score.get("away") is None:
            continue
        entry = parse_match(m)
        key   = (entry["home_team"], entry["away_team"], entry["date"])
        if key not in existing_keys:
            new_entries.append(entry)
            existing_keys.add(key)

    if not new_entries:
        print("Nenhum resultado novo.")
        set_gha_output("new_results", "false")
        return

    updated = sorted(existing + new_entries, key=lambda r: r["date"])
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    print(f"{len(new_entries)} resultado(s) novo(s):")
    for e in new_entries:
        print(f"  {e['date']}  {e['home_team']} {e['home_score']} x {e['away_score']} {e['away_team']}")

    set_gha_output("new_results", "true")


if __name__ == "__main__":
    main()
