#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de Convergência Monte Carlo — Copa 2026
Varia N (simulações) e mede a variância das probabilidades para determinar
o menor N onde os resultados estabilizam.
"""

import sys
import json
import csv
import argparse
import time
from pathlib import Path
from statistics import mean, stdev

sys.path.insert(0, str(Path(__file__).parent))
import atualizar as atl

BENCH_SIZES = [10_000, 50_000, 100_000, 500_000]
N_RUNS = 10
STD_THRESHOLD = 0.10  # pp (percentage points) — limiar de "estável"


def run_steps_1_to_5():
    """Executa as etapas 1-5 uma vez e retorna os inputs para step6."""
    print("\n" + "=" * 80)
    print("Preparando pipeline (etapas 1-5)...")
    print("=" * 80)

    atl.step1_update_history()
    model, FEAT_COLS, log, rank_map, elo_map = atl.step2_retrain()
    games_data, outrights_raw = atl.step3_fetch_odds()
    market_probs, mkt_champion = atl.step4_parse_odds(games_data, outrights_raw)
    df_bl = atl.step5_blend(model, FEAT_COLS, log, rank_map, elo_map, market_probs)

    print("   ✅ Pipeline preparado\n")
    return model, FEAT_COLS, log, rank_map, elo_map, df_bl


def run_single_bench(model, FEAT_COLS, log, rank_map, elo_map, df_bl, n):
    """Executa uma simulação com n_sims=n e retorna tempo + resultados."""
    t0 = time.perf_counter()
    results = atl.step6_monte_carlo(
        model, FEAT_COLS, log, rank_map, elo_map, df_bl,
        n_sims=n, save=False
    )
    elapsed = time.perf_counter() - t0
    return {"elapsed": elapsed, "champion": results["champion"]}


def run_convergence_suite(model, FEAT_COLS, log, rank_map, elo_map, df_bl, bench_sizes, n_runs):
    """Roda benchmarks para cada N em bench_sizes, n_runs vezes cada."""
    records = []

    for n in bench_sizes:
        print(f"\n{'─' * 80}")
        print(f"N = {n:,} simulações × {n_runs} rodadas")
        print(f"{'─' * 80}")

        for run_idx in range(n_runs):
            rec = run_single_bench(model, FEAT_COLS, log, rank_map, elo_map, df_bl, n)
            rec["n_sims"] = n
            rec["run_index"] = run_idx + 1
            records.append(rec)

            # Exibir progresso por linha
            brasil_pct = rec["champion"].get("Brasil", 0.0)
            print(f"  Run {run_idx + 1:2d}/{n_runs}  {rec['elapsed']:6.2f}s  Brasil: {brasil_pct:7.2f}%")

    return records


def get_top_teams(records, top_n=5):
    """Retorna os top_n times mais prováveis de campeão (a partir da primeira run)."""
    if not records:
        return []
    first_champ = records[0]["champion"]
    sorted_teams = sorted(first_champ.items(), key=lambda x: x[1], reverse=True)
    return [team for team, _ in sorted_teams[:top_n]]


def aggregate(records, top_teams):
    """
    Agrega estatísticas por (n_sims, team).
    Retorna: {n: {team: {mean, stdev, oscillation, time_avg}, ...}, ...}
    """
    agg = {}

    for n in set(r["n_sims"] for r in records):
        runs_at_n = [r for r in records if r["n_sims"] == n]
        agg[n] = {}

        for team in top_teams:
            probs = [r["champion"].get(team, 0.0) for r in runs_at_n]
            times = [r["elapsed"] for r in runs_at_n]

            mean_pct = mean(probs)
            std_pct = stdev(probs) if len(probs) > 1 else 0.0
            oscillation = max(probs) - min(probs)
            time_avg = mean(times)

            agg[n][team] = {
                "mean": mean_pct,
                "stdev": std_pct,
                "oscillation": oscillation,
                "time_avg": time_avg,
            }

    return agg


def format_table(agg, bench_sizes, top_teams, std_threshold):
    """Formata e imprime a tabela de convergência."""
    print("\n" + "═" * 90)
    print("CONVERGÊNCIA MONTE CARLO — PROBABILIDADE DE CAMPEÃO")
    print("═" * 90)

    for team in top_teams:
        print(f"\n{team.upper()}")
        print("─" * 90)

        # Cabeçalho com os tamanhos
        header = "         " + "".join(f"N={n:>9,}".rjust(15) for n in bench_sizes)
        print(header)

        # Média
        means = "  Média % " + "".join(
            f"{agg[n][team]['mean']:>14.2f}%" for n in bench_sizes
        )
        print(means)

        # Desvio padrão
        stdevs = "  Desvio % " + "".join(
            f"{agg[n][team]['stdev']:>14.2f}%" for n in bench_sizes
        )
        print(stdevs)

        # Oscilação (max - min)
        oscs = "  Oscil pp " + "".join(
            f"{agg[n][team]['oscillation']:>14.2f}pp" for n in bench_sizes
        )
        print(oscs)

    # Tempo médio por N
    print("\n" + "─" * 90)
    print("TEMPO MÉDIO POR N")
    print("─" * 90)
    for n in bench_sizes:
        time_avg = mean(agg[n][team]["time_avg"] for team in top_teams)
        print(f"  N={n:>9,}: {time_avg:6.2f}s", end="  ")
    print()

    # Veredicto de convergência
    print("\n" + "─" * 90)
    print(f"VEREDICTO DE CONVERGÊNCIA (limiar: std < {std_threshold:.2f} pp)")
    print("─" * 90)
    for n in bench_sizes:
        # Usar média dos stdevs de todos os times para decisão
        avg_std = mean(agg[n][team]["stdev"] for team in top_teams)
        status = "ESTÁVEL" if avg_std < std_threshold else "INSTÁVEL"
        print(f"  N={n:>9,}: {status:10s}  (std médio: {avg_std:.3f}pp)", end="  ")
    print()

    print("═" * 90 + "\n")


def export_results(records, agg, bench_sizes, top_teams, export_path):
    """Exporta resultados em CSV (raw) e JSON (summary)."""
    dados_dir = export_path / "dados"
    dados_dir.mkdir(exist_ok=True)

    # CSV: um registro por (n, run_index)
    csv_path = dados_dir / "convergencia_raw.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["n_sims", "run_index", "elapsed_s"] + top_teams
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rec in records:
            row = {
                "n_sims": rec["n_sims"],
                "run_index": rec["run_index"],
                "elapsed_s": f"{rec['elapsed']:.3f}",
            }
            for team in top_teams:
                row[team] = f"{rec['champion'].get(team, 0.0):.2f}"
            writer.writerow(row)

    # JSON: stats agregadas
    json_path = dados_dir / "convergencia_summary.json"
    summary = {}
    for n in bench_sizes:
        summary[str(n)] = {}
        for team in top_teams:
            stats = agg[n][team]
            summary[str(n)][team] = {
                "mean_pct": round(stats["mean"], 2),
                "stdev_pct": round(stats["stdev"], 2),
                "oscillation_pp": round(stats["oscillation"], 2),
                "time_avg_s": round(stats["time_avg"], 3),
            }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Resultados salvos em:")
    print(f"  {csv_path}")
    print(f"  {json_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Teste de convergência Monte Carlo para Copa 2026"
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=BENCH_SIZES,
        help=f"Tamanhos de simulação a testar (padrão: {BENCH_SIZES})",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=N_RUNS,
        help=f"Número de rodadas por tamanho (padrão: {N_RUNS})",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Não exportar resultados para CSV/JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=STD_THRESHOLD,
        help=f"Limiar de desvio padrão para 'estável' em pp (padrão: {STD_THRESHOLD})",
    )

    args = parser.parse_args()

    # Ordenar tamanhos
    bench_sizes = sorted(args.sizes)

    print(f"\n🎲 Teste de Convergência Monte Carlo — Copa 2026")
    print(f"   Tamanhos: {bench_sizes}")
    print(f"   Rodadas por tamanho: {args.runs}")
    print(f"   Limiar de estabilidade: {args.threshold} pp")

    # Executar etapas 1-5
    try:
        model, FEAT_COLS, log, rank_map, elo_map, df_bl = run_steps_1_to_5()
    except Exception as e:
        print(f"❌ Erro ao executar etapas 1-5: {e}")
        sys.exit(1)

    # Executar benchmark
    try:
        records = run_convergence_suite(
            model, FEAT_COLS, log, rank_map, elo_map, df_bl,
            bench_sizes, args.runs
        )
    except Exception as e:
        print(f"❌ Erro ao executar benchmarks: {e}")
        sys.exit(1)

    # Determinar top times dinamicamente
    top_teams = get_top_teams(records, top_n=5)
    if not top_teams:
        print("❌ Nenhum resultado obtido")
        sys.exit(1)

    print(f"\n✅ Benchmarks concluídos. Analisando top-5 times: {', '.join(top_teams)}")

    # Agregar
    agg = aggregate(records, top_teams)

    # Imprimir tabela
    format_table(agg, bench_sizes, top_teams, args.threshold)

    # Exportar
    if not args.no_export:
        try:
            export_results(records, agg, bench_sizes, top_teams, Path(__file__).parent.parent)
        except Exception as e:
            print(f"⚠️  Erro ao exportar resultados: {e}")
    else:
        print("(Resultados não foram exportados com --no-export)")


if __name__ == "__main__":
    main()
