import base64, os
from weasyprint import HTML
from pdf2image import convert_from_path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def font_b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()

BOLD = font_b64("/tmp/oswald-bold.woff2")
REG  = font_b64("/tmp/oswald-regular.woff2")

BASE_CSS = f"""
@font-face {{
  font-family: 'Oswald';
  font-weight: 700;
  src: url('data:font/woff2;base64,{BOLD}') format('woff2');
}}
@font-face {{
  font-family: 'Oswald';
  font-weight: 400;
  src: url('data:font/woff2;base64,{REG}') format('woff2');
}}
@page {{ size: 810pt 1440pt; margin: 0; }}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  width: 810pt; height: 1440pt;
  background: #111111;
  font-family: 'Oswald', sans-serif;
  color: #f0f0ee;
  overflow: hidden;
  display: flex; flex-direction: column;
}}
.top-bar {{ width: 100%; height: 5pt; background: #00a84f; margin-top: 187pt; flex-shrink: 0; }}
.inner {{
  flex: 1; display: flex; flex-direction: column;
  padding: 44pt 64pt 0 64pt; min-height: 0;
}}
.kicker {{
  font-size: 14pt; font-weight: 400; letter-spacing: 6pt;
  text-transform: uppercase; color: #00a84f; margin-bottom: 20pt;
}}
.intro {{ font-size: 23pt; font-weight: 400; color: #aaa; line-height: 1.45; margin-bottom: 44pt; }}
.number-label {{ font-size: 22pt; font-weight: 400; color: #ccc; margin-bottom: 6pt; }}
.number-hero {{ line-height: 0.85; margin-bottom: 8pt; }}
.number-big {{ font-size: 240pt; font-weight: 700; color: #f5c518; letter-spacing: -6pt; }}
.number-unit {{ font-size: 84pt; font-weight: 700; color: #f5c518; }}
.number-anchor {{
  font-size: 28pt; font-weight: 700; color: #f0f0ee;
  text-transform: uppercase; letter-spacing: 2pt; margin-bottom: 22pt;
}}
.number-context {{ font-size: 25pt; font-weight: 400; color: #aaa; line-height: 1.45; }}
.number-context strong {{ color: #f0f0ee; font-weight: 700; }}
.flex-gap {{ flex: 1; min-height: 24pt; }}
.divider {{ width: 56pt; height: 4pt; background: #00a84f; margin-bottom: 32pt; flex-shrink: 0; }}
.question {{
  font-size: 88pt; font-weight: 700; text-transform: uppercase;
  line-height: 0.9; color: #f0f0ee; letter-spacing: -1pt; flex-shrink: 0;
}}
.question span {{ color: #f5c518; }}
.cta-zone {{
  flex-shrink: 0; margin: 32pt 64pt 187pt 64pt;
  border: 1.5pt solid #2a2a2a; border-left: 3pt solid #00a84f;
  padding: 22pt 28pt;
  display: flex; align-items: center; justify-content: space-between; gap: 16pt;
}}
.cta-text {{ font-size: 20pt; font-weight: 400; color: #888; line-height: 1.4; }}
.cta-text strong {{ display: block; font-size: 22pt; font-weight: 700; color: #f0f0ee; margin-bottom: 4pt; }}
.cta-arrow {{ font-size: 32pt; font-weight: 700; color: #00a84f; flex-shrink: 0; }}
"""

# ─────────────────────────────────────────────
# STORY 1 — Brasil vai à final?
# ─────────────────────────────────────────────
S1 = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>{BASE_CSS}</style></head><body>
<div class="top-bar"></div>
<div class="inner">
  <p class="kicker">Copa do Mundo 2026</p>
  <p class="intro">Rodei 100 mil simulações do torneio.<br>Um número me surpreendeu.</p>
  <p class="number-label">O Brasil vai à final da Copa?</p>
  <div class="number-hero">
    <span class="number-big">23</span><span class="number-unit">%</span>
  </div>
  <p class="number-anchor">de chance de chegar à final</p>
  <p class="number-context">
    É mais do que <strong>França</strong> e <strong>Espanha.</strong><br>
    Mas e a chance de ser campeão?<br>
    Essa é outra história.
  </p>
  <div class="flex-gap"></div>
  <div class="divider"></div>
  <p class="question">Quem vai<br>ganhar a<br><span>Copa?</span></p>
</div>
<div class="cta-zone">
  <div class="cta-text">
    <strong>Ver as previsões completas</strong>
    Toque na etiqueta para acessar
  </div>
  <div class="cta-arrow">&#8599;</div>
</div>
</body></html>"""

# ─────────────────────────────────────────────
# STORY 2 — E de ser hexacampeão?
# ─────────────────────────────────────────────
S2 = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>{BASE_CSS}</style></head><body>
<div class="top-bar"></div>
<div class="inner">
  <p class="kicker">Copa do Mundo 2026</p>
  <p class="intro">Chegar à final é uma coisa.<br>Mas levantar a taça é outra.</p>
  <p class="number-label">E de ser hexacampeão?</p>
  <div class="number-hero">
    <span class="number-big">8,7</span><span class="number-unit">%</span>
  </div>
  <p class="number-anchor">de chance de ser campeão</p>
  <p class="number-context">
    Em 100 simulações, o Brasil levanta<br>
    menos de 9 vezes. Mas ainda é o<br>
    <strong>3º maior favorito</strong> entre 48 seleções.
  </p>
  <div class="flex-gap"></div>
  <div class="divider"></div>
  <p class="question">Quem vai<br>ganhar a<br><span>Copa?</span></p>
</div>
<div class="cta-zone">
  <div class="cta-text">
    <strong>Ver as previsões completas</strong>
    Toque na etiqueta para acessar
  </div>
  <div class="cta-arrow">&#8599;</div>
</div>
</body></html>"""

# ─────────────────────────────────────────────
# STORY 3 — CTA puro
# ─────────────────────────────────────────────
CTA_CSS = f"""
@font-face {{
  font-family: 'Oswald';
  font-weight: 700;
  src: url('data:font/woff2;base64,{BOLD}') format('woff2');
}}
@font-face {{
  font-family: 'Oswald';
  font-weight: 400;
  src: url('data:font/woff2;base64,{REG}') format('woff2');
}}
@page {{ size: 810pt 1440pt; margin: 0; }}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  width: 810pt; height: 1440pt;
  background: #111111;
  font-family: 'Oswald', sans-serif;
  color: #f0f0ee;
  overflow: hidden;
  display: flex; flex-direction: column;
}}
.top-bar {{ width: 100%; height: 5pt; background: #00a84f; margin-top: 187pt; flex-shrink: 0; }}
.inner {{
  flex: 1; display: flex; flex-direction: column; justify-content: space-between;
  padding: 52pt 64pt 0 64pt;
}}
.kicker {{
  font-size: 14pt; font-weight: 400; letter-spacing: 6pt;
  text-transform: uppercase; color: #00a84f; margin-bottom: 36pt;
}}
.headline {{
  font-size: 96pt; font-weight: 700; text-transform: uppercase;
  line-height: 0.9; letter-spacing: -1pt;
}}
.headline span {{ color: #f5c518; }}
.sub {{
  font-size: 26pt; font-weight: 400; color: #aaa;
  line-height: 1.5; margin-top: 32pt; max-width: 640pt;
}}
.sub strong {{ color: #f0f0ee; font-weight: 700; }}
.stats-row {{
  display: flex; gap: 0;
  border-top: 1pt solid #1e1e1e;
  margin-top: 40pt;
}}
.stat {{
  flex: 1; padding: 24pt 0;
  border-right: 1pt solid #1e1e1e;
}}
.stat:last-child {{ border-right: none; }}
.stat-n {{
  font-size: 44pt; font-weight: 700;
  color: #f5c518; line-height: 1;
}}
.stat-d {{
  font-size: 14pt; font-weight: 400;
  color: #666; margin-top: 6pt; line-height: 1.3;
}}
.spacer {{ flex: 1; }}
/* zona de etiqueta — grande, ocupa o espaço central */
.link-zone {{
  flex-shrink: 0;
  margin: 0 64pt 187pt 64pt;
  border: 1.5pt solid #2a2a2a;
  border-left: 3pt solid #00a84f;
  padding: 36pt 36pt;
  display: flex; align-items: center;
  justify-content: space-between; gap: 16pt;
  background: #0d0d0d;
}}
.link-label {{
  font-size: 13pt; font-weight: 400; letter-spacing: 4pt;
  text-transform: uppercase; color: #555; margin-bottom: 10pt;
}}
.link-title {{
  font-size: 28pt; font-weight: 700; color: #f0f0ee; line-height: 1.2;
}}
.link-arrow {{
  font-size: 44pt; font-weight: 700; color: #00a84f; flex-shrink: 0;
}}
"""

S3 = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>{CTA_CSS}</style></head><body>
<div class="top-bar"></div>
<div class="inner">
  <div>
    <p class="kicker">Copa do Mundo 2026</p>
    <h1 class="headline">As<br>previsões<br>estão no<br><span>ar.</span></h1>
    <p class="sub">
      <strong>72 jogos. 48 seleções.</strong><br>
      100 mil simulações para calcular<br>
      as chances de cada time em<br>cada fase do torneio.
    </p>
    <div class="stats-row">
      <div class="stat">
        <div class="stat-n">8,7%</div>
        <div class="stat-d">Brasil<br>campeão</div>
      </div>
      <div class="stat" style="padding-left:20pt">
        <div class="stat-n">23%</div>
        <div class="stat-d">Brasil<br>na final</div>
      </div>
      <div class="stat" style="padding-left:20pt">
        <div class="stat-n">3%</div>
        <div class="stat-d">Clássico<br>na final</div>
      </div>
    </div>
  </div>
  <div class="spacer"></div>
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
