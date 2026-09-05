#!/usr/bin/env python3
"""
pipeline.py
Orquestador principal: corre el agregador de noticias, el motor de
sentimiento, el rastreador de movimientos de mercado y el rastreador de 13F,
y guarda un snapshot unificado en data/latest.json (+ copia histórica).

También calcula una lista de "alerts": eventos que ameritan notificación
push (sentimiento extremo, movimiento de mercado fuerte, nuevo filing 13F
con cambios relevantes).

Uso: python3 pipeline.py
Salida: imprime un resumen legible y dice si hay alerts (para que la sesión
programada decida si manda push notification).
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import news_aggregator as news_mod
import sentiment as sentiment_mod
import market_movers as movers_mod
import sec13f as sec13f_mod

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
LATEST_PATH = os.path.join(DATA_DIR, "latest.json")
FUND_STATE_PATH = os.path.join(DATA_DIR, "13f_state.json")

# Umbrales para generar alerts
SENTIMENT_ALERT_THRESHOLD = 0.5       # |compound| promedio por categoría
MOVER_ALERT_THRESHOLD_PCT = 8.0       # % de cambio para considerarlo notable
FUND_CHANGE_ALERT_PCT = 15.0          # % de cambio en valor de posición 13F

# Tope de holdings por fondo que se persisten en 13f_state.json. El estado se
# guarda en la base de datos del Artifact (límite ~256KB por documento) para
# sobrevivir entre corridas del scheduled task, así que no puede crecer sin
# límite — fondos como Renaissance Technologies reportan miles de posiciones.
# Se conservan las de mayor valor (las más relevantes para detectar cambios
# notables); las posiciones muy pequeñas se pierden del baseline de diff, lo
# cual es un costo aceptable para una señal aproximada.
MAX_STATE_HOLDINGS_PER_FUND = 250


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_fund_state():
    if os.path.exists(FUND_STATE_PATH):
        with open(FUND_STATE_PATH, "r") as f:
            return json.load(f)
    return {}


def save_fund_state(state):
    with open(FUND_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def run_news_and_sentiment(alerts):
    print("== Recolectando noticias ==")
    items = news_mod.collect_general_market_news()
    items += news_mod.collect_sector_news()  # todos los sectores por defecto
    items = news_mod.dedupe(items)
    print(f"  {len(items)} noticias únicas recolectadas")

    items = sentiment_mod.score_news_items(items)
    by_category = sentiment_mod.aggregate_sentiment(items, group_key="category")

    for category, agg in by_category.items():
        if abs(agg["avg_compound"]) >= SENTIMENT_ALERT_THRESHOLD and agg["n"] >= 3:
            alerts.append(
                f"Sentimiento {agg['label']} fuerte ({agg['avg_compound']}) en '{category}' "
                f"basado en {agg['n']} noticias"
            )

    return {"items": items, "sentiment_by_category": by_category}


def run_market_movers(alerts, news_items_accum):
    print("== Recolectando movimientos de mercado ==")
    us = movers_mod.fetch_us_movers()
    eu = movers_mod.fetch_eu_movers()
    all_movers = {**us, **eu}
    print(f"  US gainers/losers/active + EU gainers/losers listos")

    LABELS_ES = {
        "us_top_gainers": "mayores subas EE.UU.",
        "us_top_losers": "mayores bajas EE.UU.",
        "us_most_active": "más activas EE.UU.",
        "eu_top_gainers": "mayores subas Europa",
        "eu_top_losers": "mayores bajas Europa",
    }

    notable_symbols = []
    notable_info = {}
    for label, quotes in all_movers.items():
        if "gainers" not in label and "losers" not in label:
            continue
        friendly = LABELS_ES.get(label, label)
        for q in quotes[:5]:
            if abs(q.get("change_pct") or 0) >= MOVER_ALERT_THRESHOLD_PCT:
                alerts.append(f"{q['symbol']} se movió {q['change_pct']}% ({friendly})")
                if q["symbol"] not in notable_info:
                    notable_symbols.append(q["symbol"])
                    notable_info[q["symbol"]] = {
                        "symbol": q["symbol"],
                        "change_pct": q.get("change_pct"),
                        "label": friendly,
                        "price": q.get("price"),
                    }

    # "Radar de hoy": cruce entre movimiento de precio notable y las noticias
    # más recientes de ese mismo símbolo (con su sentimiento ya calculado).
    # Es puramente informativo -- muestra qué se movió y qué se dice de ello,
    # nunca una recomendación de compra/venta ni una sugerencia de "mejor
    # opción". Limitado a los 4 símbolos más notables para no saturar de
    # llamadas RSS por corrida.
    radar = []
    for symbol in notable_symbols[:4]:
        extra = news_mod.collect_ticker_news([symbol], max_per_ticker=3)
        extra = sentiment_mod.score_news_items(extra)
        news_items_accum.extend(extra)
        entry = dict(notable_info[symbol])
        entry["news"] = extra[:3]
        radar.append(entry)

    radar.sort(key=lambda r: abs(r.get("change_pct") or 0), reverse=True)

    return all_movers, radar


def run_13f(alerts):
    print("== Recolectando 13F de fondos institucionales ==")
    state = load_fund_state()
    snapshots = sec13f_mod.fetch_all_funds()
    new_state = dict(state)

    for snap in snapshots:
        fund = snap.get("fund")
        if "error" in snap:
            print(f"  [warn] {fund}: {snap['error']}")
            continue

        prev = state.get(fund)
        acc = snap.get("accession_number")
        print(f"  {fund}: filing {snap.get('filing_date')} ({snap.get('total_positions')} posiciones)")

        if prev and prev.get("accession_number") == acc:
            pass  # sin filing nuevo desde el último check
        else:
            if prev:
                diff = sec13f_mod.diff_holdings(
                    prev.get("holdings", []), snap.get("holdings", []), min_value_change_pct=FUND_CHANGE_ALERT_PCT
                )
                if diff["new_positions"]:
                    names = ", ".join(h["issuer"] for h in diff["new_positions"][:5])
                    alerts.append(f"{fund} abrió nueva(s) posición(es) 13F: {names}")
                if diff["closed_positions"]:
                    names = ", ".join(h["issuer"] for h in diff["closed_positions"][:5])
                    alerts.append(f"{fund} cerró posición(es) 13F: {names}")
                if diff["changed_positions"]:
                    for h in diff["changed_positions"][:5]:
                        alerts.append(f"{fund}: {h['issuer']} cambió {h['change_pct']}% en valor 13F")
                snap["diff_vs_previous"] = diff
            else:
                alerts.append(f"Primer snapshot 13F guardado para {fund} (filing {snap.get('filing_date')})")

            trimmed_holdings = sorted(
                snap.get("holdings", []), key=lambda h: h.get("value_usd") or 0, reverse=True
            )[:MAX_STATE_HOLDINGS_PER_FUND]
            new_state[fund] = {
                "accession_number": acc,
                "filing_date": snap.get("filing_date"),
                "holdings": trimmed_holdings,
            }

    save_fund_state(new_state)
    return snapshots


def run_pipeline():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    alerts = []

    news_data = run_news_and_sentiment(alerts)
    movers_data, radar_data = run_market_movers(alerts, news_data["items"])
    funds_data = run_13f(alerts)

    snapshot = {
        "generated_at": _now_iso(),
        "news": news_data,
        "market_movers": movers_data,
        "radar": radar_data,
        "funds_13f": funds_data,
        "alerts": alerts,
    }

    with open(LATEST_PATH, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(HISTORY_DIR, f"snapshot_{ts}.json"), "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    print("\n== RESUMEN ==")
    print(f"Noticias: {len(news_data['items'])}")
    print(f"Sectores con sentimiento agregado: {len(news_data['sentiment_by_category'])}")
    print(f"Fondos 13F procesados: {len(funds_data)}")
    print(f"Radar de hoy: {len(radar_data)} símbolos con movimiento + noticia")
    print(f"Alerts generadas: {len(alerts)}")
    for a in alerts:
        print(f"  - {a}")

    return snapshot


if __name__ == "__main__":
    run_pipeline()
