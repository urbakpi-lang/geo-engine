"""
geo-engine · engine.py
Registro delle "ricette" + dispatcher analyze(geometria, ricetta).
I servizi (EUDR, Agri, ...) chiamano analyze(); non sanno quale provider c'è sotto.
"""
from typing import Callable, Dict, Any

RECIPES: Dict[str, Callable] = {}

def recipe(name: str):
    def deco(fn: Callable):
        RECIPES[name] = fn
        return fn
    return deco

def analyze(recipe_name: str, geometry: dict, params: dict | None = None) -> Any:
    """geometry = GeoJSON geometry (Polygon/MultiPolygon/Point)."""
    if recipe_name not in RECIPES:
        raise ValueError("Ricetta sconosciuta: %s. Disponibili: %s" % (recipe_name, list(RECIPES)))
    return RECIPES[recipe_name](geometry, params or {})

def list_recipes():
    return sorted(RECIPES.keys())
