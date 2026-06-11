#!/usr/bin/env python3
"""
Injeta os horários oficiais (UTC, vindos de dados/agenda.json) no array JOGOS
de resultados.html. Roda rápido, sem retreinar o modelo.
"""
import json, re
from pathlib import Path

ROOT  = Path(__file__).parent.parent
DADOS = ROOT / "dados"


def main():
    agenda_path = DADOS / "agenda.json"
    if not agenda_path.exists():
        print("agenda.json não existe — nada a injetar.")
        return

    with open(agenda_path) as f:
        # casa/fora podem vir invertidos em relação à nossa base; o horário é o mesmo
        agenda = {frozenset((m["home_team"], m["away_team"])): m["utc"]
                  for m in json.load(f)}

    html_path = ROOT / "resultados.html"
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    match = re.search(r'const JOGOS=(\[[^\n]*\]);', html)
    if not match:
        print("Array JOGOS não encontrado em resultados.html.")
        return

    jogos = json.loads(match.group(1))
    updated = 0
    for j in jogos:
        utc = agenda.get(frozenset((j["home"], j["away"])))
        if utc and j.get("utc") != utc:
            j["utc"] = utc
            updated += 1

    if not updated:
        print("Horários já estavam atualizados.")
        return

    novo = json.dumps(jogos, ensure_ascii=False, separators=(",", ":"))
    html = html[:match.start()] + f"const JOGOS={novo};" + html[match.end():]
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{updated} jogo(s) com horário atualizado.")


if __name__ == "__main__":
    main()
