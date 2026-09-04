#!/usr/bin/env python3
"""
sec13f.py
Rastrea los reportes 13F-HR (holdings trimestrales) de una lista curada de
fondos institucionales usando la API pública de SEC EDGAR. Sin API key, pero
SEC exige un User-Agent identificable (política de acceso justo).

Notas importantes:
- Los 13F se publican con hasta 45 días de retraso respecto al cierre del
  trimestre, así que esto NUNCA es información en tiempo real.
- Un mismo emisor puede aparecer en varias líneas del info table (distintas
  sub-cuentas/managers); se agregan por (issuer, cusip).
"""
import requests
import time
import re
from xml.etree import ElementTree as ET

HEADERS = {"User-Agent": "InvestNewsBot research tool contact@example.com"}

# Fondos curados: nombre a mostrar -> término de búsqueda en EDGAR company search
CURATED_FUNDS = {
    "Berkshire Hathaway (Warren Buffett)": "berkshire hathaway inc",
    "Bridgewater Associates": "bridgewater associates",
    "Scion Asset Management (Michael Burry)": "scion asset management",
    "Pershing Square Capital (Bill Ackman)": "pershing square capital",
    "Third Point (Dan Loeb)": "third point llc",
    "Tiger Global Management": "tiger global management",
    "Renaissance Technologies": "renaissance technologies",
    "Duquesne Family Office (Druckenmiller)": "duquesne family office",
}

ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def find_latest_13f(company_query, retries=2):
    """Busca el CIK y el último filing 13F-HR de un fondo por nombre."""
    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        f"&company={requests.utils.quote(company_query)}&type=13F-HR&dateb=&owner=include"
        "&count=5&output=atom"
    )
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                break
        except Exception as e:
            if attempt == retries:
                print(f"  [warn] fallo búsqueda EDGAR para '{company_query}': {e}")
                return None
        time.sleep(1)
    else:
        return None

    text = r.text
    cik_match = re.search(r"<cik>(\d+)</cik>", text)
    if not cik_match:
        return None
    cik = cik_match.group(1)

    accession_match = re.search(r"<accession-number>([\d-]+)</accession-number>", text)
    date_match = re.search(r"<filing-date>([\d-]+)</filing-date>", text)
    if not accession_match:
        return None

    return {
        "cik": cik,
        "accession_number": accession_match.group(1),
        "filing_date": date_match.group(1) if date_match else None,
    }


def _find_info_table_doc(cik, accession_number, retries=2):
    acc_nodash = accession_number.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/index.json"
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                items = r.json().get("directory", {}).get("item", [])
                xml_files = [it for it in items if it["name"].endswith(".xml") and it["name"] != "primary_doc.xml"]
                if not xml_files:
                    return None
                # el information table suele ser el xml más grande (aparte de primary_doc)
                xml_files.sort(key=lambda it: int(it.get("size") or 0), reverse=True)
                return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{xml_files[0]['name']}"
        except Exception as e:
            if attempt == retries:
                print(f"  [warn] fallo index.json cik={cik}: {e}")
        time.sleep(1)
    return None


def fetch_holdings(doc_url, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.get(doc_url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                break
        except Exception as e:
            if attempt == retries:
                print(f"  [warn] fallo al obtener info table {doc_url}: {e}")
                return []
        time.sleep(1)
    else:
        return []

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return []

    # el namespace puede variar; detectarlo del tag raíz
    ns_match = re.match(r"\{(.*)\}", root.tag)
    ns = {"t": ns_match.group(1)} if ns_match else {}
    tag = lambda name: f"t:{name}" if ns else name

    holdings = {}
    for info in root.findall(f".//{tag('infoTable')}", ns):
        issuer = (info.findtext(tag("nameOfIssuer"), default="", namespaces=ns) or "").strip()
        cusip = (info.findtext(tag("cusip"), default="", namespaces=ns) or "").strip()
        value_node = info.findtext(tag("value"), default="0", namespaces=ns)
        shares_node = info.findtext(f"{tag('shrsOrPrnAmt')}/{tag('sshPrnamt')}", default="0", namespaces=ns)
        try:
            value = int(value_node or 0)
        except ValueError:
            value = 0
        try:
            shares = int(shares_node or 0)
        except ValueError:
            shares = 0

        key = (issuer, cusip)
        if key not in holdings:
            holdings[key] = {"issuer": issuer, "cusip": cusip, "value_usd": 0, "shares": 0}
        holdings[key]["value_usd"] += value
        holdings[key]["shares"] += shares

    result = list(holdings.values())
    result.sort(key=lambda h: h["value_usd"], reverse=True)
    return result


def fetch_fund_snapshot(fund_label, company_query):
    latest = find_latest_13f(company_query)
    if not latest:
        return {"fund": fund_label, "error": "no se encontró filing 13F-HR"}

    doc_url = _find_info_table_doc(latest["cik"], latest["accession_number"])
    if not doc_url:
        return {"fund": fund_label, "error": "no se encontró information table", **latest}

    holdings = fetch_holdings(doc_url)
    return {
        "fund": fund_label,
        "cik": latest["cik"],
        "accession_number": latest["accession_number"],
        "filing_date": latest["filing_date"],
        "holdings": holdings,
        "total_positions": len(holdings),
    }


def fetch_all_funds(funds=None):
    funds = funds or CURATED_FUNDS
    results = []
    for label, query in funds.items():
        snap = fetch_fund_snapshot(label, query)
        results.append(snap)
        time.sleep(0.5)  # ser buen ciudadano con la API de SEC
    return results


def diff_holdings(previous_holdings, current_holdings, min_value_change_pct=15):
    """Compara dos snapshots de holdings y devuelve nuevas posiciones, cerradas y cambios grandes."""
    prev_map = {(h["issuer"], h["cusip"]): h for h in previous_holdings}
    curr_map = {(h["issuer"], h["cusip"]): h for h in current_holdings}

    new_positions = [h for k, h in curr_map.items() if k not in prev_map]
    closed_positions = [h for k, h in prev_map.items() if k not in curr_map]
    changed = []
    for k, curr in curr_map.items():
        if k in prev_map:
            prev_val = prev_map[k]["value_usd"] or 1
            change_pct = (curr["value_usd"] - prev_val) / prev_val * 100
            if abs(change_pct) >= min_value_change_pct:
                changed.append({**curr, "change_pct": round(change_pct, 1)})

    return {"new_positions": new_positions, "closed_positions": closed_positions, "changed_positions": changed}


if __name__ == "__main__":
    print("Probando rastreador 13F con Berkshire Hathaway...")
    snap = fetch_fund_snapshot("Berkshire Hathaway (Warren Buffett)", CURATED_FUNDS["Berkshire Hathaway (Warren Buffett)"])
    print(f"CIK: {snap.get('cik')}, filing date: {snap.get('filing_date')}, posiciones: {snap.get('total_positions')}")
    for h in snap.get("holdings", [])[:5]:
        print(f"  {h['issuer']}: ${h['value_usd']:,} ({h['shares']:,} shares)")
