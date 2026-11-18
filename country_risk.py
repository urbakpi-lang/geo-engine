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


# Codici ISO 3166 numerici (restituiti da GFW/GADM) -> ISO3
NUMERIC_TO_ISO3 = {
    4: "AFG", 8: "ALB", 10: "ATA", 12: "DZA", 16: "ASM", 20: "AND", 24: "AGO", 28: "ATG", 31: "AZE",
    32: "ARG", 36: "AUS", 40: "AUT", 44: "BHS", 48: "BHR", 50: "BGD", 51: "ARM", 52: "BRB",
    56: "BEL", 60: "BMU", 64: "BTN", 68: "BOL", 70: "BIH", 72: "BWA", 74: "BVT", 76: "BRA",
    84: "BLZ", 86: "IOT", 90: "SLB", 92: "VGB", 96: "BRN", 100: "BGR", 104: "MMR", 108: "BDI",
    112: "BLR", 116: "KHM", 120: "CMR", 124: "CAN", 132: "CPV", 136: "CYM", 140: "CAF", 144: "LKA",
    148: "TCD", 152: "CHL", 156: "CHN", 158: "TWN", 162: "CXR", 166: "CCK", 170: "COL", 174: "COM",
    175: "MYT", 178: "COG", 180: "COD", 184: "COK", 188: "CRI", 191: "HRV", 192: "CUB", 196: "CYP",
    203: "CZE", 204: "BEN", 208: "DNK", 212: "DMA", 214: "DOM", 218: "ECU", 222: "SLV", 226: "GNQ",
    231: "ETH", 232: "ERI", 233: "EST", 234: "FRO", 238: "FLK", 239: "SGS", 242: "FJI", 246: "FIN",
    248: "ALA", 250: "FRA", 254: "GUF", 258: "PYF", 260: "ATF", 262: "DJI", 266: "GAB", 268: "GEO",
    270: "GMB", 275: "PSE", 276: "DEU", 288: "GHA", 292: "GIB", 296: "KIR", 300: "GRC", 304: "GRL",
    308: "GRD", 312: "GLP", 316: "GUM", 320: "GTM", 324: "GIN", 328: "GUY", 332: "HTI", 334: "HMD",
    336: "VAT", 340: "HND", 344: "HKG", 348: "HUN", 352: "ISL", 356: "IND", 360: "IDN", 364: "IRN",
    368: "IRQ", 372: "IRL", 376: "ISR", 380: "ITA", 384: "CIV", 388: "JAM", 392: "JPN", 398: "KAZ",
    400: "JOR", 404: "KEN", 408: "PRK", 410: "KOR", 414: "KWT", 417: "KGZ", 418: "LAO", 422: "LBN",
    426: "LSO", 428: "LVA", 430: "LBR", 434: "LBY", 438: "LIE", 440: "LTU", 442: "LUX", 446: "MAC",
    450: "MDG", 454: "MWI", 458: "MYS", 462: "MDV", 466: "MLI", 470: "MLT", 474: "MTQ", 478: "MRT",
    480: "MUS", 484: "MEX", 492: "MCO", 496: "MNG", 498: "MDA", 499: "MNE", 500: "MSR", 504: "MAR",
    508: "MOZ", 512: "OMN", 516: "NAM", 520: "NRU", 524: "NPL", 528: "NLD", 531: "CUW", 533: "ABW",
    534: "SXM", 535: "BES", 540: "NCL", 548: "VUT", 554: "NZL", 558: "NIC", 562: "NER", 566: "NGA",
    570: "NIU", 574: "NFK", 578: "NOR", 580: "MNP", 581: "UMI", 583: "FSM", 584: "MHL", 585: "PLW",
    586: "PAK", 591: "PAN", 598: "PNG", 600: "PRY", 604: "PER", 608: "PHL", 612: "PCN", 616: "POL",
    620: "PRT", 624: "GNB", 626: "TLS", 630: "PRI", 634: "QAT", 638: "REU", 642: "ROU", 643: "RUS",
    646: "RWA", 652: "BLM", 654: "SHN", 659: "KNA", 660: "AIA", 662: "LCA", 663: "MAF", 666: "SPM",
    670: "VCT", 674: "SMR", 678: "STP", 682: "SAU", 686: "SEN", 688: "SRB", 690: "SYC", 694: "SLE",
    702: "SGP", 703: "SVK", 704: "VNM", 705: "SVN", 706: "SOM", 710: "ZAF", 716: "ZWE", 724: "ESP",
    728: "SSD", 729: "SDN", 732: "ESH", 740: "SUR", 744: "SJM", 748: "SWZ", 752: "SWE", 756: "CHE",
    760: "SYR", 762: "TJK", 764: "THA", 768: "TGO", 772: "TKL", 776: "TON", 780: "TTO", 784: "ARE",
    788: "TUN", 792: "TUR", 795: "TKM", 796: "TCA", 798: "TUV", 800: "UGA", 804: "UKR", 807: "MKD",
    818: "EGY", 826: "GBR", 831: "GGY", 832: "JEY", 833: "IMN", 834: "TZA", 840: "USA", 850: "VIR",
    854: "BFA", 858: "URY", 860: "UZB", 862: "VEN", 876: "WLF", 882: "WSM", 887: "YEM", 894: "ZMB",
}


def iso3_from_numeric(v):
    try:
        return NUMERIC_TO_ISO3.get(int(v))
    except (TypeError, ValueError):
        s = str(v or "").strip().upper()
        return s if len(s) == 3 and s.isalpha() else None
