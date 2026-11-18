"""
geo-engine · clients.py
Come i TRE prodotti si collegano allo STESSO motore. Un solo backend, tre servizi.
Avvia prima il motore:  uvicorn main:app --port 8000
Poi:  python clients.py
"""
import os, requests
ENGINE = os.getenv("ENGINE_URL", "http://localhost:8000")

def post(path, body):
    r = requests.post(ENGINE + path, json=body, timeout=120)
    r.raise_for_status()
    return r.json()

# ============ PRODOTTO 1 — EUDR / GroveProof (ricetta: deforestation) ============
# Il sito groveproof.html è GIÀ collegato: basta impostare in cima allo script
#     var API_URL = "<url-del-geo-engine>";
# e il sito chiama /check. Equivalente da codice:
def eudr_check(plots):
    return post("/check", {"plots": plots})

# ============ PRODOTTO 2 — Agri Risk Index (ricetta: ndvi) ============
# Indice 0–100 live per regione: chiama la ricetta 'ndvi' sul motore e normalizza.
def agri_index(regions, start, end):
    rows = []
    for rg in regions:
        res = post("/analyze", {"recipe": "ndvi",
                                 "geometry": {"type": "Point", "coordinates": [rg["lng"], rg["lat"]]},
                                 "params": {"area_ha": rg.get("area_ha", 5000), "start": start, "end": end}})["result"]
        rows.append({"region": rg["name"], "ndvi_mean": res.get("ndvi_mean")})
    vals = [r["ndvi_mean"] for r in rows if r["ndvi_mean"] is not None]
    lo, hi = (min(vals), max(vals)) if vals else (0, 1)
    for r in rows:
        v = r["ndvi_mean"]
        r["index_0_100"] = None if v is None else round(100 * (v - lo) / (hi - lo + 1e-9))
    return rows

# ============ PRODOTTO 3 — Rischio alluvione (ricetta: flood) ============
# Esposizione per asset: chiama la ricetta 'flood' sul motore.
def flood_exposure(assets, start, end):
    out = []
    for a in assets:
        res = post("/analyze", {"recipe": "flood",
                                "geometry": {"type": "Point", "coordinates": [a["lng"], a["lat"]]},
                                "params": {"area_ha": a.get("area_ha", 10), "start": start, "end": end}})["result"]
        out.append({"asset": a["name"], "exposure": res.get("exposure"), "water_fraction": res.get("water_fraction")})
    return out

if __name__ == "__main__":
    print("Ricette disponibili:", post("/health", {}) if False else requests.get(ENGINE + "/recipes").json())

    print("\n[1] EUDR —", eudr_check([
        {"plot_id": "BRA-003", "origine": "Brasile", "lat": -9.52, "lng": -62.55, "area_ha": 20}]))

    print("\n[2] Agri Index —", agri_index([
        {"name": "Iowa", "lat": 42.0, "lng": -93.6},
        {"name": "Illinois", "lat": 40.0, "lng": -89.0}], "2023-05-01", "2023-09-30"))

    print("\n[3] Flood —", flood_exposure([
        {"name": "Magazzino A", "lat": 45.44, "lng": 12.33}], "2023-10-01", "2023-11-30"))
