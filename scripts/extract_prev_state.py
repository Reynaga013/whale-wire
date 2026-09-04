#!/usr/bin/env python3
"""
extract_prev_state.py
Extrae el bloque <script id="ww-state-13f" type="application/json"> del HTML
del dashboard PUBLICADO en la corrida anterior (obtenido vía Artifact action
"read") y lo escribe en data/13f_state.json como estado previo para
pipeline.py.

Este es el mecanismo de persistencia de estado entre corridas del scheduled
task: reemplaza a Artifact read_db/write_db (que resultó no confiable /
colgado cuando se invocó desde una sesión de trigger desatendida — ver nota
en la Arquitectura de Obsidian) y no depende de que el paso de git push de
vuelta a GitHub tenga éxito.

Uso: python3 extract_prev_state.py <ruta_al_html_previo>
  - Si el archivo no existe, o no contiene el bloque ww-state-13f, o el JSON
    es inválido: no hace nada y termina con código 0 (se trata como "sin
    estado previo", igual que la primera corrida — pipeline.py ya maneja
    data/13f_state.json ausente).
"""
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUND_STATE_PATH = os.path.join(BASE_DIR, "data", "13f_state.json")

BLOCK_RE = re.compile(
    r'<script id="ww-state-13f" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def main():
    if len(sys.argv) < 2:
        print("Uso: extract_prev_state.py <ruta_al_html_previo>")
        sys.exit(0)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"[extract_prev_state] {path} no existe — se trata como primera corrida (sin estado previo).")
        sys.exit(0)

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    m = BLOCK_RE.search(html)
    if not m:
        print("[extract_prev_state] No se encontró el bloque ww-state-13f en el HTML — sin estado previo.")
        sys.exit(0)

    raw = m.group(1).strip()
    # build_dashboard.py escapa "</" como "<\/" para no cerrar el <script>
    # prematuramente; hay que revertirlo antes de parsear JSON.
    raw = raw.replace("<\\/", "</")

    if not raw:
        print("[extract_prev_state] Bloque ww-state-13f vacío — sin estado previo.")
        sys.exit(0)

    try:
        state = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[extract_prev_state] JSON inválido en ww-state-13f ({e}) — se descarta, sin estado previo.")
        sys.exit(0)

    os.makedirs(os.path.dirname(FUND_STATE_PATH), exist_ok=True)
    with open(FUND_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    n_funds = len(state) if isinstance(state, dict) else 0
    print(f"[extract_prev_state] Estado previo recuperado: {n_funds} fondos -> {FUND_STATE_PATH}")


if __name__ == "__main__":
    main()
