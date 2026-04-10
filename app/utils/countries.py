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

TED_COUNTRY_TO_NAME: dict[str, str] = {
    "AUT": "Austria",
    "BEL": "Belgium",
    "BGR": "Bulgaria",
    "HRV": "Croatia",
    "CYP": "Cyprus",
    "CZE": "Czechia",
    "DNK": "Denmark",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "DEU": "Germany",
    "GRC": "Greece",
    "HUN": "Hungary",
    "IRL": "Ireland",
    "ITA": "Italy",
    "LVA": "Latvia",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MLT": "Malta",
    "NLD": "Netherlands",
    "POL": "Poland",
    "PRT": "Portugal",
    "ROU": "Romania",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "ESP": "Spain",
    "SWE": "Sweden",
    "NOR": "Norway",
    "ISL": "Iceland",
    "LIE": "Liechtenstein",
    "CHE": "Switzerland",
    "GBR": "United Kingdom",
    "ALB": "Albania",
    "BIH": "Bosnia and Herzegovina",
    "MNE": "Montenegro",
    "MKD": "North Macedonia",
    "SRB": "Serbia",
    "TUR": "Turkey",
    "UKR": "Ukraine",
    "MDA": "Moldova",
    "GEO": "Georgia",
}


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


def country_display_label(value: str | None) -> str:
    normalized = normalize_ted_country_code(value)
    if not normalized:
        return "Unknown"

    name = TED_COUNTRY_TO_NAME.get(normalized, normalized)
    alpha2 = TED_COUNTRY_TO_ALPHA2.get(normalized)
    if alpha2:
        return f"{name} ({alpha2})"
    return name


def country_filter_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for ted_code, name in sorted(TED_COUNTRY_TO_NAME.items(), key=lambda item: item[1]):
        alpha2 = TED_COUNTRY_TO_ALPHA2.get(ted_code, ted_code)
        options.append((f"{name} ({alpha2})", alpha2))
    return options
