"""
geo-engine · recipes.py
Le "ricette": una domanda di business → una funzione sopra i provider.
Aggiungere un servizio = aggiungere una ricetta qui. I servizi chiamano analyze().
"""
from engine import recipe
from geometry import as_polygon, centroid
import provider_gfw, provider_cdse

# ---------- Ricetta 1: DEFORESTAZIONE (EUDR / GroveProof) ----------
@recipe("deforestation")
def deforestation(geometry: dict, params: dict):
    """params: {area_ha?, cutoff_year=2021, thresh_ha=0.1}"""
    poly = as_polygon(geometry, params.get("area_ha"))
    loss = provider_gfw.tree_cover_loss_since(poly, params.get("cutoff_year", 2021))
    thresh = params.get("thresh_ha", 0.1)
    lon, lat = centroid(poly)
    return {"recipe": "deforestation",
            "disturb_ha_post2020": round(loss, 2),
            "verdict": "A_RISCHIO" if loss > thresh else "OK",
            "lon": round(lon, 5), "lat": round(lat, 5)}

# ---------- Ricetta 2: NDVI / stress colturale (Agri Index) ----------
@recipe("ndvi")
def ndvi(geometry: dict, params: dict):
    """params: {area_ha?, start, end, interval_days=30}"""
    poly = as_polygon(geometry, params.get("area_ha"))
    start = params.get("start"); end = params.get("end")
    if not (start and end):
        raise ValueError("ndvi richiede params.start e params.end ('YYYY-MM-DD')")
    stats = provider_cdse.ndvi_stats(poly, start, end, params.get("interval_days", 30))
    lon, lat = centroid(poly)
    return {"recipe": "ndvi", **stats, "lon": round(lon, 5), "lat": round(lat, 5)}

# ---------- Ricetta 3: ESPOSIZIONE ALLUVIONE (assicurazioni / banche) ----------
@recipe("flood")
def flood(geometry: dict, params: dict):
    """params: {area_ha?, start, end, interval_days=30}. Usa Sentinel-1 (radar)."""
    poly = as_polygon(geometry, params.get("area_ha"))
    start = params.get("start"); end = params.get("end")
    if not (start and end):
        raise ValueError("flood richiede params.start e params.end ('YYYY-MM-DD')")
    wf = provider_cdse.water_fraction_s1(poly, start, end, params.get("interval_days", 30))
    lon, lat = centroid(poly)
    level = "n/d" if wf is None else ("alta" if wf > 0.30 else "media" if wf > 0.05 else "bassa")
    return {"recipe": "flood",
            "water_fraction": (round(wf, 3) if wf is not None else None),
            "exposure": level, "lon": round(lon, 5), "lat": round(lat, 5)}

# ---------- Come aggiungere una ricetta (es. built-up / incendi) ----------
# @recipe("builtup")
# def builtup(geometry, params):
#     poly = as_polygon(geometry, params.get("area_ha"))
#     ...  # un nuovo evalscript CDSE o un altro provider, stessa forma di output
