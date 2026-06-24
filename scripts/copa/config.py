"""
config.py
=========
Configurações centrais: caminhos, constantes, mapeamentos e colunas de features.
"""

import os
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────
ROOT  = Path(__file__).parent.parent.parent
DADOS = ROOT / "dados"

# ── Chaves e hiperparâmetros ──────────────────────────────
ODDS_KEY     = os.getenv("ODDS_API_KEY", "")
BLEND_ALPHA  = 0.65    # peso do mercado no blend de partidas (0 = só modelo, 1 = só mercado)
CHAMPION_BLEND = 0.45  # peso do mercado nas probabilidades de campeão
N_SIMS       = 100_000
SEED         = 42

# ── Mapeamento de nomes EN → PT-BR ───────────────────────
NAME_MAP: dict[str, str] = {
    "Brazil": "Brasil", "Morocco": "Marrocos", "Scotland": "Escócia", "Haiti": "Haiti",
    "France": "França", "Spain": "Espanha", "Belgium": "Bélgica", "Netherlands": "Holanda",
    "Argentina": "Argentina", "Portugal": "Portugal", "Mexico": "México", "Norway": "Noruega",
    "Croatia": "Croácia", "Germany": "Alemanha", "England": "Inglaterra", "Colombia": "Colômbia",
    "Switzerland": "Suíça", "Ecuador": "Equador", "South Korea": "Coreia do Sul", "Japan": "Japão",
    "Iran": "Irã", "Senegal": "Senegal", "Tunisia": "Tunísia", "Italy": "Itália",
    "Austria": "Áustria", "Egypt": "Egito", "Czech Republic": "República Tcheca",
    "United States": "Estados Unidos", "USA": "Estados Unidos", "Uruguay": "Uruguai",
    "Canada": "Canadá", "Turkey": "Turquia", "Ukraine": "Ucrânia", "Australia": "Austrália",
    "Qatar": "Catar", "DR Congo": "RD Congo", "New Zealand": "Nova Zelândia", "Algeria": "Argélia",
    "South Africa": "África do Sul", "Paraguay": "Paraguai", "Saudi Arabia": "Arábia Saudita",
    "Ivory Coast": "Costa do Marfim", "Curaçao": "Curaçao", "Uzbekistan": "Uzbequistão",
    "Cape Verde": "Cabo Verde", "Panama": "Panamá", "Ghana": "Gana", "Iraq": "Iraque",
    "Jordan": "Jordânia", "Bosnia and Herzegovina": "Bósnia e Herzegovina", "Sweden": "Suécia",
}

# ── Bandeiras por time (nome em PT-BR) ───────────────────
BANDEIRAS: dict[str, str] = {
    "Brasil": "🇧🇷", "Marrocos": "🇲🇦", "Haiti": "🇭🇹", "Escócia": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "França": "🇫🇷", "Espanha": "🇪🇸", "Bélgica": "🇧🇪", "Holanda": "🇳🇱",
    "Argentina": "🇦🇷", "Portugal": "🇵🇹", "México": "🇲🇽", "Noruega": "🇳🇴",
    "Croácia": "🇭🇷", "Alemanha": "🇩🇪", "Inglaterra": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Colômbia": "🇨🇴",
    "Suíça": "🇨🇭", "Equador": "🇪🇨", "Coreia do Sul": "🇰🇷", "Japão": "🇯🇵",
    "Irã": "🇮🇷", "Senegal": "🇸🇳", "Tunísia": "🇹🇳", "Itália": "🇮🇹",
    "Áustria": "🇦🇹", "Egito": "🇪🇬", "República Tcheca": "🇨🇿", "Estados Unidos": "🇺🇸",
    "Uruguai": "🇺🇾", "Canadá": "🇨🇦", "Turquia": "🇹🇷", "Ucrânia": "🇺🇦",
    "Austrália": "🇦🇺", "Catar": "🇶🇦", "RD Congo": "🇨🇩", "Nova Zelândia": "🇳🇿",
    "Argélia": "🇩🇿", "África do Sul": "🇿🇦", "Paraguai": "🇵🇾", "Arábia Saudita": "🇸🇦",
    "Costa do Marfim": "🇨🇮", "Curaçao": "🇨🇼", "Uzbequistão": "🇺🇿", "Cabo Verde": "🇨🇻",
    "Panamá": "🇵🇦", "Gana": "🇬🇭", "Iraque": "🇮🇶", "Jordânia": "🇯🇴",
    "Bósnia e Herzegovina": "🇧🇦", "Suécia": "🇸🇪",
}

# ── Colunas de features (ordem exata exigida pelo modelo) ─
FEAT_COLS: list[str] = [
    "h_win_rate", "h_draw_rate", "h_goals_scored_avg", "h_goals_conceded_avg",
    "h_clean_sheets_rate", "h_goal_diff_avg", "h_form_pts", "h_fifa_rank", "h_elo",
    "h_elo_expected", "a_win_rate", "a_draw_rate", "a_goals_scored_avg",
    "a_goals_conceded_avg", "a_clean_sheets_rate", "a_goal_diff_avg", "a_form_pts",
    "a_fifa_rank", "a_elo", "rank_diff", "elo_diff", "elo_expected_home",
    "h2h_win_rate", "h2h_goal_diff", "h2h_games", "neutral",
    "h_confederation", "a_confederation", "h_squad_value", "a_squad_value",
    "h_wc_appearances", "a_wc_appearances", "h_squad_age", "a_squad_age",
    "squad_value_diff", "wc_exp_diff",
    "draw_rate_product", "elo_closeness",
]

# ── Força confederações (codificação numérica) ────────────
CONF_STRENGTH: dict[str, int] = {
    "UEFA": 6, "CONMEBOL": 5, "CONCACAF": 4, "AFC": 3, "CAF": 2, "OFC": 1,
}
