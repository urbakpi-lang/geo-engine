"""
geo-engine · main.py — API HTTP del motore.
  POST /analyze  {recipe, geometry, params}         -> ricetta generica
  POST /check    {plots:[{plot_id,origine,lat?,lng?,area_ha?,geometry?}], version?}  -> GroveProof/EUDR
                 version "v2" (default): ricetta eudr_v2 (baseline 2020, qualità dati, confidenza)
                 version "v1": vecchia ricetta 'deforestation'
  GET  /methodology -> fonti, soglie e limiti (pubblici)
  GET  /recipes  -> ricette disponibili
  GET  /health
Avvio: uvicorn main:app --port 8000
"""
import os
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
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
    plot_id: str
    origine: Optional[str] = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    area_ha: Optional[float] = None
    geometry: Optional[dict] = None      # Polygon/MultiPolygon GeoJSON (consigliato sopra 4 ha)

class CheckReq(BaseModel):
    plots: List[Plot]
    version: Optional[str] = "v2"

MAX_PLOTS = int(os.getenv("MAX_PLOTS", "200"))

@app.get("/recipes")
def recipes_list():
    return {"recipes": list_recipes()}

@app.get("/health")
def health():
    return {"ok": True, "recipes": list_recipes(),
            "gfw_key_set": bool(os.getenv("GFW_API_KEY", "").strip()),
            "cdse_set": bool(os.getenv("CDSE_CLIENT_ID") and os.getenv("CDSE_CLIENT_SECRET"))}

class LeadReq(BaseModel):
    email: str
    company: Optional[str] = ""

@app.post("/lead")
def lead(req: LeadReq):
    """Contatti dal modulo dei siti. Per ora finiscono nei Logs di Render (cerca '[lead]').
    Il disco del piano free non è persistente: per conservarli serve un foglio/DB esterno."""
    print("[lead] %s | %s" % (req.email, req.company or ""), flush=True)
    return {"ok": True}

@app.post("/analyze")
def analyze_ep(req: AnalyzeReq):
    try:
        return {"result": analyze(req.recipe, req.geometry, req.params or {})}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, "Errore provider: %s" % e)

def _check_v1(p: Plot):
    geom = {"type": "Point", "coordinates": [p.lng, p.lat]}
    r = analyze("deforestation", geom, {"area_ha": p.area_ha})
    return {"plot_id": p.plot_id, "origine": p.origine or "", "lon": r["lon"], "lat": r["lat"],
            "forest_ha_2020": None, "disturb_ha_post2020": r["disturb_ha_post2020"], "verdict": r["verdict"]}


def _check_v2(p: Plot):
    geom = p.geometry if p.geometry else {"type": "Point", "coordinates": [p.lng, p.lat]}
    r = analyze("eudr_v2", geom, {"area_ha": p.area_ha, "country": p.origine})
    return {"plot_id": p.plot_id, "origine": p.origine or "",
            "lon": r.get("lon"), "lat": r.get("lat"),
            "forest_ha_2020": r.get("forest2020_ha"), **{k: v for k, v in r.items() if k not in ("lon", "lat")}}


@app.post("/check")
def check(req: CheckReq):
    """GroveProof: verifica EUDR di ogni particella (in parallelo)."""
    if len(req.plots) > MAX_PLOTS:
        raise HTTPException(413, "Massimo %d particelle per richiesta." % MAX_PLOTS)
    fn = _check_v1 if (req.version or "v2") == "v1" else _check_v2

    def one(p: Plot):
        try:
            if p.geometry is None and (p.lat is None or p.lng is None) and fn is _check_v1:
                raise ValueError("coordinate mancanti")
            return fn(p)
        except Exception as e:
            print("[check] %s: %s" % (p.plot_id, e), flush=True)   # visibile nei Logs di Render
            return {"plot_id": p.plot_id, "origine": p.origine or "", "lon": p.lng, "lat": p.lat,
                    "forest_ha_2020": None, "disturb_ha_post2020": None, "verdict": "DATI_MANCANTI",
                    "confidence": "bassa", "reasons": ["Errore durante la verifica: riprova più tardi."],
                    "error": str(e)[:300]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        out = list(ex.map(one, req.plots))
    return {"results": out, "version": req.version or "v2",
            "disclaimer": "Evidenza a supporto della due diligence. I casi A_RISCHIO e a bassa confidenza "
                          "richiedono revisione umana. La responsabilità della DDS resta all'operatore."}


@app.get("/methodology")
def methodology():
    import recipes as R, country_risk
    return {
        "cutoff": "31/12/2020 (perdita conteggiata dal 2021 in poi)",
        "baseline_2020": "JRC Global Forest Cover 2020 (mappa di riferimento UE)",
        "loss": "UMD/Hansen Global Forest Change, 30 m, annuale",
        "drivers": "WRI / Google DeepMind, cause della perdita arborea",
        "country_risk": country_risk.SOURCE,
        "threshold": "perdita > %.1f ha o > %d%% della particella" % (R.THRESH_HA, int(R.THRESH_SHARE * 100)),
        "verdicts": {"OK": "nessuna perdita di foresta 2020 dopo il 2020",
                     "OK_NO_FOREST_2020": "nel 2020 non era foresta",
                     "A_RISCHIO": "perdita di foresta 2020 dopo il 2020: revisione umana",
                     "DATI_MANCANTI": "coordinate non valide o dati non disponibili"},
        "limits": ["Dati a 30 m: particelle sotto 0,5 ha e coltivazioni all'ombra possono dare falsi esiti.",
                   "Un punto senza poligono viene verificato come un'area attorno al punto.",
                   "È evidenza a supporto, non una certificazione legale."],
    }
