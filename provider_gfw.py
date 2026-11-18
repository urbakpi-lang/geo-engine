"""
geo-engine · provider_gfw.py
Provider "deforestazione" via API gratuita Global Forest Watch (dati Hansen).
Nessun Google Cloud: serve solo un token GFW gratuito (env GFW_API_KEY).
"""
import os, requests

GFW_API_KEY = os.getenv("GFW_API_KEY")
GFW_DATASET = os.getenv("GFW_DATASET", "umd_tree_cover_loss")
GFW_VERSION = os.getenv("GFW_VERSION", "v1.11")   # verifica l'ultima su data-api.globalforestwatch.org
BASE = "https://data-api.globalforestwatch.org"

def tree_cover_loss_since(polygon_geom: dict, cutoff_year: int = 2021) -> float:
    """Ettari di perdita di copertura arborea con anno >= cutoff (default 2021 = dopo il 2020)."""
    if not GFW_API_KEY:
        raise RuntimeError("GFW_API_KEY non impostata")
    url = f"{BASE}/dataset/{GFW_DATASET}/{GFW_VERSION}/query/json"
    sql = f"SELECT SUM(area__ha) AS loss_ha FROM results WHERE umd_tree_cover_loss__year >= {cutoff_year}"
    r = requests.post(url, headers={"x-api-key": GFW_API_KEY, "Content-Type": "application/json"},
                      json={"sql": sql, "geometry": polygon_geom}, timeout=60)
    r.raise_for_status()
    rows = (r.json() or {}).get("data") or []
    return float((rows[0].get("loss_ha") if rows else 0) or 0)
