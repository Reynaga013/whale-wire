#!/usr/bin/env python3
"""
build_dashboard.py
Genera el dashboard HTML autocontenido a partir de data/latest.json.

"Whale & Wire" — app-shell estilo iOS: tab bar inferior, tarjeta hero,
controles segmentados, listas agrupadas y sheets modales. El renderizado de
contenido (noticias, movimientos, fondos, asesor) es 100% client-side en JS
a partir de un blob de datos embebido (window.__DATA__), inspirado en el
sistema de diseño documentado en la nota de Obsidian "Neto - UI y Apariencia".
"""
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
LATEST_PATH = os.path.join(BASE_DIR, "data", "latest.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "dashboard.html")
CSS_PATH = os.path.join(SCRIPTS_DIR, "dashboard_style.css")
JS_PATH = os.path.join(SCRIPTS_DIR, "dashboard_app.js")

MAX_HOLDINGS_PER_FUND = 20

ICONS = {
    "hoy": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
    "noticias": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h5"/>',
    "mercado": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "fondos": '<line x1="3" y1="22" x2="21" y2="22"/><line x1="6" y1="18" x2="6" y2="11"/><line x1="10" y1="18" x2="10" y2="11"/><line x1="14" y1="18" x2="14" y2="11"/><line x1="18" y1="18" x2="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
    "asesor": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
}
TAB_LABELS = {"hoy": "Hoy", "noticias": "Noticias", "mercado": "Mercado", "fondos": "Fondos", "asesor": "Asesor"}
TAB_ORDER = ["hoy", "noticias", "mercado", "fondos", "asesor"]


def svg(name, active=False):
    stroke = "currentColor"
    return (
        f'<svg viewBox="0 0 24 24" fill="none" stroke="{stroke}" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>'
    )


def build_tabbar():
    btns = []
    for i, tab in enumerate(TAB_ORDER):
        active = "active" if i == 0 else ""
        btns.append(
            f'<button class="tab-btn {active}" data-tab="{tab}">{svg(tab)}<span>{TAB_LABELS[tab]}</span></button>'
        )
    return "".join(btns)


def prep_data(raw):
    """Recorta los holdings de fondos gigantes para que el payload embebido sea razonable."""
    data = json.loads(json.dumps(raw))  # copia profunda barata
    for fund in data.get("funds_13f", []):
        if "holdings" in fund:
            fund["holdings"] = fund["holdings"][:MAX_HOLDINGS_PER_FUND]
        diff = fund.get("diff_vs_previous")
        if diff:
            for key in ("new_positions", "closed_positions", "changed_positions"):
                if key in diff:
                    diff[key] = diff[key][:10]
    # recortar resúmenes largos de noticias
    for it in data.get("news", {}).get("items", []):
        if "summary" in it:
            it["summary"] = it["summary"][:220]
    return data


def build_dashboard():
    with open(LATEST_PATH, "r") as f:
        raw = json.load(f)
    with open(CSS_PATH, "r") as f:
        css = f.read()
    with open(JS_PATH, "r") as f:
        js = f.read()

    data = prep_data(raw)
    generated_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(generated_at)
        generated_str = dt.strftime("%d %b, %H:%M UTC")
    except ValueError:
        generated_str = generated_at

    data_json = json.dumps(data, default=str, separators=(",", ":"))
    data_json = data_json.replace("</", "<\\/")  # evitar cierre prematuro de </script>

    tabbar_html = build_tabbar()

    html_out = f"""<title>Whale &amp; Wire</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Whale &amp; Wire">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&display=swap">
<style>
{css}
</style>

<div id="app">
  <header id="app-header">
    <div class="row">
      <h1>Whale &amp; Wire</h1>
      <span class="updated">{generated_str}</span>
    </div>
    <div class="subtitle">Noticias · Sentimiento · Mercado · Fondos 13F · Asesor</div>
  </header>

  <main>
    <section class="screen" data-tab="hoy" hidden>
      <div class="hero">
        <div class="glow"></div>
        <div class="label">Pulso del mercado</div>
        <div class="value serif" id="hero-value">—</div>
        <div class="sub" id="hero-sub">Cargando…</div>
      </div>
      <div class="stat-row">
        <div class="stat-chip"><div class="n tabular" id="stat-news">–</div><div class="l">Noticias</div></div>
        <div class="stat-chip"><div class="n tabular" id="stat-sectors">–</div><div class="l">Sectores</div></div>
        <div class="stat-chip"><div class="n tabular" id="stat-funds">–</div><div class="l">Fondos 13F</div></div>
        <div class="stat-chip"><div class="n tabular" id="stat-alerts">–</div><div class="l">Alertas</div></div>
      </div>
      <div class="section-title">Eventos destacados</div>
      <div class="list" id="alerts-list"></div>
      <div class="disclaimer" style="margin-top:18px"><span class="ic">ⓘ</span><div><b>Informativo, no asesoría financiera.</b> El sentimiento es una estimación automática y los datos 13F llegan con hasta 45 días de retraso respecto al cierre del trimestre.</div></div>
    </section>

    <section class="screen" data-tab="noticias" hidden>
      <div class="section-title" style="margin-top:4px">Sentimiento por sector</div>
      <div class="list" id="sentiment-list"></div>
      <div class="section-title">Noticias</div>
      <div class="chip-row" id="news-chip-row"></div>
      <div class="list" id="news-list"></div>
    </section>

    <section class="screen" data-tab="mercado" hidden>
      <div class="section-title" style="margin-top:4px">Región</div>
      <div class="segmented" id="region-segment">
        <button class="segment active" data-val="us">EE.UU.</button>
        <button class="segment" data-val="eu">Europa</button>
      </div>
      <div class="segmented" id="kind-segment"></div>
      <div class="list" id="movers-list"></div>
    </section>

    <section class="screen" data-tab="fondos" hidden>
      <div class="section-title" style="margin-top:4px">Fondos 13F rastreados</div>
      <div class="list" id="funds-list"></div>
      <div class="disclaimer" style="margin-top:16px"><span class="ic">ⓘ</span><div>Los holdings 13F reflejan posiciones con hasta 45 días de retraso respecto al cierre del trimestre — nunca es información en tiempo real.</div></div>
    </section>

    <section class="screen" data-tab="asesor" hidden>
      <div class="section-title" style="margin-top:4px">¿Cuánto quieres invertir?</div>
      <input class="text-field" id="amount-input" type="text" inputmode="decimal" placeholder="Ej. 5000 (opcional)">
      <div class="field-label">Horizonte temporal</div>
      <div class="segmented" id="horizon-segment">
        <button class="segment" data-val="lt2">&lt;2a</button>
        <button class="segment" data-val="2a5">2-5a</button>
        <button class="segment active" data-val="5a10">5-10a</button>
        <button class="segment" data-val="10p">10a+</button>
      </div>
      <div class="field-label">Tolerancia al riesgo</div>
      <div class="segmented" id="risk-segment">
        <button class="segment" data-val="conservador">Conservador</button>
        <button class="segment active" data-val="moderado">Moderado</button>
        <button class="segment" data-val="agresivo">Agresivo</button>
      </div>
      <div class="section-title">Fondo de emergencia</div>
      <div class="toggle-row">
        <div><div class="t">Ya tengo fondo de emergencia</div><div class="d">3-6 meses de gastos guardados aparte</div></div>
        <button class="switch on" id="emergency-switch"></button>
      </div>
      <button class="btn" id="calc-btn" style="margin-top:18px">Calcular guía</button>
      <div id="asesor-result" hidden style="margin-top:20px"></div>
    </section>
  </main>

  <nav id="tabbar">{tabbar_html}</nav>

  <div class="sheet-backdrop" id="sheet-backdrop"></div>
  <div class="sheet" id="fund-sheet">
    <div class="sheet-handle"></div>
    <div class="sheet-head"><h2 id="sheet-title">Fondo</h2><button class="sheet-close" id="sheet-close">✕</button></div>
    <div class="sheet-body" id="sheet-body"></div>
  </div>

  <footer class="legal">Whale &amp; Wire · fuentes: Google News, MarketWatch, WSJ, Investing.com, SEC EDGAR, Yahoo Finance</footer>
</div>

<script>
window.__DATA__ = {data_json};
</script>
<script>
{js}
</script>
"""

    with open(OUTPUT_PATH, "w") as f:
        f.write(html_out)

    print(f"Dashboard generado en {OUTPUT_PATH} ({len(html_out)/1024:.0f} KB)")
    return OUTPUT_PATH


if __name__ == "__main__":
    build_dashboard()
