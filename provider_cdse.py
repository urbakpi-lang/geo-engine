"""
geo-engine · provider_cdse.py
Provider "ottico" via Copernicus Data Space Ecosystem (Sentinel Hub Statistical API).
Gratis (a quota), UE. Credenziali OAuth gratuite da CDSE:
  env CDSE_CLIENT_ID / CDSE_CLIENT_SECRET.
Calcola statistiche NDVI (Sentinel-2 L2A) su una geometria in un intervallo.
"""
import os
from sentinelhub import (SHConfig, SentinelHubStatistical, DataCollection,
                         Geometry, CRS)

def _config():
    c = SHConfig()
    c.sh_client_id = os.getenv("CDSE_CLIENT_ID")
    c.sh_client_secret = os.getenv("CDSE_CLIENT_SECRET")
    c.sh_base_url = "https://sh.dataspace.copernicus.eu"
    c.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    return c

NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{bands: ["B04","B08","dataMask"]}],
    output: [{id: "ndvi", bands: 1}, {id: "dataMask", bands: 1}]
  };
}
function evaluatePixel(s) {
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);
  return {ndvi: [ndvi], dataMask: [s.dataMask]};
}
"""

def ndvi_stats(polygon_geom: dict, start: str, end: str, interval_days: int = 30) -> dict:
    """Ritorna statistiche NDVI (mean, max) aggregate nell'intervallo. start/end = 'YYYY-MM-DD'."""
    cfg = _config()
    s2 = DataCollection.SENTINEL2_L2A.define_from("s2-cdse", service_url=cfg.sh_base_url)
    req = SentinelHubStatistical(
        aggregation=SentinelHubStatistical.aggregation(
            evalscript=NDVI_EVALSCRIPT,
            time_interval=(start, end),
            aggregation_interval=f"P{interval_days}D"),
        input_data=[SentinelHubStatistical.input_data(s2, maxcc=0.3)],
        geometry=Geometry(polygon_geom, crs=CRS.WGS84),
        config=cfg)
    data = req.get_data()[0]
    # estrai mean/max NDVI massimi sull'intervallo (il picco stagionale)
    means, maxs = [], []
    for item in data.get("data", []):
        st = (item.get("outputs", {}).get("ndvi", {}).get("bands", {}).get("B0", {}).get("stats", {}))
        if st:
            if st.get("mean") is not None: means.append(st["mean"])
            if st.get("max")  is not None: maxs.append(st["max"])
    return {"ndvi_mean": (max(means) if means else None),   # picco della media
            "ndvi_max":  (max(maxs)  if maxs  else None),
            "n_intervals": len(means)}


# ---------- Acqua / alluvione via Sentinel-1 (radar: vede attraverso le nuvole) ----------
WATER_EVALSCRIPT_S1 = """
//VERSION=3
function setup() {
  return {input: [{bands: ["VV","dataMask"]}],
          output: [{id: "water", bands: 1}, {id: "dataMask", bands: 1}]};
}
function evaluatePixel(s) {
  // VV (lineare) -> dB; l'acqua ha backscatter basso
  let db = 10 * Math.log(s.VV) / Math.LN10;
  let water = db < -17 ? 1 : 0;
  return {water: [water], dataMask: [s.dataMask]};
}
"""

def water_fraction_s1(polygon_geom: dict, start: str, end: str, interval_days: int = 30):
    """Massima frazione d'acqua osservata nella geometria sull'intervallo (proxy di esposizione)."""
    cfg = _config()
    s1 = DataCollection.SENTINEL1_IW.define_from("s1-cdse", service_url=cfg.sh_base_url)
    req = SentinelHubStatistical(
        aggregation=SentinelHubStatistical.aggregation(
            evalscript=WATER_EVALSCRIPT_S1,
            time_interval=(start, end),
            aggregation_interval=f"P{interval_days}D"),
        input_data=[SentinelHubStatistical.input_data(s1)],
        geometry=Geometry(polygon_geom, crs=CRS.WGS84),
        config=cfg)
    data = req.get_data()[0]
    fracs = []
    for item in data.get("data", []):
        st = (item.get("outputs", {}).get("water", {}).get("bands", {}).get("B0", {}).get("stats", {}))
        if st and st.get("mean") is not None:
            fracs.append(st["mean"])
    return max(fracs) if fracs else None
