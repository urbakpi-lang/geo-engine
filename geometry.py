"""
geo-engine · geometry.py — helper geometrie.
"""
import math

def square_polygon(lat: float, lng: float, area_ha: float | None):
    """Punto -> quadrato GeoJSON con l'area dichiarata (min ~50 m di raggio)."""
    area = area_ha if (area_ha and area_ha > 0) else 1.0
    r = max(math.sqrt(area * 10000 / math.pi), 50.0)            # metri
    dlat = r / 111320.0
    dlng = r / (111320.0 * max(math.cos(math.radians(lat)), 0.1))
    return {"type": "Polygon", "coordinates": [[
        [lng - dlng, lat - dlat], [lng + dlng, lat - dlat],
        [lng + dlng, lat + dlat], [lng - dlng, lat + dlat], [lng - dlng, lat - dlat]]]}

def centroid(geom: dict):
    if geom["type"] == "Point":
        return geom["coordinates"][0], geom["coordinates"][1]
    ring = geom["coordinates"][0]
    xs = [c[0] for c in ring]; ys = [c[1] for c in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)

def as_polygon(geom: dict, area_ha: float | None = None):
    """Normalizza a Polygon: i punti vengono bufferati."""
    if geom["type"] == "Point":
        lng, lat = geom["coordinates"][0], geom["coordinates"][1]
        return square_polygon(lat, lng, area_ha)
    return geom
