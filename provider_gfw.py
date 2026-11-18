"""
geo-engine · provider_gfw.py
Provider "deforestazione" via API gratuita Global Forest Watch.
Serve solo un token GFW gratuito (env GFW_API_KEY).

NB: se la chiave GFW è stata creata con una lista di "domains", GFW accetta
la richiesta solo se l'header Origin corrisponde a uno di quei domini.
Le chiamate dal server (Render) non hanno Origin, quindi lo mandiamo
esplicitamente (env GFW_ORIGIN, default il sito GroveProof).

Dataset usati (tutti su data-api.globalforestwatch.org):
- umd_tree_cover_loss            perdita di copertura arborea per anno (Hansen, CC BY 4.0)
- is__jrc_global_forest_cover    mappa forestale 2020 di riferimento UE (JRC GFC2020)
- gadm_administrative_boundaries confini dei paesi (per il controllo del paese dichiarato)
- wri_google_tree_cover_loss_drivers  causa della perdita (WRI / Google DeepMind)
- wdpa_protected_areas__iucn_cat, is__landmark_ip_lc_and_indicative_poly  aree protette e terre indigene
Tutti interrogati sul dataset jrc_global_forest_cover/v2020.3 (layer verificati il 18/11/2026).
"""
import os
import requests

GFW_API_KEY = os.getenv("GFW_API_KEY", "").strip()
GFW_ORIGIN = os.getenv("GFW_ORIGIN", "https://groveproof.netlify.app").strip()
GFW_DATASET = os.getenv("GFW_DATASET", "umd_tree_cover_loss")
GFW_VERSION = os.getenv("GFW_VERSION", "v1.13")
BASE = "https://data-api.globalforestwatch.org"
# Dataset che contiene TUTTI i layer usati (JRC 2020, perdita per anno, cause, WDPA, LandMark, GADM)
PROFILE_DATASET = os.getenv("GFW_PROFILE_DATASET", "jrc_global_forest_cover")
PROFILE_VERSION = os.getenv("GFW_PROFILE_VERSION", "v2020.3")
# Base che copre TUTTA la terraferma (0 in mare): superficie, paese, aree protette, terre indigene.
# NB: umd_tree_cover_loss contiene solo i pixel con una perdita dal 2001, quindi non va bene come base.
LAND_DATASET = os.getenv("GFW_LAND_DATASET", "umd_land_cover")
LAND_VERSION = os.getenv("GFW_LAND_VERSION", "v2020")

DRIVERS = {
    1: "agricoltura permanente", 2: "estrazione mineraria/energia", 3: "agricoltura itinerante",
    4: "taglio forestale", 5: "incendio", 6: "insediamenti e infrastrutture", 7: "disturbi naturali",
}
DEFOREST_DRIVERS = {1, 2, 6}   # conversione permanente = deforestazione vera e propria


class GFWError(RuntimeError):
    pass


def _headers():
    if not GFW_API_KEY:
        raise GFWError("GFW_API_KEY non impostata su Render")
    h = {"x-api-key": GFW_API_KEY, "Content-Type": "application/json"}
    if GFW_ORIGIN:
        h["Origin"] = GFW_ORIGIN
    return h


def query(sql: str, geometry: dict, dataset: str = None, version: str = None, timeout: int = 60):
    """Query SQL su un dataset GFW, limitata alla geometria. Ritorna la lista di righe."""
    url = f"{BASE}/dataset/{dataset or GFW_DATASET}/{version or GFW_VERSION}/query/json"
    r = requests.post(url, headers=_headers(), json={"sql": sql, "geometry": geometry}, timeout=timeout)
    if r.status_code in (401, 403):
        raise GFWError("GFW ha rifiutato la chiave (HTTP %s): chiave scaduta/errata o dominio "
                       "non autorizzato (Origin=%s). Dettaglio: %s"
                       % (r.status_code, GFW_ORIGIN or "-", r.text[:200]))
    if r.status_code == 404 and dataset is None and version is None and GFW_VERSION != "v1.11":
        return query(sql, geometry, GFW_DATASET, "v1.11", timeout)   # versione che sappiamo funzionare
    if r.status_code >= 400:
        raise GFWError("GFW HTTP %s: %s" % (r.status_code, r.text[:300]))
    return (r.json() or {}).get("data") or []


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _sum_col(rows):
    """La colonna della somma ha nomi diversi a seconda della versione: prendi il primo numero 'area'."""
    for k in ("area__ha", "sum", "area_ha", "loss_ha"):
        if rows and k in rows[0]:
            return k
    return next((k for k in (rows[0] if rows else {}) if "area" in k or "sum" in k), "area__ha")


# ---------- v1 (compatibilità) ----------
def tree_cover_loss_since(polygon_geom: dict, cutoff_year: int = 2021) -> float:
    """Ettari di perdita di copertura arborea con anno >= cutoff."""
    rows = query("SELECT SUM(area__ha) AS loss_ha FROM results WHERE umd_tree_cover_loss__year >= %d"
                 % cutoff_year, polygon_geom)
    return _num(rows[0].get("loss_ha") if rows else 0)


# ---------- v2: profilo completo della particella ----------
def _jrc(sql, geom):
    """Dataset JRC 2020: contiene SOLO i pixel che erano foresta nel 2020.
    Al suo interno l'anno di perdita Hansen è codificato 1..24 (= 2001..2024)."""
    return query(sql, geom, PROFILE_DATASET, PROFILE_VERSION)


def plot_profile(polygon_geom: dict, cutoff_year: int = 2021) -> dict:
    """
    Raccoglie tutto ciò che serve al verdetto EUDR (query verificate sui dati reali il 18/11/2026).
    Ogni parte è indipendente: se una fallisce, le altre restano e l'errore finisce in 'errors'.
    """
    from concurrent.futures import ThreadPoolExecutor
    import country_risk
    g = polygon_geom
    land = lambda sql: query(sql, g, LAND_DATASET, LAND_VERSION)
    jobs = {
        "land": lambda: land("SELECT SUM(area__ha) FROM results"),
        "loss_years": lambda: query("SELECT umd_tree_cover_loss__year, SUM(area__ha) FROM results "
                                    "GROUP BY umd_tree_cover_loss__year", g),
        "forest": lambda: _jrc("SELECT SUM(area__ha) FROM results", g),
        "loss_forest": lambda: _jrc("SELECT SUM(area__ha) FROM results WHERE umd_tree_cover_loss__year >= %d"
                                    % (cutoff_year - 2000), g),
        "country": lambda: land("SELECT gadm_administrative_boundaries__adm0, SUM(area__ha) FROM results "
                                "GROUP BY gadm_administrative_boundaries__adm0"),
        "drivers": lambda: query("SELECT wri_google_tree_cover_loss_drivers__category, SUM(area__ha) FROM results "
                                 "WHERE umd_tree_cover_loss__year >= %d "
                                 "GROUP BY wri_google_tree_cover_loss_drivers__category" % cutoff_year, g),
        "wdpa": lambda: land("SELECT wdpa_protected_areas__iucn_cat, SUM(area__ha) FROM results "
                             "GROUP BY wdpa_protected_areas__iucn_cat"),
        "indigenous": lambda: land("SELECT is__landmark_ip_lc_and_indicative_poly, SUM(area__ha) FROM results "
                                   "GROUP BY is__landmark_ip_lc_and_indicative_poly"),
    }
    res, errors = {}, []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {k: ex.submit(fn) for k, fn in jobs.items()}
        for k, f in futs.items():
            try:
                res[k] = f.result()
            except Exception as e:
                errors.append("%s: %s" % (k, str(e)[:160]))

    total = lambda rows: sum(_num(r.get(_sum_col(rows))) for r in rows) if rows else 0.0
    p = {"land_ha": None, "forest2020_ha": None, "loss_post2020_ha": None, "loss_in_forest2020_ha": None,
         "loss_by_year": {}, "country_iso3": None, "drivers_ha": {}, "protected_areas": None,
         "indigenous_lands": None, "errors": errors,
         "datasets": ["UMD/Hansen tree cover loss %s" % GFW_VERSION]}
    if "land" in res:
        p["land_ha"] = round(total(res["land"]), 3)
    if "loss_years" in res:
        rows = res["loss_years"]; col = _sum_col(rows); loss = 0.0
        for r in rows:
            try:
                y = int(r.get("umd_tree_cover_loss__year") or 0)
            except (TypeError, ValueError):
                continue
            if y >= cutoff_year:
                a = _num(r.get(col)); loss += a
                p["loss_by_year"][y] = round(a, 3)
        p["loss_post2020_ha"] = round(loss, 3)
    if "forest" in res:
        p["forest2020_ha"] = round(total(res["forest"]), 3)
        p["datasets"].append("JRC Global Forest Cover 2020 (%s)" % PROFILE_VERSION)
    if "loss_forest" in res:
        p["loss_in_forest2020_ha"] = round(total(res["loss_forest"]), 3)
    if res.get("country"):
        rows = res["country"]; col = _sum_col(rows)
        best = max(rows, key=lambda r: _num(r.get(col)))
        p["country_iso3"] = country_risk.iso3_from_numeric(best.get("gadm_administrative_boundaries__adm0"))
    if "drivers" in res:
        rows = res["drivers"]; col = _sum_col(rows)
        for r in rows:
            try:
                c = int(r.get("wri_google_tree_cover_loss_drivers__category"))
            except (TypeError, ValueError):
                continue
            name = DRIVERS.get(c, "altro")
            p["drivers_ha"][name] = round(p["drivers_ha"].get(name, 0) + _num(r.get(col)), 3)
        if rows:
            p["datasets"].append("WRI/Google DeepMind drivers of tree cover loss")

    def _inside(v):
        if v in (None, "", 0, "0", False, "false", "False", "None"):
            return False
        return True
    for key, src, field in (("protected_areas", "wdpa", "wdpa_protected_areas__iucn_cat"),
                            ("indigenous_lands", "indigenous", "is__landmark_ip_lc_and_indicative_poly")):
        if key and src in res:
            rows = res[src]; col = _sum_col(rows)
            p[key] = round(sum(_num(r.get(col)) for r in rows if _inside(r.get(field))), 3)
    return p
