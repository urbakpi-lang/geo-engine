"""
geo-engine · quality.py
Controllo qualità dei dati di geolocalizzazione, prima di qualsiasi analisi satellitare.
Restituisce una lista di problemi: {"code", "level": "errore"|"avviso", "msg"}.
Un "errore" blocca la verifica (esito DATI_MANCANTI); un "avviso" abbassa la confidenza.
"""
import math
from shapely.geometry import shape, Point
from shapely.validation import explain_validity

FOUR_HA = 4.0


from messages import t


def _issue(code, level, lang="it", **kw):
    return {"code": code, "level": level, "msg": t(code, lang, **kw)}


def area_ha(geom: dict) -> float:
    """Area approssimata in ettari (proiezione equirettangolare locale, ok per particelle agricole)."""
    g = shape(geom)
    if g.is_empty or g.geom_type == "Point":
        return 0.0
    lat0 = math.radians(g.centroid.y)
    kx, ky = 111320.0 * math.cos(lat0), 110540.0

    def proj(coords):
        return [((x * kx), (y * ky)) for x, y, *_ in coords]

    from shapely.geometry import Polygon, MultiPolygon
    polys = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
    tot = 0.0
    for p in polys:
        pp = Polygon(proj(p.exterior.coords), [proj(i.coords) for i in p.interiors])
        tot += pp.area
    return tot / 10000.0


def check_point(lat, lng, check_precision=True, lang="it"):
    out = []
    if lat is None or lng is None or (isinstance(lat, float) and math.isnan(lat)) or (isinstance(lng, float) and math.isnan(lng)):
        return [_issue("coord_mancanti", "errore", lang)]
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        out.append(_issue("coord_fuori_range", "errore", lang))
        if -90 <= lng <= 90 and -180 <= lat <= 180:
            out.append(_issue("lat_lng_invertite", "avviso", lang))
        return out
    if lat == 0 and lng == 0:
        out.append(_issue("coord_zero", "errore", lang))
    if abs(lat) > 30:
        out.append(_issue("fuori_fascia_caffe", "avviso", lang))
    dec = lambda v: len(repr(float(v)).split(".")[1].rstrip("0")) if "." in repr(float(v)) else 0
    if check_precision and min(dec(lat), dec(lng)) < 4:
        out.append(_issue("precisione_bassa", "avviso", lang))
    return out


def check_geometry(geom: dict | None, declared_ha: float | None, lang="it"):
    """Controlla un poligono GeoJSON e la regola dei 4 ettari."""
    out = []
    if geom is None:
        if declared_ha and declared_ha > FOUR_HA:
            out.append(_issue("serve_poligono", "avviso", lang))
        return out, None
    try:
        g = shape(geom)
    except Exception:
        return [_issue("geometria_illeggibile", "errore", lang)], None
    if g.geom_type not in ("Polygon", "MultiPolygon", "Point"):
        return [_issue("geometria_tipo", "errore", lang)], None
    if g.geom_type == "Point":
        return check_geometry(None, declared_ha, lang)
    if not g.is_valid:
        out.append(_issue("poligono_non_valido", "errore", lang, detail=explain_validity(g)))
    a = area_ha(geom)
    if declared_ha and a > 0:
        diff = abs(a - declared_ha) / max(declared_ha, 0.01)
        if diff > 0.25:
            out.append(_issue("area_incoerente", "avviso", lang, decl=declared_ha, poly=a))
    if a > 5000:
        out.append(_issue("poligono_enorme", "avviso", lang))
    return out, a
