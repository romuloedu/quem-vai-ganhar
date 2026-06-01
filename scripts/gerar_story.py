import base64, os
from weasyprint import HTML, CSS
from pdf2image import convert_from_path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PDF = os.path.join(BASE, "story.pdf")
OUT_PNG = os.path.join(BASE, "story.png")

def font_b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()

BOLD = font_b64("/tmp/oswald-bold.woff2")
REG  = font_b64("/tmp/oswald-regular.woff2")

HTML_STORY = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
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

@page {{
  size: 810pt 1440pt;
  margin: 0;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  width: 810pt;
  height: 1440pt;
  background: #111111;
  font-family: 'Oswald', sans-serif;
  color: #f0f0ee;
  overflow: hidden;
  position: relative;
}}

/* barra superior verde */
.top-bar {{
  width: 100%;
  height: 4pt;
  background: #00a84f;
}}

.inner {{
  padding: 52pt 56pt 0 56pt;
  display: flex;
  flex-direction: column;
  height: calc(1440pt - 4pt);
}}

/* kicker */
.kicker {{
  font-size: 11pt;
  font-weight: 400;
  letter-spacing: 5pt;
  text-transform: uppercase;
  color: #00a84f;
  margin-bottom: 18pt;
  margin-top: 36pt;
}}

/* headline */
.headline {{
  font-size: 80pt;
  font-weight: 700;
  text-transform: uppercase;
  line-height: 0.92;
  letter-spacing: -1pt;
  color: #f0f0ee;
  margin-bottom: 10pt;
}}

.headline span {{
  color: #f5c518;
}}

/* subtítulo */
.subtitle {{
  font-size: 18pt;
  font-weight: 400;
  color: #888;
  line-height: 1.5;
  max-width: 580pt;
  margin-top: 14pt;
}}

/* divisor */
.divider {{
  width: 48pt;
  height: 3pt;
  background: #00a84f;
  margin: 44pt 0;
}}

/* bloco de stats */
.stats {{
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 44pt;
}}

.stat-row {{
  display: flex;
  align-items: baseline;
  gap: 16pt;
  padding: 20pt 0;
  border-bottom: 1pt solid #1e1e1e;
}}

.stat-row:first-child {{
  border-top: 1pt solid #1e1e1e;
}}

.stat-num {{
  font-size: 48pt;
  font-weight: 700;
  line-height: 1;
  min-width: 160pt;
}}

.stat-num.green {{ color: #00a84f; }}
.stat-num.yellow {{ color: #f5c518; }}
.stat-num.orange {{ color: #e07b39; }}

.stat-desc {{
  font-size: 15pt;
  font-weight: 400;
  color: #999;
  line-height: 1.4;
}}

/* spacer */
.spacer {{ flex: 1; }}

/* CTA */
.cta-block {{
  background: #0d0d0d;
  border: 1pt solid #1e1e1e;
  border-left: 3pt solid #00a84f;
  padding: 28pt 32pt;
  margin-bottom: 0;
}}

.cta-label {{
  font-size: 10pt;
  font-weight: 400;
  letter-spacing: 4pt;
  text-transform: uppercase;
  color: #555;
  margin-bottom: 10pt;
}}

.cta-url {{
  font-size: 18pt;
  font-weight: 700;
  color: #f0f0ee;
  letter-spacing: 0.5pt;
}}

/* rodapé */
.footer {{
  padding: 28pt 0 44pt 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

.author-name {{
  font-size: 13pt;
  font-weight: 700;
  color: #f0f0ee;
  letter-spacing: 1pt;
}}

.author-role {{
  font-size: 10pt;
  font-weight: 400;
  color: #555;
  margin-top: 4pt;
  letter-spacing: 0.5pt;
}}

.footer-badge {{
  font-size: 9pt;
  font-weight: 400;
  letter-spacing: 3pt;
  text-transform: uppercase;
  color: #333;
  text-align: right;
}}
</style>
</head>
<body>

<div class="top-bar"></div>

<div class="inner">

  <p class="kicker">Copa do Mundo 2026</p>

  <h1 class="headline">
    Quem vai<br>ganhar a<br><span>Copa?</span>
  </h1>

  <p class="subtitle">
    Rodei 100 mil simulações do torneio.<br>Os números dizem mais do que qualquer palpite.
  </p>

  <div class="divider"></div>

  <div class="stats">
    <div class="stat-row">
      <span class="stat-num green">8,7%</span>
      <span class="stat-desc">de chance do Brasil<br>ser hexacampeão</span>
    </div>
    <div class="stat-row">
      <span class="stat-num yellow">23%</span>
      <span class="stat-desc">de chance do Brasil<br>chegar à final</span>
    </div>
    <div class="stat-row">
      <span class="stat-num orange">3%</span>
      <span class="stat-desc">de chance de ter<br>Brasil x Argentina na final</span>
    </div>
  </div>

  <div class="spacer"></div>

  <div class="cta-block">
    <p class="cta-label">Acesse o projeto</p>
    <p class="cta-url">romuloedu.github.io/quem-vai-ganhar</p>
  </div>

  <div class="footer">
    <div>
      <p class="author-name">Romulo Eduardo</p>
      <p class="author-role">Data Science &amp; Analytics · USP/Esalq</p>
    </div>
    <p class="footer-badge">Monte Carlo<br>+ Regressão Logística</p>
  </div>

</div>
</body>
</html>
"""

print("Gerando PDF...")
HTML(string=HTML_STORY).write_pdf(OUT_PDF)
print(f"PDF gerado: {OUT_PDF}")

print("Convertendo para PNG...")
pages = convert_from_path(OUT_PDF, dpi=96)
pages[0].save(OUT_PNG, "PNG")
print(f"PNG gerado: {OUT_PNG}")
print(f"Tamanho: {pages[0].size[0]}x{pages[0].size[1]}px")
