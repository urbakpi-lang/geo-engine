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

# ---------- Ricetta 1b: EUDR v2 (GroveProof) ----------
import country_risk, quality
from messages import t, driver_name
from datetime import date

THRESH_HA = 0.1          # sotto questa soglia la perdita è rumore del dato a 30 m
THRESH_SHARE = 0.01      # ...oppure meno dell'1% della particella

_CACHE: dict = {}        # stessa particella verificata da più torrefazioni = un solo calcolo


@recipe("eudr_v2")
def eudr_v2(geometry: dict, params: dict):
    """
    Verifica EUDR completa di una particella.
    geometry: Point o Polygon/MultiPolygon GeoJSON.
    params: {area_ha?, country?, cutoff_year=2021, lang='it'|'en'|'de'}
    Ritorna verdetto, confidenza (alta/media/bassa), motivazioni e dati di dettaglio.
    """
    declared_ha = params.get("area_ha")
    declared_country = params.get("country")
    cutoff = params.get("cutoff_year", 2021)
    lang = params.get("lang") or "it"
    W = lambda code, level, **kw: {"code": code, "level": level, "msg": t(code, lang, **kw)}
    reasons, issues = [], []

    # 1) qualità dei dati
    is_polygon = geometry.get("type") in ("Polygon", "MultiPolygon")
    if is_polygon:
        try:
            from shapely.geometry import shape
            c = shape(geometry).centroid
            lon, lat = c.x, c.y
        except Exception:
            lon, lat = float("nan"), float("nan")
    else:
        lon, lat = (list(geometry.get("coordinates") or []) + [None, None])[:2]
    issues += quality.check_point(lat, lon, check_precision=not is_polygon, lang=lang)
    if any(i["level"] == "errore" for i in issues):
        lon = lon if isinstance(lon, (int, float)) else 0.0
        lat = lat if isinstance(lat, (int, float)) else 0.0
    g_issues, poly_ha = quality.check_geometry(geometry if is_polygon else None, declared_ha, lang)
    issues += g_issues
    iso_declared = country_risk.iso3_of(declared_country)
    if declared_country and not iso_declared:
        issues.append(W("paese_sconosciuto", "avviso", name=declared_country))

    import math
    _r = lambda v: (round(float(v), 6) if isinstance(v, (int, float)) and not math.isnan(v) else None)
    base = {"recipe": "eudr_v2", "lon": _r(lon), "lat": _r(lat),
            "geometry_type": "poligono" if is_polygon else "punto",
            "area_ha_polygon": round(poly_ha, 2) if poly_ha else None,
            "country_declared": iso_declared,
            "country_risk": country_risk.risk_of(iso_declared),
            "country_risk_source": country_risk.SOURCE,
            "checked_on": date.today().isoformat()}
    if any(i["level"] == "errore" for i in issues):
        return {**base, "verdict": "DATI_MANCANTI", "confidence": "bassa", "issues": issues,
                "reasons": [i["msg"] for i in issues if i["level"] == "errore"],
                "forest2020_ha": None, "disturb_ha_post2020": None}

    # 2) profilo satellitare (con cache)
    poly = geometry if is_polygon else as_polygon(geometry, declared_ha)
    key = (str(poly["coordinates"])[:2000], cutoff)
    prof = _CACHE.get(key)
    if prof is None:
        prof = provider_gfw.plot_profile(poly, cutoff)
        if not prof["errors"] or prof.get("forest2020_ha") is not None:
            _CACHE[key] = prof
            if len(_CACHE) > 5000:
                _CACHE.pop(next(iter(_CACHE)))

    land, forest = prof.get("land_ha"), prof.get("forest2020_ha")
    loss, loss_f = prof.get("loss_post2020_ha"), prof.get("loss_in_forest2020_ha")

    # 3) controlli che dipendono dal satellite
    if land is not None and land <= 0.001:
        issues.append(W("fuori_terra", "errore"))
    real = prof.get("country_iso3")
    if real:
        base["country_detected"] = real
        if iso_declared and real != iso_declared:
            issues.append(W("paese_diverso", "avviso", decl=iso_declared, real=real))
        if not iso_declared:
            base["country_risk"] = country_risk.risk_of(real)
    if base.get("country_risk") == "alto":
        reasons.append(t("alto_rischio", lang))
    if prof.get("protected_areas"):
        issues.append(W("area_protetta", "avviso", ha=prof["protected_areas"]))
    if prof.get("indigenous_lands"):
        issues.append(W("terre_indigene", "avviso", ha=prof["indigenous_lands"]))

    out = {**base, "forest2020_ha": forest, "disturb_ha_post2020": loss,
           "loss_in_forest2020_ha": loss_f, "loss_by_year": prof.get("loss_by_year"),
           "drivers_ha": prof.get("drivers_ha"), "protected_ha": prof.get("protected_areas"),
           "indigenous_ha": prof.get("indigenous_lands"), "datasets": prof.get("datasets"),
           "provider_errors": prof.get("errors")}

    if any(i["level"] == "errore" for i in issues):
        return {**out, "verdict": "DATI_MANCANTI", "confidence": "bassa", "issues": issues,
                "reasons": [i["msg"] for i in issues if i["level"] == "errore"]}
    if loss is None:
        return {**out, "verdict": "DATI_MANCANTI", "confidence": "bassa", "issues": issues,
                "reasons": [t("sat_unavailable", lang)]}

    # 4) verdetto
    size = land or poly_ha or declared_ha or 1.0
    thresh = max(THRESH_HA, THRESH_SHARE * size)
    drivers = prof.get("drivers_ha") or {}
    main_driver = max(drivers, key=drivers.get) if drivers else None

    if forest is not None:                        # baseline JRC disponibile
        if forest <= thresh and loss <= thresh:
            verdict, conf = "OK_NO_FOREST_2020", "alta"
            reasons.append(t("no_forest_2020", lang))
        elif loss_f > thresh:
            verdict, conf = "A_RISCHIO", "alta"
            reasons.append(t("loss_forest", lang, ha=loss_f))
            if main_driver:
                reasons.append(t("driver", lang, name=driver_name(main_driver, lang)))
            if main_driver in ("incendio", "disturbi naturali"):
                conf = "media"
                reasons.append(t("natural_review", lang))
        elif loss > thresh:
            verdict, conf = "OK", "media"
            reasons.append(t("loss_outside", lang, ha=loss))
        else:
            verdict, conf = "OK", "alta"
            reasons.append(t("clean", lang))
    else:                                         # solo Hansen (ripiego)
        verdict = "A_RISCHIO" if loss > thresh else "OK"
        conf = "media"
        reasons.append(t("v1_loss", lang, ha=loss) if loss > thresh else t("v1_clean", lang))

    # 5) la confidenza scende con gli avvisi
    warn = [i for i in issues if i["level"] == "avviso"]
    if any(i["code"] in ("serve_poligono", "paese_diverso", "area_protetta", "terre_indigene") for i in warn):
        conf = {"alta": "media", "media": "bassa", "bassa": "bassa"}[conf]
    if not is_polygon:
        reasons.append(t("point_only", lang))
    return {**out, "verdict": verdict, "confidence": conf, "issues": issues, "reasons": reasons}


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
