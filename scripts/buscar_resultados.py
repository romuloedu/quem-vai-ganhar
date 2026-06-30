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
    "Jordan": "Jordânia", "Bosnia and Herzegovina": "Bósnia e Herzegovina",
    "Bosnia-Herzegovina": "Bósnia e Herzegovina", "Sweden": "Suécia",
    "Congo DR": "RD Congo", "Cape Verde Islands": "Cabo Verde",
}


def set_gha_output(key, value):
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")


def fetch_all_matches():
    resp = requests.get(
        API_URL,
        headers={"X-Auth-Token": API_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("matches", [])


GROUP_STAGES = {"GROUP_STAGE"}

def update_agenda(matches):
    """Grava dados/agenda.json com o horário UTC oficial de cada jogo.
    Retorna True se a agenda mudou."""
    agenda = []
    for m in matches:
        if not m["homeTeam"].get("name") or not m["awayTeam"].get("name"):
            continue  # mata-mata ainda sem times definidos
        home = NAME_MAP.get(m["homeTeam"]["name"], m["homeTeam"]["name"])
        away = NAME_MAP.get(m["awayTeam"]["name"], m["awayTeam"]["name"])
        stage = m.get("stage", "GROUP_STAGE")
        # id é usado para ordenar os confrontos do mata-mata na ordem do chaveamento
        agenda.append({"id": m.get("id"), "home_team": home, "away_team": away,
                       "utc": m["utcDate"], "stage": stage})
    agenda.sort(key=lambda a: (a["utc"], a["home_team"]))

    agenda_path = DADOS / "agenda.json"
    old = json.load(open(agenda_path)) if agenda_path.exists() else None
    if agenda == old:
        return False
    with open(agenda_path, "w", encoding="utf-8") as f:
        json.dump(agenda, f, ensure_ascii=False, indent=2)
    return True


def parse_match(m):
    date   = m["utcDate"][:10]
    home   = NAME_MAP.get(m["homeTeam"]["name"], m["homeTeam"]["name"])
    away   = NAME_MAP.get(m["awayTeam"]["name"], m["awayTeam"]["name"])
    score  = m["score"]["fullTime"]
    entry  = {
        "date":       date,
        "home_team":  home,
        "away_team":  away,
        "home_score": score["home"],
        "away_score": score["away"],
        "tournament": "FIFA World Cup",
        "country":    "USA",
    }
    # Mata-mata: registra a fase, o avançante (pode ser nos pênaltis) e o placar de pênaltis
    stage = m.get("stage", "GROUP_STAGE")
    if stage != "GROUP_STAGE":
        entry["stage"] = stage
        winner = m.get("score", {}).get("winner")
        entry["winner"] = (
            "home" if winner == "HOME_TEAM"
            else "away" if winner == "AWAY_TEAM"
            else None
        )
        pens = m.get("score", {}).get("penalties") or {}
        if pens.get("home") is not None and pens.get("away") is not None:
            entry["penalties"] = f"{pens['home']}-{pens['away']}"
    return entry


def has_game_in_window(existing):
    """Retorna True se há jogo ativo ou recente que justifica chamada à API.

    Janela principal (ao vivo + resultado):
      Do KO até KO+max_min (fase de grupos: 185min, eliminatórias: 300min).

    Catch-up (resultado perdido por lacuna no cron):
      Qualquer jogo sem resultado cujo KO+max_min já passou mas ocorreu
      há menos de 36 horas — garante captura mesmo após a janela.
    """
    agenda_path = DADOS / "agenda.json"
    if not agenda_path.exists():
        return True  # sem agenda, chama por segurança

    existing_pairs = {(r["home_team"], r["away_team"]) for r in existing}
    now = datetime.datetime.now(datetime.timezone.utc)

    with open(agenda_path) as f:
        agenda = json.load(f)

    for m in agenda:
        if (m["home_team"], m["away_team"]) in existing_pairs:
            continue  # resultado já capturado
        try:
            ko = datetime.datetime.fromisoformat(m["utc"].replace("Z", "+00:00"))
        except Exception:
            continue
        stage = m.get("stage", "GROUP_STAGE")
        max_min = 185 if stage in GROUP_STAGES else 300
        elapsed_min = (now - ko).total_seconds() / 60
        if 0 <= elapsed_min <= max_min:
            return True
        # Catch-up: janela já encerrada mas jogo ocorreu nas últimas 36h
        if max_min < elapsed_min <= 36 * 60:
            print(f"  Catch-up: {m['home_team']} vs {m['away_team']} sem resultado "
                  f"(KO+{elapsed_min:.0f}min)")
            return True

    # Descoberta de novas fases: se todos os jogos conhecidos na agenda já
    # aconteceram mas a Copa segue em andamento, consulta a API para descobrir
    # os confrontos do mata-mata recém-definidos — eles só entram na agenda
    # depois que as seleções são conhecidas, então sem este gatilho ficaríamos
    # presos com a agenda da fase de grupos e nunca buscaríamos o mata-mata.
    kickoffs = []
    for m in agenda:
        try:
            kickoffs.append(datetime.datetime.fromisoformat(m["utc"].replace("Z", "+00:00")))
        except Exception:
            continue
    if kickoffs and max(kickoffs) <= now:
        # Há um próximo jogo (mata-mata) que ainda não está na agenda. O guard de
        # período em main() limita esta sondagem à janela da Copa.
        print("  Descoberta: jogos conhecidos já passaram e a Copa continua — "
              "buscando confrontos das próximas fases")
        return True

    return False


def main():
    hoje = datetime.date.today()
    if hoje < COPA_INICIO or hoje > COPA_FIM:
        print(f"Fora do período da Copa ({hoje}). Nada a fazer.")
        set_gha_output("new_results", "false")
        set_gha_output("agenda_changed", "false")
        set_gha_output("live_changed", "false")
        return

    if not API_KEY:
        print("FOOTBALL_DATA_API_KEY não definida — abortando.")
        sys.exit(2)

    results_path = DADOS / "resultados_reais.json"
    with open(results_path) as f:
        existing = json.load(f)

    if not has_game_in_window(existing):
        print("Nenhum jogo na janela de interesse. Pulando chamada à API.")
        set_gha_output("new_results", "false")
        set_gha_output("agenda_changed", "false")
        set_gha_output("live_changed", "false")
        return

    existing_keys = {(r["home_team"], r["away_team"], r["date"]) for r in existing}

    try:
        matches = fetch_all_matches()
    except Exception as e:
        print(f"Erro ao acessar API: {e}")
        set_gha_output("new_results", "false")
        set_gha_output("agenda_changed", "false")
        set_gha_output("live_changed", "false")
        return

    agenda_changed = update_agenda(matches)
    set_gha_output("agenda_changed", "true" if agenda_changed else "false")
    if agenda_changed:
        print("Agenda de horários atualizada.")

    import collections
    status_dist = collections.Counter(m.get("status") for m in matches)
    print(f"  API: {len(matches)} jogos | status: {dict(status_dist)}")
    for m in matches:
        if m.get("status") == "FINISHED":
            ht = NAME_MAP.get(m["homeTeam"]["name"], m["homeTeam"]["name"])
            at = NAME_MAP.get(m["awayTeam"]["name"], m["awayTeam"]["name"])
            sc = m.get("score", {})
            ft = sc.get("fullTime", {})
            print(f"    FINISHED {m['utcDate'][:10]} {ht} {ft.get('home')}x{ft.get('away')} {at}")

    # ── Placares ao vivo ──────────────────────────────────────────────────────
    LIVE_STATUSES = {"IN_PLAY", "HALFTIME", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT", "LIVE"}
    live_jogos = {}
    for m in matches:
        if m.get("status") not in LIVE_STATUSES:
            continue
        ht = NAME_MAP.get(m["homeTeam"].get("name", ""), m["homeTeam"].get("name", ""))
        at = NAME_MAP.get(m["awayTeam"].get("name", ""), m["awayTeam"].get("name", ""))
        if not ht or not at:
            continue
        ft = m.get("score", {}).get("fullTime", {})
        h = ft.get("home") if ft.get("home") is not None else 0
        a = ft.get("away") if ft.get("away") is not None else 0
        live_jogos[f"{ht}|{at}"] = {"home_score": h, "away_score": a, "status": m.get("status")}
        print(f"    {m.get('status')} {ht} {h}x{a} {at}")

    live_path = DADOS / "placares_ao_vivo.json"
    old_live = {}
    if live_path.exists():
        with open(live_path) as _f:
            old_live = json.load(_f).get("jogos", {})
    live_changed = live_jogos != old_live
    with open(live_path, "w", encoding="utf-8") as _f:
        json.dump({"jogos": live_jogos}, _f, ensure_ascii=False, indent=2)
    set_gha_output("live_changed", "true" if live_changed else "false")
    if live_jogos:
        print(f"  {len(live_jogos)} jogo(s) ao vivo.")
    # ─────────────────────────────────────────────────────────────────────────

    new_entries = []
    for m in matches:
        if m.get("status") != "FINISHED":
            continue
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
