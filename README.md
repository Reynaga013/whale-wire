# Whale & Wire

Bot de seguimiento financiero: noticias + sentimiento por sector, movimientos
de mercado (EE.UU. y Europa) y holdings 13F de fondos institucionales
curados, publicados en un dashboard iOS-style vía Claude Artifact, con
alertas push cuando hay eventos notables.

Documentación completa (arquitectura, decisiones, UI) en el vault de
Obsidian del usuario, carpeta `Proyectos/Whale & Wire/`.

## Estructura
- `scripts/news_aggregator.py` — recolección de noticias vía RSS (Google
  News, MarketWatch, WSJ, Investing.com), cobertura EE.UU. + Europa +
  sectores GICS + cripto.
- `scripts/sentiment.py` — VADER + léxico financiero propio para puntuar
  sentimiento de cada noticia.
- `scripts/market_movers.py` — mayores subas/bajas/más activas en EE.UU.
  (Yahoo Finance screener) y Europa (universo curado vía chart endpoint).
- `scripts/sec13f.py` — holdings 13F-HR de fondos institucionales curados
  desde SEC EDGAR (nota: el campo `<value>` viene en dólares enteros, no en
  miles, desde el cambio de spec de la SEC ~2023).
- `scripts/pipeline.py` — orquestador: corre todo lo anterior, genera
  alertas (sentimiento extremo, movimiento de mercado fuerte, cambios 13F
  relevantes) y guarda `data/latest.json` + histórico + `data/13f_state.json`
  (estado para diffing entre corridas).
- `scripts/build_dashboard.py` (+ `dashboard_style.css`, `dashboard_app.js`)
  — genera `dashboard.html` autocontenido (app-shell iOS: tab bar, hero,
  segmentados, sheets) a partir de `data/latest.json`.
- `data/13f_state.json` — estado semilla de posiciones 13F para poder
  detectar altas/bajas/cambios en la primera corrida real.

## Uso (ejecutado automáticamente por una tarea programada)
```
pip install -r requirements.txt
python3 scripts/pipeline.py        # recolecta datos, guarda data/latest.json
python3 scripts/build_dashboard.py # genera dashboard.html
```
El dashboard resultante se publica/actualiza con el Artifact tool de Claude.

## Importante
Herramienta informativa, no asesoría financiera certificada. No ejecuta
operaciones reales. Los datos 13F siempre tienen hasta 45 días de retraso
respecto al cierre del trimestre.
