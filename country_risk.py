"""
geo-engine · country_risk.py
Classificazione ufficiale UE del rischio paese per l'EUDR
(Regolamento di esecuzione (UE) 2025/1093, 22 maggio 2025).
- ALTO: Bielorussia, Corea del Nord, Myanmar, Russia
- STANDARD: elenco sotto
- BASSO: tutti gli altri paesi
Da ricontrollare a ogni revisione della Commissione.
"""

HIGH = {"BLR", "PRK", "MMR", "RUS"}

STANDARD = {
    "AGO", "ARG", "BLZ", "BEN", "BOL", "BWA", "BRA", "BFA", "KHM", "CMR", "TCD", "COL",
    "CIV", "COD", "ECU", "SLV", "GNQ", "ERI", "ETH", "GMB", "GTM", "GIN", "GNB", "HTI",
    "HND", "IDN", "ISR", "LBR", "MWI", "MYS", "MRT", "MEX", "MOZ", "NAM", "NIC", "NER",
    "NGA", "PAK", "PAN", "PRY", "PER", "SEN", "SLE", "SOM", "SDN", "TZA", "UGA", "VEN",
    "ZMB", "ZWE",
}

SOURCE = "Regolamento di esecuzione (UE) 2025/1093"

# Nomi di paese (EN/DE/IT/ES/FR) -> ISO3, per i paesi d'origine del caffè e quelli a rischio.
_NAMES = {
    "BRA": ["brazil", "brasil", "brasilien", "brasile", "brésil"],
    "COL": ["colombia", "kolumbien", "colombie"],
    "ETH": ["ethiopia", "äthiopien", "aethiopien", "etiopia", "etiopía", "éthiopie"],
    "HND": ["honduras"],
    "PER": ["peru", "perù", "perú", "pérou"],
    "VNM": ["vietnam", "viet nam", "việt nam"],
    "UGA": ["uganda", "ouganda"],
    "IDN": ["indonesia", "indonesien", "indonésie"],
    "IND": ["india", "indien", "inde"],
    "GTM": ["guatemala"],
    "MEX": ["mexico", "mexiko", "messico", "méxico", "mexique"],
    "NIC": ["nicaragua"],
    "CRI": ["costa rica"],
    "KEN": ["kenya", "kenia"],
    "TZA": ["tanzania", "tansania", "tanzanie"],
    "RWA": ["rwanda", "ruanda"],
    "BDI": ["burundi"],
    "SLV": ["el salvador", "salvador"],
    "PNG": ["papua new guinea", "papua-neuguinea", "papua nuova guinea", "png"],
    "LAO": ["laos", "lao", "lao pdr"],
    "CIV": ["cote d'ivoire", "côte d'ivoire", "ivory coast", "elfenbeinküste", "costa d'avorio"],
    "CMR": ["cameroon", "kamerun", "camerun", "cameroun"],
    "ECU": ["ecuador", "équateur"],
    "BOL": ["bolivia", "bolivien", "bolivie"],
    "PAN": ["panama", "panamá"],
    "CHN": ["china", "cina", "chine"],
    "YEM": ["yemen", "jemen", "yémen"],
    "THA": ["thailand", "thailandia", "thaïlande"],
    "PHL": ["philippines", "philippinen", "filippine", "filipinas"],
    "COD": ["dr congo", "drc", "congo (drc)", "democratic republic of the congo", "rd congo", "kongo"],
    "MMR": ["myanmar", "burma", "birmania"],
    "JAM": ["jamaica", "jamaika", "giamaica"],
    "DOM": ["dominican republic", "dominikanische republik", "repubblica dominicana"],
    "HTI": ["haiti", "haïti"],
    "CUB": ["cuba", "kuba"],
    "VEN": ["venezuela"],
    "MWI": ["malawi"],
    "ZMB": ["zambia", "sambia"],
    "ZWE": ["zimbabwe", "simbabwe"],
    "MOZ": ["mozambique", "mosambik", "mozambico"],
    "MDG": ["madagascar", "madagaskar"],
    "TLS": ["timor-leste", "east timor", "osttimor", "timor est"],
    "NPL": ["nepal"],
    "USA": ["usa", "united states", "hawaii"],
    "AUS": ["australia", "australien"],
    "BLR": ["belarus", "weißrussland", "bielorussia"],
    "RUS": ["russia", "russland", "russian federation"],
    "PRK": ["north korea", "nordkorea", "corea del nord"],
}
NAME_TO_ISO3 = {n: iso for iso, names in _NAMES.items() for n in names}


def iso3_of(name: str | None) -> str | None:
    """Converte un nome di paese (o un codice ISO3) in ISO3. None se sconosciuto."""
    if not name:
        return None
    k = name.strip().lower()
    if len(k) == 3 and k.upper() in (HIGH | STANDARD | set(_NAMES)):
        return k.upper()
    return NAME_TO_ISO3.get(k)


def risk_of(iso3: str | None) -> str | None:
    """'alto' | 'standard' | 'basso' | None (paese sconosciuto)."""
    if not iso3:
        return None
    if iso3 in HIGH:
        return "alto"
    if iso3 in STANDARD:
        return "standard"
    return "basso"
