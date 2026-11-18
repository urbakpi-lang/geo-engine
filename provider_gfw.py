"""
geo-engine · provider_gfw.py
Provider "deforestazione" via API gratuita Global Forest Watch (dati Hansen).
Nessun Google Cloud: serve solo un token GFW gratuito (env GFW_API_KEY).

NB: se la chiave GFW è stata creata con una lista di "domains", GFW accetta
la richiesta solo se l'header Origin corrisponde a uno di quei domini.
Le chiamate dal server (Render) non hanno Origin → 403. Per questo lo mandiamo
esplicitamente (env GFW_ORIGIN, default il sito GroveProof).
"""
import os, requests

GFW_API_KEY = os.getenv("GFW_API_KEY", "").strip()
GFW_ORIGIN = os.getenv("GFW_ORIGIN", "https://groveproof.netlify.app").strip()
GFW_DATASET = os.getenv("GFW_DATASET", "umd_tree_cover_loss")
GFW_VERSION = os.getenv("GFW_VERSION", "v1.11")   # disponibili anche v1.12, v1.13
BASE = "https://data-api.globalforestwatch.org"


class GFWError(RuntimeError):
    pass


def tree_cover_loss_since(polygon_geom: dict, cutoff_year: int = 2021) -> float:
    """Ettari di perdita di copertura arborea con anno >= cutoff (default 2021 = dopo il 2020)."""
    if not GFW_API_KEY:
        raise GFWError("GFW_API_KEY non impostata su Render")
    url = f"{BASE}/dataset/{GFW_DATASET}/{GFW_VERSION}/query/json"
    sql = f"SELECT SUM(area__ha) AS loss_ha FROM results WHERE umd_tree_cover_loss__year >= {cutoff_year}"
    headers = {"x-api-key": GFW_API_KEY, "Content-Type": "application/json"}
    if GFW_ORIGIN:
        headers["Origin"] = GFW_ORIGIN
    r = requests.post(url, headers=headers, json={"sql": sql, "geometry": polygon_geom}, timeout=60)
    if r.status_code in (401, 403):
        raise GFWError("GFW ha rifiutato la chiave (HTTP %s): chiave scaduta/errata o dominio "
                       "non autorizzato (Origin=%s). Dettaglio: %s"
                       % (r.status_code, GFW_ORIGIN or "-", r.text[:200]))
    r.raise_for_status()
    rows = (r.json() or {}).get("data") or []
    return float((rows[0].get("loss_ha") if rows else 0) or 0)
