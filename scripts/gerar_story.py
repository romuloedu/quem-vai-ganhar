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
  display: flex;
  flex-direction: column;
}}

/* barra verde topo */
.top-bar {{
  width: 100%;
  height: 5pt;
  background: #00a84f;
  flex-shrink: 0;
}}

/* zona superior: kicker + intro + número */
.zone-top {{
  flex: 0 0 auto;
  padding: 52pt 60pt 0 60pt;
}}

.kicker {{
  font-size: 13pt;
  font-weight: 400;
  letter-spacing: 6pt;
  text-transform: uppercase;
  color: #00a84f;
  margin-bottom: 24pt;
}}

.intro {{
  font-size: 24pt;
  font-weight: 400;
  color: #777;
  line-height: 1.45;
  margin-bottom: 52pt;
}}

.number-label {{
  font-size: 14pt;
  font-weight: 400;
  letter-spacing: 3pt;
  text-transform: uppercase;
  color: #444;
  margin-bottom: 4pt;
}}

.number-hero {{
  line-height: 0.85;
  margin-bottom: 16pt;
}}

.number-big {{
  font-size: 260pt;
  font-weight: 700;
  color: #f5c518;
  letter-spacing: -6pt;
}}

.number-unit {{
  font-size: 90pt;
  font-weight: 700;
  color: #f5c518;
}}

.number-context {{
  font-size: 26pt;
  font-weight: 400;
  color: #888;
  line-height: 1.45;
  max-width: 650pt;
}}

.number-context strong {{
  color: #f0f0ee;
  font-weight: 700;
}}

/* espaçador flexível entre zonas */
.flex-gap {{ flex: 1; }}

/* divisor */
.divider-zone {{
  flex: 0 0 auto;
  padding: 0 60pt;
}}

.divider {{
  width: 56pt;
  height: 4pt;
  background: #00a84f;
  margin-bottom: 44pt;
}}

/* zona inferior: pergunta grande */
.zone-bottom {{
  flex: 0 0 auto;
  padding: 0 60pt 0 60pt;
}}

.question {{
  font-size: 96pt;
  font-weight: 700;
  text-transform: uppercase;
  line-height: 0.9;
  color: #f0f0ee;
  letter-spacing: -1pt;
}}

.question span {{
  color: #f5c518;
}}

/* rodapé */
.footer {{
  flex: 0 0 auto;
  margin: 44pt 60pt 44pt 60pt;
  padding-top: 24pt;
  border-top: 1pt solid #1e1e1e;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}

.author-name {{
  font-size: 18pt;
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
  font-size: 11pt;
  font-weight: 400;
  letter-spacing: 3pt;
  text-transform: uppercase;
  color: #333;
  text-align: right;
  line-height: 1.7;
}}
</style>
</head>
<body>

<div class="top-bar"></div>

<div class="zone-top">
  <p class="kicker">Copa do Mundo 2026</p>
  <p class="intro">Rodei 100 mil simulações do torneio.<br>Um número me surpreendeu.</p>

  <p class="number-label">Chance do Brasil chegar à final</p>
  <div class="number-hero">
    <span class="number-big">23</span><span class="number-unit">%</span>
  </div>
  <p class="number-context">
    Mais do que <strong>França</strong> ou <strong>Espanha.</strong><br>
    Mas e a chance de ser campeão?<br>
    Essa é outra história.
  </p>
</div>

<div class="flex-gap"></div>

<div class="divider-zone">
  <div class="divider"></div>
</div>

<div class="zone-bottom">
  <p class="question">
    Quem vai<br>ganhar a<br><span>Copa?</span>
  </p>
</div>

<div class="footer">
  <div>
    <p class="author-name">Romulo Eduardo</p>
    <p class="author-role">Data Science &amp; Analytics · USP/Esalq</p>
  </div>
  <p class="footer-tag">Monte Carlo<br>Regressão Logística</p>
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
