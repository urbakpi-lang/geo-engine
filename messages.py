"""
geo-engine · messages.py — testi degli esiti in italiano, inglese e tedesco.
t(code, lang, **valori) restituisce il messaggio nella lingua richiesta (default: italiano).
"""

MSG = {
    "coord_mancanti": {"it": "Coordinate mancanti.", "en": "Coordinates missing.", "de": "Koordinaten fehlen."},
    "coord_fuori_range": {
        "it": "Coordinate impossibili: latitudine tra -90 e 90, longitudine tra -180 e 180.",
        "en": "Impossible coordinates: latitude must be between -90 and 90, longitude between -180 and 180.",
        "de": "Unmögliche Koordinaten: Breite zwischen -90 und 90, Länge zwischen -180 und 180."},
    "lat_lng_invertite": {"it": "Latitudine e longitudine sembrano invertite.",
                          "en": "Latitude and longitude look swapped.",
                          "de": "Breiten- und Längengrad scheinen vertauscht."},
    "coord_zero": {"it": "Coordinate 0,0: valore segnaposto, non una particella reale.",
                   "en": "Coordinates 0,0: a placeholder, not a real plot.",
                   "de": "Koordinaten 0,0: Platzhalter, kein echtes Flurstück."},
    "fuori_fascia_caffe": {
        "it": "Il punto è fuori dalla fascia tropicale dove si coltiva il caffè: controlla le coordinate.",
        "en": "The point is outside the tropical belt where coffee grows: check the coordinates.",
        "de": "Der Punkt liegt außerhalb des tropischen Kaffeegürtels: Koordinaten prüfen."},
    "precisione_bassa": {
        "it": "Meno di 4 decimali: la posizione è incerta di oltre 10 metri. TRACES ne chiede 6.",
        "en": "Fewer than 4 decimals: position uncertain by more than 10 m. TRACES asks for 6.",
        "de": "Weniger als 4 Nachkommastellen: Position auf über 10 m unsicher. TRACES verlangt 6."},
    "serve_poligono": {
        "it": "Particella oltre 4 ha: l'EUDR richiede il poligono, non solo il punto.",
        "en": "Plot above 4 ha: the EUDR requires a polygon, not just a point.",
        "de": "Flurstück über 4 ha: Die EUDR verlangt ein Polygon, nicht nur einen Punkt."},
    "geometria_illeggibile": {"it": "Il poligono non è un GeoJSON valido.", "en": "The polygon is not valid GeoJSON.",
                              "de": "Das Polygon ist kein gültiges GeoJSON."},
    "geometria_tipo": {"it": "Sono accettati solo Point, Polygon e MultiPolygon.",
                       "en": "Only Point, Polygon and MultiPolygon are accepted.",
                       "de": "Nur Point, Polygon und MultiPolygon werden akzeptiert."},
    "poligono_non_valido": {"it": "Poligono non valido ({detail}): TRACES lo rifiuterebbe.",
                            "en": "Invalid polygon ({detail}): TRACES would reject it.",
                            "de": "Ungültiges Polygon ({detail}): TRACES würde es ablehnen."},
    "area_incoerente": {"it": "Area dichiarata {decl:.1f} ha, area del poligono {poly:.1f} ha.",
                        "en": "Declared area {decl:.1f} ha, polygon area {poly:.1f} ha.",
                        "de": "Angegebene Fläche {decl:.1f} ha, Polygonfläche {poly:.1f} ha."},
    "poligono_enorme": {"it": "Poligono oltre 5.000 ha: è davvero una sola particella?",
                        "en": "Polygon over 5,000 ha: is this really a single plot?",
                        "de": "Polygon über 5.000 ha: Ist das wirklich ein einzelnes Flurstück?"},
    "paese_sconosciuto": {"it": "Paese «{name}» non riconosciuto: scrivilo in inglese o con il codice ISO.",
                          "en": "Country “{name}” not recognised: write it in English or as an ISO code.",
                          "de": "Land „{name}“ nicht erkannt: auf Englisch oder als ISO-Code angeben."},
    "fuori_terra": {"it": "Il punto cade in mare o fuori dai dati: controlla latitudine e longitudine.",
                    "en": "The point falls in the sea or outside the data: check latitude and longitude.",
                    "de": "Der Punkt liegt im Meer oder außerhalb der Daten: Breite und Länge prüfen."},
    "paese_diverso": {"it": "Paese dichiarato {decl}, ma le coordinate cadono in {real}.",
                      "en": "Declared country {decl}, but the coordinates fall in {real}.",
                      "de": "Angegebenes Land {decl}, die Koordinaten liegen aber in {real}."},
    "area_protetta": {"it": "{ha:.1f} ha della particella ricadono in un'area protetta: verifica la legalità.",
                      "en": "{ha:.1f} ha of the plot lie in a protected area: check legality.",
                      "de": "{ha:.1f} ha des Flurstücks liegen in einem Schutzgebiet: Legalität prüfen."},
    "terre_indigene": {"it": "{ha:.1f} ha ricadono in terre indigene o comunitarie: verifica i diritti sulla terra.",
                       "en": "{ha:.1f} ha lie on indigenous or community lands: check land rights.",
                       "de": "{ha:.1f} ha liegen auf indigenem oder Gemeinschaftsland: Landrechte prüfen."},
    "alto_rischio": {"it": "Paese ad alto rischio secondo la classificazione UE: serve due diligence rafforzata.",
                     "en": "High-risk country in the EU classification: enhanced due diligence needed.",
                     "de": "Hochrisikoland laut EU-Einstufung: verstärkte Sorgfaltspflicht nötig."},
    "no_forest_2020": {
        "it": "Nel 2020 la particella non era foresta (mappa JRC): non può esserci deforestazione dopo il 2020.",
        "en": "The plot was not forest in 2020 (JRC map): there can be no deforestation after 2020.",
        "de": "Das Flurstück war 2020 kein Wald (JRC-Karte): Entwaldung nach 2020 ist ausgeschlossen."},
    "loss_forest": {"it": "{ha:.2f} ha di foresta 2020 persi dopo il 2020.",
                    "en": "{ha:.2f} ha of 2020 forest lost after 2020.",
                    "de": "{ha:.2f} ha Wald (Stand 2020) nach 2020 verloren."},
    "driver": {"it": "Causa prevalente stimata: {name}.", "en": "Estimated main cause: {name}.",
               "de": "Geschätzte Hauptursache: {name}."},
    "natural_review": {
        "it": "Perdita forse naturale: serve revisione con immagine ad alta risoluzione.",
        "en": "Loss may be natural: review with high-resolution imagery needed.",
        "de": "Verlust möglicherweise natürlich: Prüfung mit hochauflösendem Bild nötig."},
    "loss_outside": {
        "it": "{ha:.2f} ha di perdita arborea dopo il 2020, ma fuori dalla foresta 2020 (per esempio potatura degli alberi d'ombra).",
        "en": "{ha:.2f} ha of tree-cover loss after 2020, but outside 2020 forest (e.g. pruning of shade trees).",
        "de": "{ha:.2f} ha Baumverlust nach 2020, aber außerhalb des Waldes von 2020 (z. B. Rückschnitt von Schattenbäumen)."},
    "clean": {"it": "Nessuna perdita di foresta dopo il 31/12/2020 (Hansen + JRC 2020).",
              "en": "No forest loss after 31/12/2020 (Hansen + JRC 2020).",
              "de": "Kein Waldverlust nach dem 31.12.2020 (Hansen + JRC 2020)."},
    "v1_loss": {"it": "{ha:.2f} ha di perdita arborea dopo il 2020.", "en": "{ha:.2f} ha of tree-cover loss after 2020.",
                "de": "{ha:.2f} ha Baumverlust nach 2020."},
    "v1_clean": {"it": "Nessuna perdita arborea dopo il 2020 (solo Hansen: baseline 2020 non disponibile).",
                 "en": "No tree-cover loss after 2020 (Hansen only: 2020 baseline unavailable).",
                 "de": "Kein Baumverlust nach 2020 (nur Hansen: Basis 2020 nicht verfügbar)."},
    "point_only": {
        "it": "Verificata un'area attorno al punto: con il poligono reale l'esito è più affidabile.",
        "en": "An area around the point was checked: the real polygon gives a more reliable result.",
        "de": "Geprüft wurde eine Fläche um den Punkt: Mit dem echten Polygon ist das Ergebnis zuverlässiger."},
    "sat_unavailable": {"it": "Dati satellitari non disponibili in questo momento: riprova più tardi.",
                        "en": "Satellite data unavailable right now: please try again later.",
                        "de": "Satellitendaten derzeit nicht verfügbar: bitte später erneut versuchen."},
    "check_error": {"it": "Errore durante la verifica: riprova più tardi.",
                    "en": "Error during the check: please try again later.",
                    "de": "Fehler bei der Prüfung: bitte später erneut versuchen."},
}

DRIVER_NAMES = {
    "agricoltura permanente": {"en": "permanent agriculture", "de": "dauerhafte Landwirtschaft"},
    "estrazione mineraria/energia": {"en": "mining/energy", "de": "Bergbau/Energie"},
    "agricoltura itinerante": {"en": "shifting cultivation", "de": "Wanderfeldbau"},
    "taglio forestale": {"en": "logging", "de": "Holzeinschlag"},
    "incendio": {"en": "wildfire", "de": "Waldbrand"},
    "insediamenti e infrastrutture": {"en": "settlements and infrastructure", "de": "Siedlungen und Infrastruktur"},
    "disturbi naturali": {"en": "natural disturbances", "de": "natürliche Störungen"},
}


def norm_lang(lang):
    return lang if lang in ("it", "en", "de") else "it"


def t(code, lang="it", **kw):
    m = MSG.get(code, {})
    s = m.get(norm_lang(lang)) or m.get("it") or code
    try:
        return s.format(**kw)
    except (KeyError, ValueError):
        return s


def driver_name(name, lang="it"):
    lang = norm_lang(lang)
    return name if lang == "it" else DRIVER_NAMES.get(name, {}).get(lang, name)
