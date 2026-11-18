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


def _issue(code, level, msg):
    return {"code": code, "level": level, "msg": msg}


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


def check_point(lat, lng, check_precision=True):
    out = []
    if lat is None or lng is None or (isinstance(lat, float) and math.isnan(lat)) or (isinstance(lng, float) and math.isnan(lng)):
        return [_issue("coord_mancanti", "errore", "Coordinate mancanti.")]
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        out.append(_issue("coord_fuori_range", "errore",
                          "Coordinate impossibili: latitudine tra -90 e 90, longitudine tra -180 e 180."))
        if -90 <= lng <= 90 and -180 <= lat <= 180:
            out.append(_issue("lat_lng_invertite", "avviso", "Latitudine e longitudine sembrano invertite."))
        return out
    if lat == 0 and lng == 0:
        out.append(_issue("coord_zero", "errore", "Coordinate 0,0: valore segnaposto, non una particella reale."))
    if abs(lat) > 30:
        out.append(_issue("fuori_fascia_caffe", "avviso",
                          "Il punto è fuori dalla fascia tropicale dove si coltiva il caffè: controlla le coordinate."))
    dec = lambda v: len(repr(float(v)).split(".")[1].rstrip("0")) if "." in repr(float(v)) else 0
    if check_precision and min(dec(lat), dec(lng)) < 4:
        out.append(_issue("precisione_bassa", "avviso",
                          "Meno di 4 decimali: la posizione è incerta di oltre 10 metri. TRACES ne chiede 6."))
    return out


def check_geometry(geom: dict | None, declared_ha: float | None):
    """Controlla un poligono GeoJSON e la regola dei 4 ettari."""
    out = []
    if geom is None:
        if declared_ha and declared_ha > FOUR_HA:
            out.append(_issue("serve_poligono", "avviso",
                              "Particella oltre 4 ha: l'EUDR richiede il poligono, non solo il punto."))
        return out, None
    try:
        g = shape(geom)
    except Exception:
        return [_issue("geometria_illeggibile", "errore", "Il poligono non è un GeoJSON valido.")], None
    if g.geom_type not in ("Polygon", "MultiPolygon", "Point"):
        return [_issue("geometria_tipo", "errore", "Sono accettati solo Point, Polygon e MultiPolygon.")], None
    if g.geom_type == "Point":
        return check_geometry(None, declared_ha)
    if not g.is_valid:
        out.append(_issue("poligono_non_valido", "errore",
                          "Poligono non valido (%s): TRACES lo rifiuterebbe." % explain_validity(g)))
    a = area_ha(geom)
    if declared_ha and a > 0:
        diff = abs(a - declared_ha) / max(declared_ha, 0.01)
        if diff > 0.25:
            out.append(_issue("area_incoerente", "avviso",
                              "Area dichiarata %.1f ha, area del poligono %.1f ha." % (declared_ha, a)))
    if a > 5000:
        out.append(_issue("poligono_enorme", "avviso", "Poligono oltre 5.000 ha: è davvero una sola particella?"))
    return out, a
