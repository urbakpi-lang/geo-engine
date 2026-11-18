# geo-engine — la base trasversale

Un solo motore geospaziale: `analyze(geometria, ricetta)`. I servizi (EUDR, Agri, …)
chiamano il motore; i provider (Global Forest Watch, Copernicus/Sentinel Hub) stanno
dietro l'astrazione e si cambiano senza toccare i prodotti.

## Struttura
```
engine.py         registro ricette + analyze()
geometry.py       helper (buffer punti, centroide)
provider_gfw.py   provider deforestazione (GFW, gratis, token)
provider_cdse.py  provider ottico/NDVI (Copernicus CDSE / Sentinel Hub, gratis, OAuth)
recipes.py        le ricette: 'deforestation', 'ndvi' (+ qui ne aggiungi altre)
main.py           API HTTP: /analyze, /check (compat GroveProof), /recipes, /health
```

## Credenziali (gratuite)
- **GFW_API_KEY** — token Global Forest Watch (https://www.globalforestwatch.org/ → Data API). Per 'deforestation'.
- **CDSE_CLIENT_ID / CDSE_CLIENT_SECRET** — OAuth del Copernicus Data Space Ecosystem
  (https://dataspace.copernicus.eu/ → Sentinel Hub → crei un OAuth client, gratis). Per 'ndvi'.

## Avvio locale
```bash
cd geoengine
pip install -r requirements.txt
export GFW_API_KEY=... CDSE_CLIENT_ID=... CDSE_CLIENT_SECRET=...
uvicorn main:app --port 8000

# ricetta generica
curl -X POST localhost:8000/analyze -H "Content-Type: application/json" -d '{
  "recipe":"deforestation",
  "geometry":{"type":"Point","coordinates":[-62.55,-9.52]},
  "params":{"area_ha":20}
}'

# NDVI (Agri) su un poligono e un intervallo
curl -X POST localhost:8000/analyze -H "Content-Type: application/json" -d '{
  "recipe":"ndvi",
  "geometry":{"type":"Point","coordinates":[-93.6,42.0]},
  "params":{"area_ha":50,"start":"2023-05-01","end":"2023-09-30"}
}'

# compat sito GroveProof
curl -X POST localhost:8000/check -H "Content-Type: application/json" \
  -d '{"plots":[{"plot_id":"BRA-003","origine":"Brasile","lat":-9.52,"lng":-62.55,"area_ha":20}]}'
```

## Deploy (Render free, no carta)
Metti la cartella in un repo → Render → Blueprint (legge `render.yaml`) → incolli le chiavi.
L'URL risultante va in `groveproof.html` come `var API_URL = "..."` (usa `/check`).

## Aggiungere un servizio = aggiungere una ricetta
In `recipes.py`:
```python
@recipe("builtup")
def builtup(geometry, params):
    poly = as_polygon(geometry, params.get("area_ha"))
    ...  # nuovo evalscript CDSE o altro provider; stessa forma di output
```
Nessun nuovo backend: il motore e il deploy restano quelli. Così EUDR, Agri, alluvioni,
cantieri, acqua, incendi girano tutti sulla stessa base.

## Note oneste
- Scaffold: provata la struttura, ma valida le credenziali e il parsing della risposta
  Sentinel Hub (i path dei campi stats possono cambiare tra versioni).
- 'deforestation' usa tree cover loss come proxy post-2020 (MVP). Per rigore pieno
  (baseline JRC + TMF) aggiungi un provider Earth Engine dietro la stessa ricetta.
- Uso **commerciale**: verifica i termini/quote di GFW e CDSE prima di scalare.
