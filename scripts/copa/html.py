"""
html.py
=======
AtualizadorHTML — atualiza index.html e resultados.html com os resultados
mais recentes das simulações, textos dinâmicos e dados dos jogos.
"""

import json
import math
import re
import datetime
from collections import defaultdict

import pandas as pd

from copa.config import BANDEIRAS, CHAMPION_BLEND, ROOT
from copa.limiar_empate import PrevisorResultado
from copa.repositorio import RepositorioDados


class AtualizadorHTML:
    """Injeta dados e textos dinâmicos nos arquivos HTML do site."""

    def __init__(
        self,
        repositorio: RepositorioDados,
        previsor: PrevisorResultado,
    ) -> None:
        """Recebe o repositório de dados e o previsor de resultado/placar."""
        self.repo     = repositorio
        self.previsor = previsor

    # ── Utilitários internos ─────────────────────────────────

    @staticmethod
    def _join(lst: list) -> str:
        """Une lista de nomes em PT-BR com vírgulas e 'e' no final."""
        if not lst:
            return ""
        if len(lst) == 1:
            return lst[0]
        return ", ".join(lst[:-1]) + " e " + lst[-1]

    @staticmethod
    def _dyn_replace(html_str: str, key: str, content: str) -> str:
        """Substitui bloco <!-- DYN:key -->...<!-- /DYN --> pelo novo conteúdo."""
        return re.sub(
            rf"<!-- DYN:{key} -->.*?<!-- /DYN -->",
            f"<!-- DYN:{key} -->{content}<!-- /DYN -->",
            html_str,
            flags=re.DOTALL,
        )

    # ── HTML principal ───────────────────────────────────────

    def atualizar_index(
        self, results: dict, df_bl: pd.DataFrame, mkt_champion: dict
    ) -> None:
        """Atualiza index.html com os dados de simulação, textos dinâmicos e slim_data."""
        print("🖥️  Passo 7: Atualizando index.html...")

        # Blend de odds de campeão com modelo
        if mkt_champion:
            # Com o mata-mata em andamento, time com chance zero no modelo está
            # eliminado — o mercado (que pode ter odds defasadas) não pode ressuscitá-lo.
            ko_iniciado = bool(self.repo.ler_json("knockout_games.json", []))
            blended_ch: dict = {}
            for team, model_p in results["champion"].items():
                if ko_iniciado and model_p <= 0:
                    blended_ch[team] = 0.0
                    continue
                mkt_p = mkt_champion.get(team, model_p)
                blended_ch[team] = CHAMPION_BLEND * mkt_p + (1 - CHAMPION_BLEND) * model_p
            tot = sum(blended_ch.values())
            results["champion"] = {t: round(p / tot * 100, 2) for t, p in blended_ch.items()}
            print(f"   ℹ️  Champion odds blendadas com mercado (alpha={CHAMPION_BLEND})")

        df_teams = self.repo.ler_csv("wc2026_groups.csv")
        flags    = BANDEIRAS

        # Lista de times para o ranking de favoritos
        teams_list = []
        for _, t in df_teams.iterrows():
            name = t["team"]
            teams_list.append({
                "team":        name,
                "group":       t["group"],
                "confederation": t["confederation"],
                "fifa_rank":   int(t["fifa_rank"]),
                "flag":        flags.get(name, "🏳️"),
                "p_champion":  results["champion"].get(name, 0),
                "p_final":     results["final"].get(name, 0),
                "p_semi":      results["semi"].get(name, 0),
                "p_quarter":   results["quarter"].get(name, 0),
                "p_round16":   results["round16"].get(name, 0),
                "p_round32":   results["round32"].get(name, 0),
                "p_group_adv": results["group_adv"].get(name, 0),
            })
        teams_list.sort(key=lambda x: x["p_champion"], reverse=True)

        # Dados por grupo
        groups_info: dict = {}
        for letter, sub in df_teams.groupby("group"):
            groups_info[letter] = [
                {
                    "team":       t["team"],
                    "flag":       flags.get(t["team"], "🏳️"),
                    "p_champion": results["champion"].get(t["team"], 0),
                    "p_group_adv": results["group_adv"].get(t["team"], 0),
                    "fifa_rank":  int(t["fifa_rank"]),
                }
                for _, t in sub.iterrows()
            ]

        # Jogos do Brasil
        brasil_games = []
        mask = (df_bl["home_team"] == "Brasil") | (df_bl["away_team"] == "Brasil")
        for _, row in df_bl[mask].iterrows():
            is_home = row["home_team"] == "Brasil"
            opp     = row["away_team"] if is_home else row["home_team"]
            brasil_games.append({
                "date":          row["date"],
                "home_team":     row["home_team"],
                "away_team":     row["away_team"],
                "venue":         row.get("venue", ""),
                "opponent":      opp,
                "p_brasil_win":  round((row["p_home_win"] if is_home else row["p_away_win"]) * 100, 1),
                "p_draw":        round(row["p_draw"] * 100, 1),
                "p_brasil_lose": round((row["p_away_win"] if is_home else row["p_home_win"]) * 100, 1),
            })

        brasil_path = {
            k: results[k].get("Brasil", 0)
            for k in ["group_adv", "round32", "round16", "quarter", "semi", "final", "champion"]
        }

        # Resumo por confederação
        conf_tot: dict = defaultdict(float)
        for t in teams_list:
            conf_tot[t["confederation"]] += t["p_champion"]
        conf_colors = {
            "UEFA": "#4fc3f7", "CONMEBOL": "#81c784", "CONCACAF": "#ffb74d",
            "CAF": "#f06292", "AFC": "#ce93d8", "OFC": "#90a4ae",
        }
        conf_teams_n = {"UEFA": 16, "CONMEBOL": 6, "CONCACAF": 6, "CAF": 10, "AFC": 9, "OFC": 1}
        conf_continentes = {
            "UEFA": "Europa", "CONMEBOL": "América do Sul",
            "CONCACAF": "América do Norte/Central", "CAF": "África",
            "AFC": "Ásia", "OFC": "Oceania",
        }
        conf_summary = sorted(
            [
                {
                    "name":      k,
                    "continent": conf_continentes.get(k, ""),
                    "teams":     conf_teams_n.get(k, 0),
                    "p_total":   round(v, 2),
                    "color":     conf_colors.get(k, "#aaa"),
                }
                for k, v in conf_tot.items()
            ],
            key=lambda x: -x["p_total"],
        )

        updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        slim = {
            "teams":        teams_list,
            "groups_info":  groups_info,
            "brasil_games": brasil_games,
            "brasil_path":  brasil_path,
            "conf_summary": conf_summary,
            "clasico_final": results.get("brasil_argentina", {}).get("final", 0),
            "updated_at":   updated_at,
        }
        self.repo.salvar_json("slim_data.json", slim, separators=(",", ":"))

        # Textos dinâmicos
        brasil_idx = next((i for i, t in enumerate(teams_list) if t["team"] == "Brasil"), 5)
        brasil_pos = brasil_idx + 1
        brasil_pct = teams_list[brasil_idx]["p_champion"]
        brasil_pct_str = f"{brasil_pct:.2f}".replace(".", ",") + "%"
        top1, top2   = teams_list[0]["team"], teams_list[1]["team"]
        teams_ahead  = [t["team"] for t in teams_list[:brasil_idx]]

        near_brasil  = [t for t in teams_ahead[2:5]]
        header_intro = (
            f"A Copa de 2026 vai ser a maior da história: 48 seleções, 12 grupos e partidas "
            f"espalhadas pelos EUA, México e Canadá. {top1} e {top2} entram como favoritas, com "
            f"{self._join(near_brasil + ['Brasil'])} no pelotão logo atrás. "
            f"A briga pelo título está mais aberta do que parece."
        )

        s1_title  = f"{top1} e {top2} lideram.<br>Brasil é {brasil_pos}º favorito."
        between   = teams_ahead[2:]
        s1_body   = (
            f"Esses são os times com mais chance de levantar a taça. {top1} lidera com {top2} colada. "
            + (
                f"{self._join(between + ['Brasil'])} vêm logo atrás com chances reais de título."
                if between
                else f"Brasil é o terceiro favorito com {brasil_pct_str}."
            )
        )
        ahead_str  = self._join(teams_ahead)
        s1_callout = (
            f"No ranking de favoritos ao título, o Brasil aparece em <b>{brasil_pos}º com "
            f"{brasil_pct_str}</b> — atrás de {ahead_str}. "
            f"Quem costuma barrar o Brasil antes da final é a dupla {top1} e {top2}."
        )

        europa    = next((c for c in conf_summary if c["name"] == "UEFA"), {"p_total": 0, "continent": "Europa"})
        second_c  = conf_summary[1] if len(conf_summary) > 1 else {"continent": "América do Sul"}
        second_n  = conf_teams_n.get(conf_summary[1]["name"] if len(conf_summary) > 1 else "CONMEBOL", 6)
        s2_title  = f"Europa tem {europa['p_total']:.2f}% de chance.<br>{second_c['continent']} é a 2ª força."
        second_pct_str = f"{second_c['p_total']:.2f}" if len(conf_summary) > 1 else "20.00"
        s2_body   = (
            f"A Europa manda {conf_teams_n.get('UEFA', 16)} seleções para a Copa e concentra a maior parte das chances. "
            f"{second_c['continent']}, com apenas {second_n} times, tem {second_pct_str}% de chance de ser campeã."
        )

        brasil_row = df_teams[df_teams["team"] == "Brasil"]
        brasil_grp = brasil_row["group"].iloc[0] if len(brasil_row) > 0 else "C"
        bg_sorted  = sorted(brasil_games, key=lambda g: g["p_brasil_win"], reverse=True)
        easiest_opp = bg_sorted[0]["opponent"]  if bg_sorted else "adversário"
        hardest_opp = bg_sorted[-1]["opponent"] if bg_sorted else "adversário"
        s3_kicker   = f"🇧🇷 Brasil · Grupo {brasil_grp}"

        def _diff(pw: float) -> str:
            if pw >= 68:    return "favorito claro"
            elif pw >= 55:  return "larga na frente"
            elif pw >= 45:  return "jogo equilibrado"
            else:           return "como azarão"

        s3_title = f"{easiest_opp} é o mais fácil.<br>Só {hardest_opp} preocupa de verdade."
        body_parts = [f"contra {g['opponent']}, {_diff(g['p_brasil_win'])}" for g in bg_sorted]
        if len(brasil_games) > 1:
            joined  = "; ".join(body_parts[:-1])
            joined  = joined[0].upper() + joined[1:]
            s3_body = (
                f"O Brasil enfrenta {len(brasil_games)} adversários bem diferentes. "
                f"{joined}. "
                f"{hardest_opp} é o jogo mais preocupante — o mais equilibrado do grupo."
            )
        else:
            s3_body = f"O Brasil enfrenta {easiest_opp} com {_diff(bg_sorted[0]['p_brasil_win'])}."

        brasil_wins = math.floor(brasil_pct)
        s4_title = f"Se essa Copa fosse jogada<br>100 vezes, o Brasil venceria {brasil_wins}."

        # Injetar no index.html
        html_path = ROOT / "index.html"
        with open(html_path, encoding="utf-8") as f:
            html = f.read()

        new_data = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
        new_html = re.sub(
            r"(const D=)(\{.*?\})(;)",
            lambda m: m.group(1) + new_data + m.group(3),
            html,
            flags=re.DOTALL,
        )
        new_html = self._dyn_replace(new_html, "header_intro",
            f'<p class="header-intro">{header_intro}</p>')
        new_html = self._dyn_replace(new_html, "s1_title",
            f'<h2 class="sec-title">{s1_title}</h2>')
        new_html = self._dyn_replace(new_html, "s1_body",
            f'<p class="sec-body">{s1_body}</p>')
        new_html = self._dyn_replace(new_html, "s1_callout",
            f"<p>{s1_callout}</p>")
        new_html = self._dyn_replace(new_html, "s2_title",
            f'<h2 class="sec-title">{s2_title}</h2>')
        new_html = self._dyn_replace(new_html, "s2_body",
            f'<p class="sec-body">{s2_body}</p>')
        new_html = self._dyn_replace(new_html, "s3_kicker",
            f'<p class="sec-kicker verde">{s3_kicker}</p>')
        new_html = self._dyn_replace(new_html, "s3_title",
            f'<h2 class="sec-title">{s3_title}</h2>')
        new_html = self._dyn_replace(new_html, "s3_body",
            f'<p class="sec-body">{s3_body}</p>')
        new_html = self._dyn_replace(new_html, "s4_title",
            f'<h2 class="sec-title">{s4_title}</h2>')

        new_html = re.sub(
            r"const DRAW_K\s*=\s*[0-9.]+;",
            f"const DRAW_K={self.previsor.k:.2f};",
            new_html,
        )
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(new_html)
        print("   ✅ index.html atualizado")

        # Atualiza resultados.html
        self.atualizar_resultados(results, df_bl, df_teams, flags, updated_at)

        # Resumo no terminal
        self._imprimir_resumo(results, teams_list, brasil_path, mkt_champion)

    def atualizar_resultados(
        self,
        results: dict,
        df_bl: pd.DataFrame,
        df_teams: pd.DataFrame,
        flags: dict,
        updated_at: str,
    ) -> None:
        """Injeta a lista de jogos e probabilidades em resultados.html."""
        real_results = self.repo.ler_json("resultados_reais.json", [])
        result_map: dict = {}
        for r in real_results:
            key    = (r["home_team"], r["away_team"])
            hs, as_ = int(r["home_score"]), int(r["away_score"])
            result_map[key] = {
                "res":    "home" if hs > as_ else ("draw" if hs == as_ else "away"),
                "placar": f"{hs}-{as_}",
            }

        frozen_probs: dict = self.repo.ler_json("frozen_probs.json", {})

        agenda: dict = {}
        if self.repo.existe("agenda.json"):
            for m in self.repo.ler_json("agenda.json", []):
                agenda[frozenset((m["home_team"], m["away_team"]))] = m["utc"]

        group_counter: dict = {}
        group_games: list   = []
        for _, row in df_bl.iterrows():
            h, a = row["home_team"], row["away_team"]
            g    = row["group"]
            group_counter[g] = group_counter.get(g, 0) + 1
            r_num  = (group_counter[g] + 1) // 2
            real   = result_map.get((h, a), {})
            fkey   = f"{h}|{a}"

            if fkey in frozen_probs:
                fp = frozen_probs[fkey]
                ph, pd_, pa = fp["ph"], fp["pd"], fp["pa"]
                placar_prev = fp["placar_prev"]
            else:
                ph  = round(row["p_home_win"] * 100, 2)
                pd_ = round(row["p_draw"]     * 100, 2)
                pa  = round(row["p_away_win"] * 100, 2)
                placar_prev = self.previsor.placar_previsto(
                    row["p_home_win"], row["p_draw"], row["p_away_win"]
                )

            group_games.append({
                "id":          int(row["match_id"]),
                "g":           g,
                "s":           row["stage"],
                "r":           r_num,
                "date":        row["date"],
                "venue":       row.get("venue", ""),
                "home":        h,
                "hf":          flags.get(h, "🏳️"),
                "away":        a,
                "af":          flags.get(a, "🏳️"),
                "ph":          ph,
                "pd":          pd_,
                "pa":          pa,
                "res":         real.get("res"),
                "placar":      real.get("placar"),
                "placar_prev": placar_prev,
                "time":        row.get("kickoff_brt", ""),
                "utc":         agenda.get(frozenset((h, a)), ""),
            })

        # Jogos do mata-mata (montados no Passo 6b) entram no mesmo array JOGOS
        knockout_games = self.repo.ler_json("knockout_games.json", [])
        todos_jogos    = group_games + knockout_games

        html_res_path = ROOT / "resultados.html"
        if not html_res_path.exists():
            return

        with open(html_res_path, encoding="utf-8") as f:
            html_res = f.read()

        jogos_json = json.dumps(todos_jogos, ensure_ascii=False, separators=(",", ":"))
        html_res = re.sub(
            r"const JOGOS=\[[^\n]*\];",
            lambda m: f"const JOGOS={jogos_json};",
            html_res,
        )

        teams_arr = []
        for t in df_teams.to_dict("records"):
            name = t["team"]
            teams_arr.append({
                "t":  name,
                "f":  flags.get(name, "🏳️"),
                "ga": round(results["group_adv"].get(name, 0), 2),
                "r32": round(results["round32"].get(name, 0), 2),
                "r16": round(results["round16"].get(name, 0), 2),
                "qt": round(results["quarter"].get(name, 0), 2),
                "sm": round(results["semi"].get(name, 0), 2),
                "fn": round(results["final"].get(name, 0), 2),
                "ch": round(results["champion"].get(name, 0), 2),
            })
        teams_json = json.dumps(teams_arr, ensure_ascii=False, separators=(",", ":"))
        html_res = re.sub(
            r"const TEAMS=\[[^\n]*\];",
            lambda m: f"const TEAMS={teams_json};",
            html_res,
        )
        html_res = re.sub(r'const D_UPDATED_AT="[^"]*";', f'const D_UPDATED_AT="{updated_at}";', html_res)
        html_res = re.sub(r"const PLACARES_AO_VIVO=\{[^\n]*\};", "const PLACARES_AO_VIVO={};", html_res)
        html_res = re.sub(
            r"const DRAW_K=[0-9.]+;",
            f"const DRAW_K={self.previsor.k:.2f};",
            html_res,
        )

        with open(html_res_path, "w", encoding="utf-8") as f:
            f.write(html_res)
        print(
            f"   ✅ resultados.html atualizado "
            f"({len(group_games)} jogos de grupo + {len(knockout_games)} de mata-mata)"
        )

    def _imprimir_resumo(
        self,
        results: dict,
        teams_list: list,
        brasil_path: dict,
        mkt_champion: dict,
    ) -> None:
        """Imprime o resumo de probabilidades do Brasil e top 5 campeões."""
        br      = results["champion"].get("Brasil", 0)
        bro_path = self.repo.dados / "_prev_simulation.json"
        prev_br = 0
        if bro_path.exists():
            import json as _json
            with open(bro_path) as f:
                prev_br = _json.load(f).get("champion", {}).get("Brasil", 0)
        self.repo.salvar_json("_prev_simulation.json", results)

        seta = "↑" if br >= prev_br else "↓"
        print(f"\n{'=' * 50}")
        print(f"🇧🇷 Brasil: {prev_br:.2f}% → {br:.2f}% ({seta}{abs(br - prev_br):.2f}%)")
        print(f"   Fase de grupos:  {brasil_path['group_adv']:.1f}%")
        print(f"   Rodada de 32:    {brasil_path['round32']:.1f}%")
        print(f"   Oitavas:         {brasil_path['round16']:.1f}%")
        print(f"   Final:           {brasil_path['final']:.1f}%")
        print(f"\n🏆 Top 5 campeões:")
        for t in teams_list[:5]:
            mkt_p   = mkt_champion.get(t["team"], 0)
            mkt_str = f" (mercado: {mkt_p:.1f}%)" if mkt_p else ""
            print(f"   {t['flag']} {t['team']:<18}: {t['p_champion']:.2f}%{mkt_str}")
        print(f"{'=' * 50}")
