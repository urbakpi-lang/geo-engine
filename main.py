"""
geo-engine · main.py — API HTTP del motore.
  POST /analyze  {recipe, geometry, params}         -> ricetta generica
  POST /check    {plots:[{plot_id,origine,lat,lng,area_ha}]}  -> compat GroveProof/EUDR
  GET  /recipes  -> ricette disponibili
  GET  /health
Avvio: uvicorn main:app --port 8000
"""
import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import recipes                      # registra le ricette (import con effetto collaterale)
from engine import analyze, list_recipes

ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*").split(",")

app = FastAPI(title="geo-engine")
app.add_middleware(CORSMiddleware, allow_origins=ALLOW_ORIGINS, allow_methods=["*"], allow_headers=["*"])

class AnalyzeReq(BaseModel):
    recipe: str
    geometry: dict
    params: Optional[dict] = None

class Plot(BaseModel):
    plot_id: str; origine: Optional[str] = ""; lat: float; lng: float; area_ha: Optional[float] = None

class CheckReq(BaseModel):
    plots: List[Plot]

@app.get("/recipes")
def recipes_list():
    return {"recipes": list_recipes()}

@app.get("/health")
def health():
    return {"ok": True, "recipes": list_recipes()}

@app.post("/analyze")
def analyze_ep(req: AnalyzeReq):
    try:
        return {"result": analyze(req.recipe, req.geometry, req.params or {})}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, "Errore provider: %s" % e)

@app.post("/check")
def check(req: CheckReq):
    """Compat col sito GroveProof: applica la ricetta 'deforestation' a ogni particella."""
    out = []
    for p in req.plots:
        geom = {"type": "Point", "coordinates": [p.lng, p.lat]}
        try:
            r = analyze("deforestation", geom, {"area_ha": p.area_ha})
            out.append({"plot_id": p.plot_id, "origine": p.origine or "",
                        "lon": r["lon"], "lat": r["lat"], "forest_ha_2020": None,
                        "disturb_ha_post2020": r["disturb_ha_post2020"], "verdict": r["verdict"]})
        except Exception as e:
            out.append({"plot_id": p.plot_id, "origine": p.origine or "",
                        "lon": p.lng, "lat": p.lat, "forest_ha_2020": None,
                        "disturb_ha_post2020": None, "verdict": "DATI_MANCANTI"})
    return {"results": out,
            "disclaimer": "Evidenza a supporto. I casi A_RISCHIO richiedono revisione umana. Responsabilità DDS all'operatore."}
