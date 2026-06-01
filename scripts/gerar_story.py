import base64, os
from weasyprint import HTML
from pdf2image import convert_from_path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def font_b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()

BOLD = font_b64("/tmp/oswald-bold.woff2")
REG  = font_b64("/tmp/oswald-regular.woff2")

FONTS = f"""
@font-face {{
  font-family: 'Oswald'; font-weight: 700;
  src: url('data:font/woff2;base64,{BOLD}') format('woff2');
}}
@font-face {{
  font-family: 'Oswald'; font-weight: 400;
  src: url('data:font/woff2;base64,{REG}') format('woff2');
}}
"""

BASE_RESET = """
@page { size: 810pt 1440pt; margin: 0; }
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 810pt; height: 1440pt;
  background: #111111;
  font-family: 'Oswald', sans-serif;
  color: #f0f0ee; overflow: hidden;
  display: flex; flex-direction: column;
}
.top-bar { width: 100%; height: 5pt; background: #00a84f; margin-top: 187pt; flex-shrink: 0; }
.kicker {
  font-size: 14pt; font-weight: 400; letter-spacing: 6pt;
  text-transform: uppercase; color: #00a84f; margin-bottom: 24pt;
}
.flex-gap { flex: 1; }
"""

# ─────────────────────────────────────────────
# STORY 1 — O gancho: 23%
# ─────────────────────────────────────────────
S1 = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
{FONTS}{BASE_RESET}
.inner {{
  flex: 1; display: flex; flex-direction: column;
  padding: 48pt 64pt 0 64pt;
}}
.intro {{
  font-size: 26pt; font-weight: 400; color: #aaa;
  line-height: 1.45; margin-bottom: 52pt;
}}
.number-label {{
  font-size: 22pt; font-weight: 400; color: #ccc; margin-bottom: 6pt;
}}
.number-hero {{ line-height: 0.85; margin-bottom: 10pt; }}
.number-big {{ font-size: 260pt; font-weight: 700; color: #f5c518; letter-spacing: -6pt; }}
.number-unit {{ font-size: 90pt; font-weight: 700; color: #f5c518; }}
.number-anchor {{
  font-size: 28pt; font-weight: 700; color: #f0f0ee;
  text-transform: uppercase; letter-spacing: 2pt;
}}
.teaser {{
  font-size: 24pt; font-weight: 400; color: #555;
  margin-top: 20pt; line-height: 1.4;
}}
.footer-bar {{
  flex-shrink: 0; height: 187pt;
  display: flex; align-items: center;
  padding: 0 64pt;
  border-top: 1pt solid #1e1e1e;
}}
.footer-label {{
  font-size: 14pt; font-weight: 400; letter-spacing: 3pt;
  text-transform: uppercase; color: #333;
}}
</style></head><body>
<div class="top-bar"></div>
<div class="inner">
  <p class="kicker">Copa do Mundo 2026</p>
  <div class="flex-gap"></div>
  <p class="intro">Rodei 100 mil simulações do torneio<br>e um número me surpreendeu.</p>
  <p class="number-label">O Brasil vai à final da Copa?</p>
  <div class="number-hero">
    <span class="number-big">23</span><span class="number-unit">%</span>
  </div>
  <p class="number-anchor">de chance de chegar à final</p>
  <p class="teaser">Mas será que chega lá para ganhar?</p>
  <div class="flex-gap"></div>
</div>
<div class="footer-bar">
  <p class="footer-label">Arraste para ver</p>
</div>
</body></html>"""

# ─────────────────────────────────────────────
# STORY 2 — A tensão: Quem vai ganhar?
# ─────────────────────────────────────────────
S2 = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
{FONTS}{BASE_RESET}
.inner {{
  flex: 1; display: flex; flex-direction: column;
  padding: 48pt 64pt 0 64pt;
}}
.setup {{
  font-size: 26pt; font-weight: 400; color: #aaa;
  line-height: 1.5; margin-bottom: 52pt;
}}
.divider {{ width: 56pt; height: 4pt; background: #00a84f; margin-bottom: 44pt; }}
.question {{
  font-size: 96pt; font-weight: 700; text-transform: uppercase;
  line-height: 0.9; color: #f0f0ee; letter-spacing: -1pt;
}}
.question span {{ color: #f5c518; }}
.footer-bar {{
  flex-shrink: 0; height: 187pt;
  display: flex; align-items: center;
  padding: 0 64pt;
  border-top: 1pt solid #1e1e1e;
}}
.footer-label {{
  font-size: 14pt; font-weight: 400; letter-spacing: 3pt;
  text-transform: uppercase; color: #333;
}}
</style></head><body>
<div class="top-bar"></div>
<div class="inner">
  <p class="kicker">Copa do Mundo 2026</p>
  <div class="flex-gap"></div>
  <p class="setup">
    Mas qual a chance do Brasil<br>
    vencer a final e ser campeão?<br>
    Os dados têm uma resposta.
  </p>
  <div class="divider"></div>
  <p class="question">Quem vai<br>ganhar a<br><span>Copa?</span></p>
  <div class="flex-gap"></div>
</div>
<div class="footer-bar">
  <p class="footer-label">Arraste para ver</p>
</div>
</body></html>"""

# ─────────────────────────────────────────────
# STORY 3 — O CTA: acesse as previsões
# ─────────────────────────────────────────────
S3 = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
{FONTS}{BASE_RESET}
.inner {{
  flex: 1; display: flex; flex-direction: column;
  padding: 48pt 64pt 0 64pt;
}}
.headline {{
  font-size: 80pt; font-weight: 700; text-transform: uppercase;
  line-height: 0.9; letter-spacing: -1pt; margin-bottom: 32pt;
}}
.headline span {{ color: #00a84f; }}
.sub {{
  font-size: 26pt; font-weight: 400; color: #aaa;
  line-height: 1.5; max-width: 620pt;
}}
.link-zone {{
  flex-shrink: 0;
  margin: 0 64pt 187pt 64pt;
  background: #0d0d0d;
  border: 1.5pt solid #2a2a2a;
  border-left: 3pt solid #00a84f;
  padding: 36pt 36pt;
  display: flex; align-items: center;
  justify-content: space-between; gap: 16pt;
}}
.link-label {{
  font-size: 13pt; font-weight: 400; letter-spacing: 4pt;
  text-transform: uppercase; color: #555; margin-bottom: 10pt;
}}
.link-title {{
  font-size: 30pt; font-weight: 700; color: #f0f0ee; line-height: 1.2;
}}
.link-arrow {{
  font-size: 48pt; font-weight: 700; color: #00a84f; flex-shrink: 0;
}}
</style></head><body>
<div class="top-bar"></div>
<div class="inner">
  <p class="kicker">Copa do Mundo 2026</p>
  <div class="flex-gap"></div>
  <h1 class="headline">As previsões<br>já estão<br><span>no ar.</span></h1>
  <p class="sub">
    72 jogos. 48 seleções.<br>
    100 mil simulações.<br>
    Tudo calculado antes<br>do apito inicial.
  </p>
  <div class="flex-gap"></div>
</div>
<div class="link-zone">
  <div>
    <p class="link-label">Acesse o projeto</p>
    <p class="link-title">Ver todas as<br>previsões</p>
  </div>
  <div class="link-arrow">&#8599;</div>
</div>
</body></html>"""


def gerar(html, nome):
    pdf = os.path.join(BASE, f"{nome}.pdf")
    png = os.path.join(BASE, f"{nome}.png")
    print(f"Gerando {nome}...")
    HTML(string=html).write_pdf(pdf)
    pages = convert_from_path(pdf, dpi=96)
    pages[0].save(png, "PNG")
    os.remove(pdf)
    print(f"  {png}  {pages[0].size[0]}x{pages[0].size[1]}px")

gerar(S1, "story_1")
gerar(S2, "story_2")
gerar(S3, "story_3")
print("Pronto.")
