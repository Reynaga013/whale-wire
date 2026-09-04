#!/usr/bin/env python3
"""
sentiment.py
Puntúa el sentimiento de textos financieros combinando VADER (léxico general)
con un léxico financiero compacto estilo Loughran-McDonald (palabras que en
contexto financiero tienen una carga que VADER no capta bien, ej. "bearish",
"guidance cut", "beat estimates").
"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Extensión de léxico financiero (palabra -> ajuste de intensidad VADER, escala -4..+4)
FINANCE_LEXICON = {
    "bullish": 2.5, "bearish": -2.5, "rally": 2.0, "selloff": -2.5, "sell-off": -2.5,
    "beat estimates": 2.5, "missed estimates": -2.5, "beats expectations": 2.5,
    "misses expectations": -2.5, "guidance cut": -2.8, "raised guidance": 2.5,
    "downgrade": -2.2, "upgrade": 2.2, "layoffs": -2.0, "bankruptcy": -3.5,
    "default": -2.5, "surge": 2.2, "plunge": -2.8, "plummet": -2.8, "soar": 2.3,
    "crash": -3.0, "recession": -2.5, "recovery": 1.8, "record high": 2.5,
    "record low": -2.0, "all-time high": 2.5, "correction": -1.5, "volatility": -0.8,
    "outperform": 2.0, "underperform": -2.0, "short squeeze": 1.5, "buyback": 1.5,
    "dividend cut": -2.3, "dividend increase": 1.8, "profit warning": -2.8,
    "insider buying": 1.5, "insider selling": -1.2, "antitrust": -1.5,
    "stimulus": 1.5, "rate hike": -1.2, "rate cut": 1.3, "inflation": -1.0,
    "deflation": -1.0, "tariff": -1.3, "trade war": -2.0, "hack": -2.0,
    "data breach": -2.0, "fraud": -3.0, "investigation": -1.8, "lawsuit": -1.5,
    "settlement": 0.5, "acquisition": 1.5, "merger": 1.2, "ipo": 1.0,
    "delisting": -3.0, "restructuring": -1.0, "profit": 1.2, "loss": -1.5,
    "growth": 1.3, "expansion": 1.2, "contraction": -1.5,
    "beating estimates": 2.5, "beat expectations": 2.5, "topped estimates": 2.3,
    "exceeded expectations": 2.3, "missed expectations": -2.5, "profit warning": -2.8,
    "short seller": -1.0, "activist investor": 0.8, "stake increase": 1.3,
    "stake reduction": -1.0, "exits position": -0.8, "new position": 0.8,
}


def score_text(text):
    """Devuelve un dict con compound score (-1..1) y etiqueta."""
    if not text:
        return {"compound": 0.0, "label": "neutral"}

    vs = _analyzer.polarity_scores(text)
    compound = vs["compound"]

    text_lower = text.lower()
    adjust = 0.0
    hits = 0
    for phrase, weight in FINANCE_LEXICON.items():
        if phrase in text_lower:
            adjust += weight
            hits += 1

    if hits:
        # normalizar el ajuste léxico financiero a escala -1..1
        finance_score = max(-1.0, min(1.0, adjust / (hits * 3.0)))
        # el léxico financiero domina cuando hay coincidencias, porque VADER
        # no está afinado para jerga financiera (ej. confunde "beat estimates"
        # con "beat" en sentido de violencia)
        finance_weight = min(0.8, 0.45 + 0.15 * hits)
        compound = max(-1.0, min(1.0, finance_weight * finance_score + (1 - finance_weight) * compound))

    if compound >= 0.15:
        label = "positivo"
    elif compound <= -0.15:
        label = "negativo"
    else:
        label = "neutral"

    return {"compound": round(compound, 3), "label": label}


def score_news_items(items):
    """Añade 'sentiment' a cada item de noticia (título + resumen)."""
    for item in items:
        text = f"{item.get('title', '')}. {item.get('summary', '')}"
        item["sentiment"] = score_text(text)
    return items


def aggregate_sentiment(items, group_key="category"):
    """Agrega el sentimiento promedio por categoría/sector/ticker."""
    groups = {}
    for item in items:
        key = item.get(group_key, "unknown")
        s = item.get("sentiment", {}).get("compound", 0.0)
        groups.setdefault(key, []).append(s)

    result = {}
    for key, scores in groups.items():
        avg = sum(scores) / len(scores) if scores else 0.0
        if avg >= 0.15:
            label = "positivo"
        elif avg <= -0.15:
            label = "negativo"
        else:
            label = "neutral"
        result[key] = {"avg_compound": round(avg, 3), "label": label, "n": len(scores)}
    return result


if __name__ == "__main__":
    samples = [
        "Apple stock surges to record high after beating estimates",
        "Company files for bankruptcy after massive fraud investigation",
        "Fed holds interest rates steady, markets show little reaction",
        "Tech sector selloff deepens as guidance cut spooks investors",
    ]
    for s in samples:
        print(score_text(s), "|", s)
