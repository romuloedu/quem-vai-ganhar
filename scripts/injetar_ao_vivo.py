#!/usr/bin/env python3
"""
Lê dados/placares_ao_vivo.json e injeta PLACARES_AO_VIVO em resultados.html.
Executado após buscar_resultados.py quando há placares ao vivo ou após atualizar.py
para limpar scores antigos caso todos os jogos tenham terminado.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DADOS = ROOT / "dados"

live_path = DADOS / "placares_ao_vivo.json"
html_path = ROOT / "resultados.html"

if not html_path.exists():
    print("resultados.html não encontrado. Pulando.")
    raise SystemExit(0)

jogos = {}
if live_path.exists():
    with open(live_path) as f:
        jogos = json.load(f).get("jogos", {})

html = html_path.read_text(encoding="utf-8")
new_const = (
    "const PLACARES_AO_VIVO="
    + json.dumps(jogos, ensure_ascii=False, separators=(",", ":"))
    + ";"
)
html = re.sub(r"const PLACARES_AO_VIVO=\{[^\n]*\};", new_const, html)
html_path.write_text(html, encoding="utf-8")

if jogos:
    print(f"Injetados {len(jogos)} placar(es) ao vivo: {list(jogos.keys())}")
else:
    print("Nenhum jogo ao vivo — PLACARES_AO_VIVO limpo.")
