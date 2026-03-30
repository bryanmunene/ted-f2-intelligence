from __future__ import annotations

ALPHA2_TO_TED_COUNTRY: dict[str, str] = {
    "AT": "AUT",
    "BE": "BEL",
    "BG": "BGR",
    "HR": "HRV",
    "CY": "CYP",
    "CZ": "CZE",
    "DK": "DNK",
    "EE": "EST",
    "FI": "FIN",
    "FR": "FRA",
    "DE": "DEU",
    "GR": "GRC",
    "EL": "GRC",
    "HU": "HUN",
    "IE": "IRL",
    "IT": "ITA",
    "LV": "LVA",
    "LT": "LTU",
    "LU": "LUX",
    "MT": "MLT",
    "NL": "NLD",
    "PL": "POL",
    "PT": "PRT",
    "RO": "ROU",
    "SK": "SVK",
    "SI": "SVN",
    "ES": "ESP",
    "SE": "SWE",
    "NO": "NOR",
    "IS": "ISL",
    "LI": "LIE",
    "CH": "CHE",
    "GB": "GBR",
    "UK": "GBR",
    "AL": "ALB",
    "BA": "BIH",
    "ME": "MNE",
    "MK": "MKD",
    "RS": "SRB",
    "TR": "TUR",
    "UA": "UKR",
    "MD": "MDA",
    "GE": "GEO",
}

COUNTRY_NAME_TO_TED_COUNTRY: dict[str, str] = {
    "AUSTRIA": "AUT",
    "BELGIUM": "BEL",
    "BULGARIA": "BGR",
    "CROATIA": "HRV",
    "CYPRUS": "CYP",
    "CZECH REPUBLIC": "CZE",
    "CZECHIA": "CZE",
    "DENMARK": "DNK",
    "ESTONIA": "EST",
    "FINLAND": "FIN",
    "FRANCE": "FRA",
    "GERMANY": "DEU",
    "GREECE": "GRC",
    "HUNGARY": "HUN",
    "IRELAND": "IRL",
    "ITALY": "ITA",
    "LATVIA": "LVA",
    "LITHUANIA": "LTU",
    "LUXEMBOURG": "LUX",
    "MALTA": "MLT",
    "NETHERLANDS": "NLD",
    "POLAND": "POL",
    "PORTUGAL": "PRT",
    "ROMANIA": "ROU",
    "SLOVAKIA": "SVK",
    "SLOVENIA": "SVN",
    "SPAIN": "ESP",
    "SWEDEN": "SWE",
    "NORWAY": "NOR",
    "ICELAND": "ISL",
    "LIECHTENSTEIN": "LIE",
    "SWITZERLAND": "CHE",
    "UNITED KINGDOM": "GBR",
    "ALBANIA": "ALB",
    "BOSNIA AND HERZEGOVINA": "BIH",
    "MONTENEGRO": "MNE",
    "NORTH MACEDONIA": "MKD",
    "SERBIA": "SRB",
    "TURKEY": "TUR",
    "UKRAINE": "UKR",
    "MOLDOVA": "MDA",
    "GEORGIA": "GEO",
}

TED_COUNTRY_TO_ALPHA2: dict[str, str] = {value: key for key, value in ALPHA2_TO_TED_COUNTRY.items()}


def normalize_ted_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    normalized = cleaned.upper()
    if normalized in COUNTRY_NAME_TO_TED_COUNTRY:
        return COUNTRY_NAME_TO_TED_COUNTRY[normalized]
    if len(normalized) == 2:
        return ALPHA2_TO_TED_COUNTRY.get(normalized, normalized)
    return normalized


def ted_country_code_variants(value: str | None) -> list[str]:
    normalized = normalize_ted_country_code(value)
    if not normalized:
        return []

    variants: list[str] = [normalized]
    alpha2 = TED_COUNTRY_TO_ALPHA2.get(normalized)
    if alpha2 and alpha2 not in variants:
        variants.append(alpha2)
    return variants
