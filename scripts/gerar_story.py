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

.top-bar {{
  width: 100%;
  height: 5pt;
  background: #00a84f;
  margin-top: 187pt;
  flex-shrink: 0;
}}

.inner {{
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 44pt 64pt 0 64pt;
  min-height: 0;
}}

/* kicker: verde, leitura fácil */
.kicker {{
  font-size: 14pt;
  font-weight: 400;
  letter-spacing: 6pt;
  text-transform: uppercase;
  color: #00a84f;
  margin-bottom: 20pt;
}}

/* intro: cinza claro suficiente para ler no fundo escuro */
.intro {{
  font-size: 23pt;
  font-weight: 400;
  color: #aaa;
  line-height: 1.45;
  margin-bottom: 44pt;
}}

/* label acima do número: um pouco mais claro que antes (#444 era ilegível) */
.number-label {{
  font-size: 14pt;
  font-weight: 400;
  letter-spacing: 3pt;
  text-transform: uppercase;
  color: #666;
  margin-bottom: 2pt;
}}

.number-hero {{
  line-height: 0.85;
  margin-bottom: 18pt;
}}

.number-big {{
  font-size: 240pt;
  font-weight: 700;
  color: #f5c518;
  letter-spacing: -6pt;
}}

.number-unit {{
  font-size: 84pt;
  font-weight: 700;
  color: #f5c518;
}}

/* contexto: cinza claro legível */
.number-context {{
  font-size: 25pt;
  font-weight: 400;
  color: #aaa;
  line-height: 1.45;
}}

.number-context strong {{
  color: #f0f0ee;
  font-weight: 700;
}}

.flex-gap {{ flex: 1; min-height: 24pt; }}

.divider {{
  width: 56pt;
  height: 4pt;
  background: #00a84f;
  margin-bottom: 32pt;
  flex-shrink: 0;
}}

.question {{
  font-size: 88pt;
  font-weight: 700;
  text-transform: uppercase;
  line-height: 0.9;
  color: #f0f0ee;
  letter-spacing: -1pt;
  flex-shrink: 0;
  margin-bottom: 0;
}}

.question span {{
  color: #f5c518;
}}

/* zona de etiqueta — espaço reservado para o link sticker do Instagram */
.cta-zone {{
  flex-shrink: 0;
  margin: 32pt 64pt 187pt 64pt;
  border: 1.5pt solid #2a2a2a;
  border-left: 3pt solid #00a84f;
  padding: 22pt 28pt;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16pt;
}}

.cta-text {{
  font-size: 20pt;
  font-weight: 400;
  color: #888;
  line-height: 1.4;
}}

.cta-text strong {{
  display: block;
  font-size: 22pt;
  font-weight: 700;
  color: #f0f0ee;
  margin-bottom: 4pt;
}}

.cta-arrow {{
  font-size: 32pt;
  font-weight: 700;
  color: #00a84f;
  flex-shrink: 0;
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

  <p class="number-label">Chance do Brasil chegar à final</p>
  <div class="number-hero">
    <span class="number-big">23</span><span class="number-unit">%</span>
  </div>

  <p class="number-context">
    Mais do que <strong>França</strong> ou <strong>Espanha.</strong><br>
    Mas e a chance de ser campeão?<br>
    Essa é outra história.
  </p>

  <div class="flex-gap"></div>

  <div class="divider"></div>

  <p class="question">
    Quem vai<br>ganhar a<br><span>Copa?</span>
  </p>
</div>

<div class="cta-zone">
  <div class="cta-text">
    <strong>Ver as previsões completas</strong>
    Toque na etiqueta para acessar
  </div>
  <div class="cta-arrow">&#8599;</div>
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
