import base64, os
from weasyprint import HTML
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
}}

.top-bar {{
  width: 100%;
  height: 5pt;
  background: #00a84f;
}}

.inner {{
  padding: 64pt 60pt 0 60pt;
  display: flex;
  flex-direction: column;
  height: calc(1440pt - 5pt);
}}

.kicker {{
  font-size: 14pt;
  font-weight: 400;
  letter-spacing: 6pt;
  text-transform: uppercase;
  color: #00a84f;
  margin-bottom: 28pt;
  margin-top: 20pt;
}}

.intro {{
  font-size: 22pt;
  font-weight: 400;
  color: #888;
  line-height: 1.5;
  margin-bottom: 56pt;
}}

.number-block {{
  margin-bottom: 20pt;
}}

.number-label {{
  font-size: 16pt;
  font-weight: 400;
  letter-spacing: 2pt;
  text-transform: uppercase;
  color: #555;
  margin-bottom: 8pt;
}}

.number-big {{
  font-size: 220pt;
  font-weight: 700;
  line-height: 0.85;
  color: #f5c518;
  letter-spacing: -4pt;
}}

.number-unit {{
  font-size: 72pt;
  font-weight: 700;
  color: #f5c518;
  letter-spacing: -2pt;
}}

.number-context {{
  font-size: 26pt;
  font-weight: 400;
  color: #999;
  line-height: 1.4;
  margin-top: 24pt;
  max-width: 620pt;
}}

.number-context strong {{
  color: #f0f0ee;
  font-weight: 700;
}}

.divider {{
  width: 56pt;
  height: 4pt;
  background: #00a84f;
  margin: 52pt 0;
}}

.question {{
  font-size: 38pt;
  font-weight: 700;
  text-transform: uppercase;
  line-height: 1.05;
  color: #f0f0ee;
  max-width: 660pt;
}}

.question span {{
  color: #f5c518;
}}

.spacer {{ flex: 1; }}

.footer {{
  padding: 32pt 0 48pt 0;
  border-top: 1pt solid #1e1e1e;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

.author-name {{
  font-size: 17pt;
  font-weight: 700;
  color: #f0f0ee;
}}

.author-role {{
  font-size: 13pt;
  font-weight: 400;
  color: #555;
  margin-top: 5pt;
}}

.footer-tag {{
  font-size: 12pt;
  font-weight: 400;
  letter-spacing: 3pt;
  text-transform: uppercase;
  color: #333;
  text-align: right;
  line-height: 1.6;
}}
</style>
</head>
<body>

<div class="top-bar"></div>

<div class="inner">

  <p class="kicker">Copa do Mundo 2026</p>

  <p class="intro">
    Rodei 100 mil simulações do torneio.<br>Um número me surpreendeu.
  </p>

  <div class="number-block">
    <p class="number-label">Chance do Brasil chegar à final</p>
    <div>
      <span class="number-big">23</span><span class="number-unit">%</span>
    </div>
  </div>

  <p class="number-context">
    Mais do que <strong>França</strong> ou <strong>Espanha.</strong><br>
    Mas e a chance de ser campeão?<br>Essa é outra história.
  </p>

  <div class="divider"></div>

  <p class="question">
    Quem vai<br>ganhar a<br><span>Copa?</span>
  </p>

  <div class="spacer"></div>

  <div class="footer">
    <div>
      <p class="author-name">Romulo Eduardo</p>
      <p class="author-role">Data Science &amp; Analytics · USP/Esalq</p>
    </div>
    <p class="footer-tag">Monte Carlo<br>Regressão Logística</p>
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
