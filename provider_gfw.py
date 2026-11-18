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
def _pq(sql, geom):
    return query(sql, geom, PROFILE_DATASET, PROFILE_VERSION)


def plot_profile(polygon_geom: dict, cutoff_year: int = 2021) -> dict:
    """
    Raccoglie in poche query tutto ciò che serve al verdetto EUDR.
    Ogni parte è indipendente: se una fallisce, le altre restano e l'errore è riportato in 'errors'.
    """
    p = {"land_ha": None, "forest2020_ha": None, "loss_post2020_ha": None,
         "loss_in_forest2020_ha": None, "loss_by_year": {}, "country_iso3": None,
         "drivers_ha": {}, "protected_areas": None, "indigenous_lands": None,
         "datasets": ["UMD Hansen tree cover loss %s" % GFW_VERSION], "errors": []}

    # 1) superficie, foresta 2020 (JRC), perdita per anno — una sola query raggruppata
    try:
        rows = _pq("SELECT is__jrc_global_forest_cover, umd_tree_cover_loss__year, SUM(area__ha) "
                   "FROM results GROUP BY is__jrc_global_forest_cover, umd_tree_cover_loss__year",
                   polygon_geom)
        p["debug_main"] = rows[:3]
        col = _sum_col(rows)
        land = forest = loss = loss_f = 0.0
        by_year = {}
        for r in rows:
            a = _num(r.get(col))
            is_f = r.get("is__jrc_global_forest_cover") in (True, 1, "true", "True")
            y = r.get("umd_tree_cover_loss__year")
            y = int(y) if y not in (None, "", 0, "0") else None
            land += a
            if is_f:
                forest += a
            if y and y >= cutoff_year:
                loss += a
                by_year[y] = round(by_year.get(y, 0) + a, 3)
                if is_f:
                    loss_f += a
        p.update(land_ha=round(land, 3), forest2020_ha=round(forest, 3), loss_post2020_ha=round(loss, 3),
                 loss_in_forest2020_ha=round(loss_f, 3), loss_by_year=by_year)
        p["datasets"].append("JRC Global Forest Cover 2020")
    except Exception as e:
        p["errors"].append("baseline 2020: %s" % e)
        try:
            p["loss_post2020_ha"] = round(tree_cover_loss_since(polygon_geom, cutoff_year), 3)
        except Exception as e2:
            p["errors"].append("perdita: %s" % e2)

    # 2) paese reale del punto (per il controllo del paese dichiarato)
    try:
        rows = _pq("SELECT gadm_administrative_boundaries__adm0, SUM(area__ha) FROM results "
                   "GROUP BY gadm_administrative_boundaries__adm0", polygon_geom)
        p["debug_country"] = rows[:3]
        col = _sum_col(rows)
        rows = [r for r in rows if r.get("gadm_administrative_boundaries__adm0")]
        if rows:
            best = max(rows, key=lambda r: _num(r.get(col)))
            v = str(best["gadm_administrative_boundaries__adm0"]).strip().upper()
            if len(v) == 3 and v.isalpha():
                p["country_iso3"] = v
    except Exception as e:
        p["errors"].append("paese: %s" % e)

    # 3) causa della perdita — solo se c'è perdita
    if (p["loss_post2020_ha"] or 0) > 0:
        try:
            rows = _pq("SELECT wri_google_tree_cover_loss_drivers__category, SUM(area__ha) FROM results "
                         "WHERE umd_tree_cover_loss__year >= %d "
                         "GROUP BY wri_google_tree_cover_loss_drivers__category" % cutoff_year, polygon_geom)
            col = _sum_col(rows)
            for r in rows:
                c = r.get("wri_google_tree_cover_loss_drivers__category")
                try:
                    c = int(c)
                except (TypeError, ValueError):
                    continue
                p["drivers_ha"][DRIVERS.get(c, "altro")] = round(
                    p["drivers_ha"].get(DRIVERS.get(c, "altro"), 0) + _num(r.get(col)), 3)
            p["datasets"].append("WRI/Google DeepMind drivers of tree cover loss")
        except Exception as e:
            p["errors"].append("cause: %s" % e)

    # 4) aree protette e terre indigene (segnali di legalità, facoltativi)
    for key, field in (("protected_areas", "wdpa_protected_areas__iucn_cat"),
                       ("indigenous_lands", "is__landmark_ip_lc_and_indicative_poly")):
        try:
            rows = _pq("SELECT %s, SUM(area__ha) FROM results GROUP BY %s" % (field, field), polygon_geom)
            col = _sum_col(rows)
            def _inside(v):
                if v in (True, 1, "true", "True"):
                    return True
                return isinstance(v, str) and v.strip() not in ("", "0", "false", "False", "None")
            inside = sum(_num(r.get(col)) for r in rows if _inside(r.get(field)))
            p[key] = round(inside, 3)
        except Exception as e:
            p["errors"].append("%s: %s" % (key, str(e)[:120]))

    return p
