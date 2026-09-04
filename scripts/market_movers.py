#!/usr/bin/env python3
"""
market_movers.py
Rastrea los movimientos de mercado más relevantes de EE.UU. (vía los screeners
públicos de Yahoo Finance: day_gainers, day_losers, most_actives) y de un
conjunto curado de grandes empresas europeas (DAX, CAC40, IBEX35, FTSE MIB,
AEX) calculado manualmente a partir del endpoint de chart de Yahoo, ya que
Yahoo no ofrece un screener público equivalente para Europa.
"""
import requests
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (InvestNewsBot research tool)"}

US_SCREENERS = {
    "us_top_gainers": "day_gainers",
    "us_top_losers": "day_losers",
    "us_most_active": "most_actives",
}

# Conjunto curado de large-caps europeos (símbolos Yahoo Finance con sufijo de bolsa)
EU_UNIVERSE = [
    # Alemania (DAX)
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MBG.DE", "BAS.DE", "BMW.DE", "VOW3.DE", "MUV2.DE", "AIR.DE",
    # Francia (CAC 40)
    "MC.PA", "OR.PA", "TTE.PA", "SAN.PA", "AI.PA", "BNP.PA", "SU.PA", "CS.PA", "DG.PA", "EL.PA",
    # España (IBEX 35)
    "SAN.MC", "ITX.MC", "IBE.MC", "BBVA.MC", "TEF.MC", "REP.MC", "FER.MC",
    # Italia (FTSE MIB)
    "ENEL.MI", "ISP.MI", "ENI.MI", "UCG.MI", "STLAM.MI",
    # Países Bajos (AEX)
    "ASML.AS", "SHELL.AS", "ADYEN.AS", "HEIA.AS",
]


def fetch_screener(screener_id, count=10, retries=2):
    url = (
        "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        f"?formatted=false&scrIds={screener_id}&count={count}&lang=en-US&region=US"
    )
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
                return [
                    {
                        "symbol": q.get("symbol"),
                        "name": q.get("shortName"),
                        "price": q.get("regularMarketPrice"),
                        "change_pct": round(q.get("regularMarketChangePercent", 0.0), 2),
                        "market_cap": q.get("marketCap"),
                    }
                    for q in quotes
                ]
        except Exception as e:
            if attempt == retries:
                print(f"  [warn] fallo screener {screener_id}: {e}")
        time.sleep(1)
    return []


def fetch_us_movers():
    result = {}
    for label, screener_id in US_SCREENERS.items():
        result[label] = fetch_screener(screener_id, count=10)
    return result


def _fetch_chart_quote(symbol, retries=1):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                meta = r.json()["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice")
                prev = meta.get("previousClose") or meta.get("chartPreviousClose")
                if price is not None and prev:
                    change_pct = round((price - prev) / prev * 100, 2)
                    return {
                        "symbol": symbol,
                        "name": meta.get("shortName") or meta.get("symbol"),
                        "price": price,
                        "change_pct": change_pct,
                    }
        except Exception:
            pass
        time.sleep(0.3)
    return None


def fetch_eu_movers(top_n=8):
    quotes = []
    for symbol in EU_UNIVERSE:
        q = _fetch_chart_quote(symbol)
        if q:
            quotes.append(q)
    quotes.sort(key=lambda x: x["change_pct"], reverse=True)
    gainers = quotes[:top_n]
    losers = sorted(quotes, key=lambda x: x["change_pct"])[:top_n]
    return {
        "eu_top_gainers": gainers,
        "eu_top_losers": losers,
        "eu_universe_size": len(quotes),
    }


def fetch_all_movers():
    result = fetch_us_movers()
    result.update(fetch_eu_movers())
    return result


if __name__ == "__main__":
    print("Probando rastreador de movimientos de mercado...")
    us = fetch_us_movers()
    for label, quotes in us.items():
        print(f"\n{label}:")
        for q in quotes[:3]:
            print(f"  {q['symbol']}: {q['change_pct']}%")

    print("\nProbando universo europeo (puede tardar ~15-20s)...")
    eu = fetch_eu_movers(top_n=5)
    print(f"Cotizaciones obtenidas: {eu['eu_universe_size']} / {len(EU_UNIVERSE)}")
    print("Top gainers EU:")
    for q in eu["eu_top_gainers"]:
        print(f"  {q['symbol']}: {q['change_pct']}%")
    print("Top losers EU:")
    for q in eu["eu_top_losers"]:
        print(f"  {q['symbol']}: {q['change_pct']}%")
