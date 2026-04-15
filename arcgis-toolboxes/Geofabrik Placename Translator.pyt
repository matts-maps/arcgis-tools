# -*- coding: utf-8 -*-
"""
OSMPlaces.pyt  -  ArcGIS Pro Python Toolbox
Downloads OSM place features directly from the Overpass API for one or more
countries and adds them to the active map.

Place type definitions follow the Geofabrik GIS Standard v0.7.12:
  https://www.geofabrik.de/data/geofabrik-osm-gis-standard-0.7.pdf

Parameter order:
  0  Country or Countries      (user defines FIRST)
  1  Place Types               (Geofabrik fclass definitions)
  2  Output Geodatabase
  3  Output Feature Class Name
  4  Target Map Name           (optional)
"""

import arcpy
import urllib.request
import urllib.parse
import json
import os
import time

# ---------------------------------------------------------------------------
# Geofabrik places layer definition - v0.7.12 (section 4.1)
# ---------------------------------------------------------------------------
GEOFABRIK_PLACE_CODES = [
    {"code": 1001, "fclass": "city",             "description": "City (>100,000 people)",            "osm_tag": "city",              "capital_filter": False},
    {"code": 1002, "fclass": "town",             "description": "Town (10,000-100,000 people)",       "osm_tag": "town",              "capital_filter": False},
    {"code": 1003, "fclass": "village",          "description": "Village (<10,000 people)",           "osm_tag": "village",           "capital_filter": False},
    {"code": 1004, "fclass": "hamlet",           "description": "Hamlet (just a few houses)",         "osm_tag": "hamlet",            "capital_filter": False},
    {"code": 1005, "fclass": "national_capital", "description": "National Capital",                   "osm_tag": "city",              "capital_filter": True},
    {"code": 1010, "fclass": "suburb",           "description": "Suburb (named area of town/city)",   "osm_tag": "suburb",            "capital_filter": False},
    {"code": 1020, "fclass": "island",           "description": "Island",                             "osm_tag": "island",            "capital_filter": False},
    {"code": 1050, "fclass": "locality",         "description": "Locality (unpopulated named place)", "osm_tag": "locality",          "capital_filter": False},
    {"code": 1060, "fclass": "named_place",      "description": "Named Place (other settlements)",    "osm_tag": "isolated_dwelling", "capital_filter": False},
]

PLACE_LABELS  = ["{code} - {fclass} | {description}".format(**r) for r in GEOFABRIK_PLACE_CODES]
LABEL_TO_META = {"{code} - {fclass} | {description}".format(**r): r for r in GEOFABRIK_PLACE_CODES}

# ---------------------------------------------------------------------------
# Country -> ISO 3166-1 alpha-2 lookup
# ---------------------------------------------------------------------------
COUNTRY_ISO = {
    "Afghanistan": "AF", "Albania": "AL", "Algeria": "DZ", "Angola": "AO",
    "Argentina": "AR", "Armenia": "AM", "Australia": "AU", "Austria": "AT",
    "Azerbaijan": "AZ", "Bangladesh": "BD", "Belarus": "BY", "Belgium": "BE",
    "Bolivia": "BO", "Bosnia and Herzegovina": "BA", "Brazil": "BR",
    "Bulgaria": "BG", "Cambodia": "KH", "Cameroon": "CM", "Canada": "CA",
    "Chile": "CL", "China": "CN", "Colombia": "CO", "Croatia": "HR",
    "Cuba": "CU", "Czech Republic": "CZ", "Denmark": "DK", "Ecuador": "EC",
    "Egypt": "EG", "Estonia": "EE", "Ethiopia": "ET", "Finland": "FI",
    "France": "FR", "Georgia": "GE", "Germany": "DE", "Ghana": "GH",
    "Greece": "GR", "Guatemala": "GT", "Hungary": "HU", "India": "IN",
    "Indonesia": "ID", "Iran": "IR", "Iraq": "IQ", "Ireland": "IE",
    "Israel": "IL", "Italy": "IT", "Japan": "JP", "Jordan": "JO",
    "Kazakhstan": "KZ", "Kenya": "KE", "Kosovo": "XK", "Kuwait": "KW",
    "Latvia": "LV", "Lebanon": "LB", "Libya": "LY", "Lithuania": "LT",
    "Luxembourg": "LU", "Malaysia": "MY", "Mexico": "MX", "Moldova": "MD",
    "Mongolia": "MN", "Morocco": "MA", "Mozambique": "MZ", "Myanmar": "MM",
    "Nepal": "NP", "Netherlands": "NL", "New Zealand": "NZ", "Nigeria": "NG",
    "North Korea": "KP", "Norway": "NO", "Pakistan": "PK", "Palestine": "PS",
    "Panama": "PA", "Paraguay": "PY", "Peru": "PE", "Philippines": "PH",
    "Poland": "PL", "Portugal": "PT", "Romania": "RO", "Russia": "RU",
    "Rwanda": "RW", "Saudi Arabia": "SA", "Serbia": "RS", "Slovakia": "SK",
    "Slovenia": "SI", "Somalia": "SO", "South Africa": "ZA",
    "South Korea": "KR", "South Sudan": "SS", "Spain": "ES",
    "Sri Lanka": "LK", "Sudan": "SD", "Sweden": "SE", "Switzerland": "CH",
    "Syria": "SY", "Taiwan": "TW", "Tanzania": "TZ", "Thailand": "TH",
    "Tunisia": "TN", "Turkey": "TR", "Uganda": "UG", "Ukraine": "UA",
    "United Arab Emirates": "AE", "United Kingdom": "GB",
    "United States": "US", "Uruguay": "UY", "Uzbekistan": "UZ",
    "Venezuela": "VE", "Vietnam": "VN", "Yemen": "YE", "Zimbabwe": "ZW",
    "French Guiana": "GF",
    # Newly added territories and smaller nations
    "Aland Islands": "AX", "American Samoa": "AS", "Anguilla": "AI",
    "Benin": "BJ", "Bermuda": "BM", "Bhutan": "BT", "Bonaire": "BQ",
    "British Indian Ocean Territory": "IO", "British Virgin Islands": "VG",
    "Burundi": "BI", "Cape Verde": "CV", "Cayman Islands": "KY",
    "Central African Republic": "CF", "Comoros": "KM", "Cook Islands": "CK",
    "Equatorial Guinea": "GQ", "Eswatini": "SZ", "Falkland Islands": "FK",
    "Faroe Islands": "FO", "French Polynesia": "PF", "Gabon": "GA",
    "Gambia": "GM", "Gibraltar": "GI", "Greenland": "GL", "Guadeloupe": "GP",
    "Guam": "GU", "Guernsey": "GG", "Guinea-Bissau": "GW", "Hong Kong": "HK",
    "Isle of Man": "IM", "Jersey": "JE", "Kiribati": "KI", "Lesotho": "LS",
    "Liberia": "LR", "Liechtenstein": "LI", "Macau": "MO", "Maldives": "MV",
    "Marshall Islands": "MH", "Martinique": "MQ", "Mauritius": "MU",
    "Mayotte": "YT", "Micronesia": "FM", "Monaco": "MC", "Montserrat": "MS",
    "Nauru": "NR", "New Caledonia": "NC", "Niue": "NU",
    "Northern Mariana Islands": "MP", "Palau": "PW", "Pitcairn Islands": "PN",
    "Puerto Rico": "PR", "Reunion": "RE", "Saint Barthelemy": "BL",
    "Saint Helena": "SH", "Saint Martin": "MF", "Saint Pierre and Miquelon": "PM",
    "Samoa": "WS", "San Marino": "SM", "Sao Tome and Principe": "ST",
    "Seychelles": "SC", "Sierra Leone": "SL", "Solomon Islands": "SB",
    "South Georgia and the South Sandwich Islands": "GS", "Svalbard": "SJ",
    "Togo": "TG", "Tokelau": "TK", "Tonga": "TO", "Turks and Caicos Islands": "TC",
    "Tuvalu": "TV", "US Virgin Islands": "VI", "Vanuatu": "VU",
    "Vatican City": "VA", "Wallis and Futuna": "WF", "Western Sahara": "EH",

    # Caribbean islands (additions)
    "Antigua and Barbuda": "AG", "Dominica": "DM", "Grenada": "GD",
    "Saint Kitts and Nevis": "KN", "Saint Lucia": "LC",
    "Saint Vincent and the Grenadines": "VC",
    "Aruba": "AW", "Curacao": "CW", "Sint Maarten": "SX",
    # Caribbean
    "Haiti": "HT", "Dominican Republic": "DO", "Jamaica": "JM",
    "Trinidad and Tobago": "TT", "Barbados": "BB", "Bahamas": "BS",
    # Central America (additions)
    "Belize": "BZ", "Honduras": "HN", "El Salvador": "SV",
    "Nicaragua": "NI", "Costa Rica": "CR",
    # Africa (additions)
    "Democratic Republic of the Congo": "CD", "Republic of the Congo": "CG",
    "Senegal": "SN", "Mali": "ML", "Niger": "NE", "Chad": "TD",
    "Burkina Faso": "BF", "Ivory Coast": "CI", "Guinea": "GN",
    "Zambia": "ZM", "Malawi": "MW", "Namibia": "NA", "Botswana": "BW",
    "Madagascar": "MG", "Mauritania": "MR", "Eritrea": "ER", "Djibouti": "DJ",
    # Asia (additions)
    "Laos": "LA", "Timor-Leste": "TL", "Brunei": "BN", "Singapore": "SG",
    "Kyrgyzstan": "KG", "Tajikistan": "TJ", "Turkmenistan": "TM",
    "Qatar": "QA", "Bahrain": "BH", "Oman": "OM",
    # Europe (additions)
    "North Macedonia": "MK", "Montenegro": "ME", "Cyprus": "CY",
    "Malta": "MT", "Iceland": "IS", "Andorra": "AD",
    # Pacific (additions)
    "Papua New Guinea": "PG", "Fiji": "FJ",
}

# ISO alpha-2 -> alpha-3 lookup (used for default filename geoextent)
ISO2_TO_ISO3 = {
    "AF": "AFG", "AL": "ALB", "DZ": "DZA", "AO": "AGO", "AR": "ARG",
    "AM": "ARM", "AU": "AUS", "AT": "AUT", "AZ": "AZE", "BD": "BGD",
    "BY": "BLR", "BE": "BEL", "BO": "BOL", "BA": "BIH", "BR": "BRA",
    "BG": "BGR", "KH": "KHM", "CM": "CMR", "CA": "CAN", "CL": "CHL",
    "CN": "CHN", "CO": "COL", "HR": "HRV", "CU": "CUB", "CZ": "CZE",
    "DK": "DNK", "EC": "ECU", "EG": "EGY", "EE": "EST", "ET": "ETH",
    "FI": "FIN", "FR": "FRA", "GE": "GEO", "DE": "DEU", "GH": "GHA",
    "GR": "GRC", "GT": "GTM", "HU": "HUN", "IN": "IND", "ID": "IDN",
    "IR": "IRN", "IQ": "IRQ", "IE": "IRL", "IL": "ISR", "IT": "ITA",
    "JP": "JPN", "JO": "JOR", "KZ": "KAZ", "KE": "KEN", "XK": "XKX",
    "KW": "KWT", "LV": "LVA", "LB": "LBN", "LY": "LBY", "LT": "LTU",
    "LU": "LUX", "MY": "MYS", "MX": "MEX", "MD": "MDA", "MN": "MNG",
    "MA": "MAR", "MZ": "MOZ", "MM": "MMR", "NP": "NPL", "NL": "NLD",
    "NZ": "NZL", "NG": "NGA", "KP": "PRK", "NO": "NOR", "PK": "PAK",
    "PS": "PSE", "PA": "PAN", "PY": "PRY", "PE": "PER", "PH": "PHL",
    "PL": "POL", "PT": "PRT", "RO": "ROU", "RU": "RUS", "RW": "RWA",
    "SA": "SAU", "RS": "SRB", "SK": "SVK", "SI": "SVN", "SO": "SOM",
    "ZA": "ZAF", "KR": "KOR", "SS": "SSD", "ES": "ESP", "LK": "LKA",
    "SD": "SDN", "SE": "SWE", "CH": "CHE", "SY": "SYR", "TW": "TWN",
    "TZ": "TZA", "TH": "THA", "TN": "TUN", "TR": "TUR", "UG": "UGA",
    "UA": "UKR", "AE": "ARE", "GB": "GBR", "US": "USA", "UY": "URY",
    "UZ": "UZB", "VE": "VEN", "VN": "VNM", "YE": "YEM", "ZW": "ZWE",
    "GF": "GUF",
    "AX": "ALA", "AS": "ASM", "AI": "AIA", "BJ": "BEN", "BM": "BMU",
    "BT": "BTN", "BQ": "BES", "IO": "IOT", "VG": "VGB", "BI": "BDI",
    "CV": "CPV", "KY": "CYM", "CF": "CAF", "KM": "COM", "CK": "COK",
    "GQ": "GNQ", "SZ": "SWZ", "FK": "FLK", "FO": "FRO", "PF": "PYF",
    "GA": "GAB", "GM": "GMB", "GI": "GIB", "GL": "GRL", "GP": "GLP",
    "GU": "GUM", "GG": "GGY", "GW": "GNB", "HK": "HKG", "IM": "IMN",
    "JE": "JEY", "KI": "KIR", "LS": "LSO", "LR": "LBR", "LI": "LIE",
    "MO": "MAC", "MV": "MDV", "MH": "MHL", "MQ": "MTQ", "MU": "MUS",
    "YT": "MYT", "FM": "FSM", "MC": "MCO", "MS": "MSR", "NR": "NRU",
    "NC": "NCL", "NU": "NIU", "MP": "MNP", "PW": "PLW", "PN": "PCN",
    "PR": "PRI", "RE": "REU", "BL": "BLM", "SH": "SHN", "MF": "MAF",
    "PM": "SPM", "WS": "WSM", "SM": "SMR", "ST": "STP", "SC": "SYC",
    "SL": "SLE", "SB": "SLB", "GS": "SGS", "SJ": "SJM", "TG": "TGO",
    "TK": "TKL", "TO": "TON", "TC": "TCA", "TV": "TUV", "VI": "VIR",
    "VU": "VUT", "VA": "VAT", "WF": "WLF", "EH": "ESH",

    "HT": "HTI", "DO": "DOM", "JM": "JAM", "TT": "TTO", "BB": "BRB", "BS": "BHS",
    "AG": "ATG", "DM": "DMA", "GD": "GRD", "KN": "KNA", "LC": "LCA", "VC": "VCT",
    "AW": "ABW", "CW": "CUW", "SX": "SXM",
    "BZ": "BLZ", "HN": "HND", "SV": "SLV", "NI": "NIC", "CR": "CRI",
    "CD": "COD", "CG": "COG", "SN": "SEN", "ML": "MLI", "NE": "NER", "TD": "TCD",
    "BF": "BFA", "CI": "CIV", "GN": "GIN", "ZM": "ZMB", "MW": "MWI",
    "NA": "NAM", "BW": "BWA", "MG": "MDG", "MR": "MRT", "ER": "ERI", "DJ": "DJI",
    "LA": "LAO", "TL": "TLS", "BN": "BRN", "SG": "SGP",
    "KG": "KGZ", "TJ": "TJK", "TM": "TKM",
    "QA": "QAT", "BH": "BHR", "OM": "OMN",
    "MK": "MKD", "ME": "MNE", "CY": "CYP", "MT": "MLT", "IS": "ISL", "AD": "AND",
    "PG": "PNG", "FJ": "FJI",
}

# ---------------------------------------------------------------------------
# Region -> list of country names
# ---------------------------------------------------------------------------
REGIONS = {
    "East Asia": [
        "China", "Hong Kong", "Japan", "Macau", "Mongolia",
        "North Korea", "South Korea", "Taiwan",
    ],
    "Southeast Asia": [
        "Brunei", "Cambodia", "Indonesia", "Laos", "Malaysia", "Myanmar",
        "Philippines", "Singapore", "Thailand", "Timor-Leste", "Vietnam",
    ],
    "South Asia": [
        "Afghanistan", "Bangladesh", "Bhutan", "India", "Maldives",
        "Nepal", "Pakistan", "Sri Lanka",
    ],
    "Central Asia": [
        "Azerbaijan", "Kazakhstan", "Kyrgyzstan", "Mongolia",
        "Tajikistan", "Turkmenistan", "Uzbekistan",
    ],
    "Middle East": [
        "Bahrain", "Iran", "Iraq", "Israel", "Jordan", "Kuwait", "Lebanon",
        "Oman", "Palestine", "Qatar", "Saudi Arabia", "Syria", "Turkey",
        "United Arab Emirates", "Yemen",
    ],
    "North Africa": [
        "Algeria", "Egypt", "Libya", "Mauritania", "Morocco",
        "Sudan", "Tunisia", "Western Sahara",
    ],
    "Sub-Saharan Africa": [
        "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi", "Cameroon",
        "Cape Verde", "Central African Republic", "Chad", "Comoros",
        "Democratic Republic of the Congo", "Djibouti", "Equatorial Guinea",
        "Eritrea", "Eswatini", "Ethiopia", "Gabon", "Gambia", "Ghana",
        "Guinea", "Guinea-Bissau", "Ivory Coast", "Kenya", "Lesotho",
        "Liberia", "Madagascar", "Malawi", "Mali", "Mauritius", "Mayotte",
        "Mozambique", "Namibia", "Niger", "Nigeria", "Republic of the Congo",
        "Reunion", "Rwanda", "Sao Tome and Principe", "Senegal", "Seychelles",
        "Sierra Leone", "Somalia", "South Africa", "South Sudan",
        "Tanzania", "Togo", "Uganda", "Zambia", "Zimbabwe",
    ],
    "Western Europe": [
        "Aland Islands", "Andorra", "Austria", "Belgium", "Cyprus", "Denmark",
        "Faroe Islands", "Finland", "France", "Germany", "Gibraltar", "Greece",
        "Guernsey", "Iceland", "Ireland", "Isle of Man", "Italy", "Jersey",
        "Liechtenstein", "Luxembourg", "Malta", "Monaco", "Netherlands",
        "Norway", "Portugal", "San Marino", "Spain", "Svalbard", "Sweden",
        "Switzerland", "United Kingdom", "Vatican City",
    ],
    "Eastern Europe": [
        "Albania", "Belarus", "Bosnia and Herzegovina", "Bulgaria", "Croatia",
        "Czech Republic", "Estonia", "Georgia", "Hungary", "Kosovo",
        "Latvia", "Lithuania", "Moldova", "Montenegro", "North Macedonia",
        "Poland", "Romania", "Russia", "Serbia", "Slovakia", "Slovenia", "Ukraine",
    ],
    "Caribbean": [
        "Anguilla", "Antigua and Barbuda", "Aruba", "Bahamas", "Barbados",
        "Bermuda", "Bonaire", "British Virgin Islands", "Cayman Islands",
        "Cuba", "Curacao", "Dominica", "Dominican Republic", "Grenada",
        "Guadeloupe", "Haiti", "Jamaica", "Martinique", "Montserrat",
        "Puerto Rico", "Saint Barthelemy", "Saint Helena",
        "Saint Kitts and Nevis", "Saint Lucia", "Saint Martin",
        "Saint Pierre and Miquelon", "Saint Vincent and the Grenadines",
        "Sint Maarten", "Trinidad and Tobago", "Turks and Caicos Islands",
        "US Virgin Islands",
    ],
    "Central America": [
        "Belize", "Costa Rica", "El Salvador", "Guatemala", "Honduras",
        "Nicaragua", "Panama",
    ],
    "North America": [
        "Canada", "Greenland", "Mexico", "Saint Pierre and Miquelon",
        "United States",
    ],
    "South America": [
        "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
        "Falkland Islands", "French Guiana", "Paraguay", "Peru",
        "South Georgia and the South Sandwich Islands", "Uruguay", "Venezuela",
    ],
    "Oceania": [
        "American Samoa", "Australia", "Cook Islands", "Fiji", "French Polynesia",
        "Guam", "Kiribati", "Marshall Islands", "Micronesia", "Nauru",
        "New Caledonia", "New Zealand", "Niue", "Northern Mariana Islands",
        "Palau", "Papua New Guinea", "Pitcairn Islands", "Samoa",
        "Solomon Islands", "Tokelau", "Tonga", "Tuvalu", "Vanuatu",
        "Wallis and Futuna",
    ],
    "Atlantic and Indian Ocean Territories": [
        "Bermuda", "British Indian Ocean Territory", "Falkland Islands",
        "Mayotte", "Reunion", "Saint Helena", "Seychelles",
        "South Georgia and the South Sandwich Islands",
    ],
}

# Short geo_extent prefix used when a region is selected
REGION_GEO_EXTENT = {
    "East Asia":           "eas",
    "Southeast Asia":      "sea",
    "South Asia":          "sas",
    "Central Asia":        "cas",
    "Middle East":         "mea",
    "North Africa":        "naf",
    "Sub-Saharan Africa":  "ssa",
    "Western Europe":      "weu",
    "Eastern Europe":      "eeu",
    "Caribbean":           "car",
    "Central America":     "cam",
    "North America":       "nam",
    "South America":       "sam",
    "Oceania":             "oce",
    "Atlantic and Indian Ocean Territories": "aio",
}

FILENAME_SUFFIX = "stle_stl_pt_s0_openstreetmap_pp_settlements"

# Available name translation fields
NAME_TRANSLATIONS = {
    "French  (name:fr)":  "name:fr",
    "Spanish (name:es)":  "name:es",
    "Arabic  (name:ar)":  "name:ar",
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def _is_folder(path):
    """Return True if the output location is a plain folder (shapefile output)."""
    if not path:
        return False
    try:
        return arcpy.Describe(path).dataType == "Folder"
    except Exception:
        ext = os.path.splitext(path)[1].lower()
        return ext not in (".gdb", ".mdb", ".sde")



# ---------------------------------------------------------------------------
class Toolbox(object):
    def __init__(self):
        self.label = "Geofabrik Placename Translator"
        self.alias = "geofabrikplacenametranslator"
        self.tools = [DownloadOSMPlaces]


# ---------------------------------------------------------------------------
class DownloadOSMPlaces(object):

    def __init__(self):
        self.label = "Geofabrik Placename Translator"
        self.description = (
            "Downloads OpenStreetMap place features for selected countries using "
            "Geofabrik GIS Standard v0.7.12 place definitions. Supports optional "
            "name translations, spatial join to admin polygons, and output to "
            "a geodatabase or folder."
        )
        self.canRunInBackground = False

    # ------------------------------------------------------------------
    def getParameterInfo(self):

        # 0 - Select by Region (optional shortcut)
        p_region = arcpy.Parameter(
            displayName   = "Select by Region (optional shortcut)",
            name          = "region",
            datatype      = "GPString",
            parameterType = "Optional",
            direction     = "Input",
        )
        p_region.filter.type = "ValueList"
        p_region.filter.list = ["(None - pick countries manually)"] + sorted(REGIONS.keys())
        p_region.value       = "(None - pick countries manually)" 


        # 1 - Country or Countries
        p0 = arcpy.Parameter(
            displayName   = "Country or Countries",
            name          = "countries",
            datatype      = "GPString",
            parameterType = "Required",
            direction     = "Input",
            multiValue    = True,
        )
        p0.filter.type = "ValueList"
        p0.filter.list = sorted(COUNTRY_ISO.keys())
        p0.parameterDependencies = [p_region.name]

        # 1 - Place Types
        p1 = arcpy.Parameter(
            displayName   = "Place Types  [Geofabrik v0.7.12 definitions]",
            name          = "place_types",
            datatype      = "GPString",
            parameterType = "Required",
            direction     = "Input",
            multiValue    = True,
        )
        p1.filter.type = "ValueList"
        p1.filter.list = PLACE_LABELS
        p1.values      = PLACE_LABELS

        # 2 - Output Location (geodatabase or folder)
        p2 = arcpy.Parameter(
            displayName   = "Output Location (Geodatabase or Folder)",
            name          = "out_location",
            datatype      = "DEWorkspace",
            parameterType = "Required",
            direction     = "Input",
        )
        p2.filter.list = ["Local Database", "File System"]

        # 3 - Geographic Extent (used as prefix in filename)
        # Defaults to ISO alpha-3 when a single country is selected
        p3 = arcpy.Parameter(
            displayName   = "Geographic Extent (filename prefix, e.g. GBR)",
            name          = "geo_extent",
            datatype      = "GPString",
            parameterType = "Required",
            direction     = "Input",
        )
        p3.value = "geoextent"

        # 4 - Output Feature Class Name (derived, read-only preview)
        p4 = arcpy.Parameter(
            displayName   = "Output Feature Class Name (auto-generated)",
            name          = "out_fc_name",
            datatype      = "GPString",
            parameterType = "Derived",
            direction     = "Output",
        )

        # 5 - Admin polygon dataset for spatial join (optional)
        p5 = arcpy.Parameter(
            displayName   = "Admin Polygon Dataset (optional spatial join)",
            name          = "admin_fc",
            datatype      = "GPFeatureLayer",
            parameterType = "Optional",
            direction     = "Input",
        )
        p5.filter.list = ["Polygon"]

        # 6 - Fields from admin polygon to include in join (optional multi-select)
        # Populated dynamically when admin_fc is set
        p6 = arcpy.Parameter(
            displayName   = "Admin Fields to Include",
            name          = "admin_fields",
            datatype      = "GPString",
            parameterType = "Optional",
            direction     = "Input",
            multiValue    = True,
        )
        p6.filter.type = "ValueList"
        p6.filter.list = []
        p6.enabled     = False   # disabled until an admin FC is chosen

        # 7 - Additional name translation fields
        p7 = arcpy.Parameter(
            displayName   = "Additional Name Translations",
            name          = "name_translations",
            datatype      = "GPString",
            parameterType = "Optional",
            direction     = "Input",
            multiValue    = True,
        )
        p7.filter.type = "ValueList"
        p7.filter.list = list(NAME_TRANSLATIONS.keys())

        # 8 - Add to Map checkbox (last)
        p8 = arcpy.Parameter(
            displayName   = "Add to Map",
            name          = "add_to_map",
            datatype      = "GPBoolean",
            parameterType = "Optional",
            direction     = "Input",
        )
        p8.value = True

        return [p_region, p0, p1, p2, p3, p4, p5, p6, p7, p8]

    # ------------------------------------------------------------------
    def updateParameters(self, params):
        region_param   = params[0]
        country_param  = params[1]
        geo_ext_param  = params[4]
        fc_name_param  = params[5]

        # When a region is selected, populate the country list with that region's countries
        if region_param.altered and not region_param.hasBeenValidated:
            region_val = region_param.valueAsText or ""
            if region_val and region_val != "(None - pick countries manually)" and region_val in REGIONS:
                region_countries = [c for c in REGIONS[region_val] if c in COUNTRY_ISO]
                country_param.filter.list = sorted(COUNTRY_ISO.keys())
                country_param.values = region_countries
                geo_ext_param.value = REGION_GEO_EXTENT.get(region_val, "aoi")
            else:
                # "(None)" selected - clear country selection
                country_param.filter.list = sorted(COUNTRY_ISO.keys())
                country_param.values = None

        # Auto-populate geo_extent whenever country selection changes:
        #   single country -> ISO alpha-3 code
        #   multiple countries -> "aoi"
        #   (only if region param did not just set it)
        elif country_param.altered and not country_param.hasBeenValidated:
            countries = _parse_multivalue(country_param.valueAsText)
            if len(countries) == 1:
                iso2 = COUNTRY_ISO.get(countries[0], "")
                iso3 = ISO2_TO_ISO3.get(iso2, "")
                geo_ext_param.value = iso3.lower() if iso3 else "geoextent"
            elif len(countries) > 1:
                geo_ext_param.value = "aoi"

        # Always rebuild the derived filename from current geo_extent value
        geo_ext = (geo_ext_param.valueAsText or "geoextent").strip().lower()
        geo_ext = "".join(c if c.isalnum() or c == "_" else "_" for c in geo_ext)
        fc_name_param.value = "{}_{}".format(geo_ext, FILENAME_SUFFIX)

        # Populate admin fields list only when the admin FC path itself changes.
        # Using hasBeenValidated=False to detect a genuine user change so that
        # the user's field selection is not wiped on every parameter update.
        admin_fc_param     = params[6]
        admin_fields_param = params[7]
        if admin_fc_param.altered and not admin_fc_param.hasBeenValidated:
            if admin_fc_param.valueAsText:
                fields = _get_admin_fields(admin_fc_param.valueAsText)
                if fields:
                    admin_fields_param.filter.list = fields
                    admin_fields_param.values      = fields  # all selected by default
                    admin_fields_param.enabled     = True
                else:
                    admin_fields_param.filter.list = []
                    admin_fields_param.values      = None
                    admin_fields_param.enabled     = False
            else:
                admin_fields_param.filter.list = []
                admin_fields_param.values      = None
                admin_fields_param.enabled     = False
        return

    # ------------------------------------------------------------------
    def updateMessages(self, params):
        country_param = params[1]
        if country_param.valueAsText:
            unknown = [c for c in _parse_multivalue(country_param.valueAsText)
                       if c not in COUNTRY_ISO]
            if unknown:
                country_param.setWarningMessage(
                    "Country name(s) not in ISO lookup: {}. "
                    "These will be skipped.".format(", ".join(unknown))
                )
        loc_param = params[3]
        if loc_param.valueAsText and not arcpy.Exists(loc_param.valueAsText):
            loc_param.setErrorMessage("Output location does not exist.")

        # Show the auto-generated filename as an info message on geo_extent
        geo_ext_param = params[4]
        loc_val = params[3].valueAsText or ""
        if geo_ext_param.valueAsText:
            geo_ext = geo_ext_param.valueAsText.strip().lower()
            geo_ext = "".join(c if c.isalnum() or c == "_" else "_" for c in geo_ext)
            suffix = FILENAME_SUFFIX
            if _is_folder(loc_val):
                geo_ext_param.setWarningMessage(
                    "Output will be: {}.shp".format("{}_{}".format(geo_ext, suffix)[:8])
                    if len("{}_{}".format(geo_ext, suffix)) > 8
                    else "Output will be: {}_{}.shp".format(geo_ext, suffix)
                )
            else:
                geo_ext_param.setWarningMessage(
                    "Output FC will be named: {}_{}".format(geo_ext, suffix)
                )
        return

    # ------------------------------------------------------------------
    def execute(self, params, messages):
        # params[0] = region (optional, already used to populate countries)
        countries     = _parse_multivalue(params[1].valueAsText)
        place_choices = _parse_multivalue(params[2].valueAsText)
        out_location  = params[3].valueAsText
        geo_ext       = (params[4].valueAsText or "geoextent").strip().lower()
        geo_ext       = "".join(c if c.isalnum() or c == "_" else "_" for c in geo_ext)
        # Detect if output is a folder (shapefile) or geodatabase (feature class)
        is_folder     = _is_folder(out_location)
        out_fc_name   = arcpy.ValidateTableName(
                            "{}_{}".format(geo_ext, FILENAME_SUFFIX), out_location)
        admin_fc      = params[6].valueAsText
        admin_fields       = _parse_multivalue(params[7].valueAsText) if params[7].valueAsText else []
        transl_labels      = _parse_multivalue(params[8].valueAsText) if params[8].valueAsText else []
        add_to_map    = params[9].value
        name_translations  = [NAME_TRANSLATIONS[l] for l in transl_labels if l in NAME_TRANSLATIONS]

        if not countries:
            arcpy.AddError("No countries selected.")
            return
        if not place_choices:
            arcpy.AddError("No place types selected.")
            return

        iso_codes = []
        for c in countries:
            if c in COUNTRY_ISO:
                iso_codes.append(COUNTRY_ISO[c])
            else:
                arcpy.AddWarning("'{}' not in ISO lookup - skipping.".format(c))
        if not iso_codes:
            arcpy.AddError("No valid countries resolved to ISO codes.")
            return

        selected_meta    = [LABEL_TO_META[p] for p in place_choices if p in LABEL_TO_META]
        if not selected_meta:
            arcpy.AddError("No valid place types resolved.")
            return

        standard_tags    = list({m["osm_tag"] for m in selected_meta if not m["capital_filter"]})
        include_capitals = any(m["capital_filter"] for m in selected_meta)
        if include_capitals and "city" not in standard_tags:
            standard_tags.append("city")

        arcpy.AddMessage("=" * 55)
        arcpy.AddMessage("OSM Places Download  (Geofabrik definitions v0.7.12)")
        arcpy.AddMessage("=" * 55)
        arcpy.AddMessage("Countries  : {}".format(", ".join(countries)))
        arcpy.AddMessage("ISO codes  : {}".format(", ".join(iso_codes)))
        arcpy.AddMessage("OSM tags   : place={}".format(", ".join(sorted(standard_tags))))
        if include_capitals:
            arcpy.AddMessage("             + national_capital filter applied")

        arcpy.AddMessage("\nQuerying Overpass API...")
        query  = _build_overpass_query(iso_codes, standard_tags)
        result = _run_overpass_query(query)

        if result is None:
            arcpy.AddError(
                "Overpass API query failed after 3 attempts. "
                "Check network connectivity to overpass-api.de."
            )
            return

        elements = result.get("elements", [])
        arcpy.AddMessage("  {} OSM node(s) returned.".format(len(elements)))

        if not elements:
            arcpy.AddWarning("No features returned. Verify country selection and place types.")
            return

        out_fc = os.path.join(out_location, out_fc_name)
        # For folder output the .shp extension is added inside _create_feature_class,
        # so resolve the actual on-disk path here so all subsequent operations
        # (spatial join, field deletion, add to map) use the correct path.
        if is_folder and not out_fc.lower().endswith(".shp"):
            out_fc = out_fc + ".shp"
        arcpy.AddMessage("\nWriting to: {} ({})".format(
            out_fc, "Shapefile" if is_folder else "Feature Class"))
        _create_feature_class(out_fc, elements, selected_meta, countries, is_folder, name_translations)

        # ------------------------------------------------------------------
        # Spatial join - places (target) joined to admin polygons (join)
        # KEEP_ALL so unmatched places are retained (left join)
        # Result overwrites the places FC in-place
        # ------------------------------------------------------------------
        if admin_fc:
            arcpy.AddMessage("\nRunning spatial join against admin polygons...")
            if admin_fields:
                arcpy.AddMessage("  Including admin fields: {}".format(", ".join(admin_fields)))
            else:
                arcpy.AddMessage("  Including all admin fields.")

            # Build field mapping:
            #   1. Add all fields from both target (places) and join (admin)
            #   2. Remove any admin fields that the user did not select
            fm = arcpy.FieldMappings()
            fm.addTable(out_fc)    # all places fields
            fm.addTable(admin_fc)  # all admin fields

            if admin_fields:
                # Collect which admin fields exist in the FC (case-insensitive)
                all_admin = [f.name for f in arcpy.ListFields(admin_fc)]
                selected_lower = {f.lower() for f in admin_fields}

                # Walk backwards so index removal doesn't shift positions
                for i in range(fm.fieldCount - 1, -1, -1):
                    fmap       = fm.getFieldMap(i)
                    out_field  = fmap.outputField.name
                    # Check if this field comes from the admin FC only
                    # (i.e. not present in the places FC)
                    in_places  = any(
                        f.name.lower() == out_field.lower()
                        for f in arcpy.ListFields(out_fc)
                    )
                    in_admin   = any(
                        f.lower() == out_field.lower() for f in all_admin
                    )
                    if in_admin and not in_places and out_field.lower() not in selected_lower:
                        fm.removeFieldMap(i)

            tmp_join = "in_memory\\osm_places_joined"
            arcpy.analysis.SpatialJoin(
                target_features    = out_fc,
                join_features      = admin_fc,
                out_feature_class  = tmp_join,
                join_operation     = "JOIN_ONE_TO_ONE",
                join_type          = "KEEP_ALL",
                match_option       = "INTERSECT",
                field_mapping      = fm,
            )
            # Overwrite the original places FC with the joined result
            if arcpy.Exists(out_fc):
                arcpy.management.Delete(out_fc)
            arcpy.management.CopyFeatures(tmp_join, out_fc)
            arcpy.management.Delete(tmp_join)

            # Remove auto-generated SpatialJoin fields
            for auto_field in ["Join_Count", "TARGET_FID"]:
                if arcpy.ListFields(out_fc, auto_field):
                    arcpy.management.DeleteField(out_fc, auto_field)

            arcpy.AddMessage("  Spatial join complete.")

        arcpy.AddMessage("\nDone - '{}'.".format(out_fc_name))
        arcpy.AddMessage("Data: (C) OpenStreetMap contributors, ODbL 1.0")

        if add_to_map:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            target_map = aprx.activeMap
            if not target_map:
                arcpy.AddWarning("No active map found - layer was not added to the map.")
            else:
                target_map.addDataFromPath(out_fc)
                arcpy.AddMessage("Layer added to map '{}'.".format(target_map.name))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _get_admin_fields(fc_path):
    """Return user-facing field names from an admin polygon FC,
    excluding geometry, OID, and standard system fields."""
    if not fc_path or not arcpy.Exists(fc_path):
        return []
    skip_types = {"Geometry", "OID", "GlobalID", "Blob", "Raster"}
    skip_names = {"shape", "shape_length", "shape_area", "objectid",
                  "fid", "globalid"}
    return [
        f.name for f in arcpy.ListFields(fc_path)
        if f.type not in skip_types
        and f.name.lower() not in skip_names
    ]

def _parse_multivalue(raw):
    if not raw:
        return []
    return [v.strip("'\" ") for v in raw.split(";") if v.strip("'\" ")]


def _query_timeout(iso_codes):
    return max(60, len(iso_codes) * 45)


def _build_overpass_query(iso_codes, osm_tags):
    timeout     = _query_timeout(iso_codes)
    value_regex = "|".join("^{}$".format(t) for t in osm_tags)
    parts = []
    for iso in iso_codes:
        var = "a{}".format(iso)
        parts.append(
            'area["ISO3166-1:alpha2"="{}"]["admin_level"="2"]->.{};\n'
            '  node["place"~"{}"](area.{});'.format(iso, var, value_regex, var)
        )
    return (
        "[out:json][timeout:{}];\n(\n  ".format(timeout)
        + "\n  ".join(parts)
        + "\n);\nout body;"
    )


def _run_overpass_query(query, retries=3):
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                OVERPASS_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            arcpy.AddWarning("  Attempt {}/{} failed: {}".format(attempt, retries, exc))
            if attempt < retries:
                wait = 5 * attempt
                arcpy.AddMessage("  Retrying in {}s...".format(wait))
                time.sleep(wait)
    return None


def _resolve_geofabrik_fclass(tags, selected_meta):
    """
    Resolve fclass and code following Geofabrik v0.7.12 rules.
    national_capital (1005): place=city AND one of:
      (a) is_capital=country
      (b) capital=yes (national level only - excludes capital=4 regional capitals)
    Note: admin_level=2 is intentionally excluded as it causes false positives
    on country-level admin boundary nodes that are not capital cities.
    """
    place_val  = tags.get("place", "")
    is_capital = (
        tags.get("is_capital") == "country"
        or tags.get("capital") == "yes"
    )

    for meta in selected_meta:
        if meta["capital_filter"] and place_val == "city" and is_capital:
            return meta["fclass"], meta["code"]

    for meta in selected_meta:
        if not meta["capital_filter"] and meta["osm_tag"] == place_val:
            return meta["fclass"], meta["code"]

    return place_val, 0


def _create_feature_class(out_fc, elements, selected_meta, countries,
                          is_folder=False, name_translations=None):
    """
    Create a WGS84 point feature class (GDB) or shapefile (folder) from
    Overpass JSON nodes.

    Attribute schema (Geofabrik standard v0.7.12, section 2.5):
      osm_id, code, fclass, name, name_en, [name_fr, name_es, name_ar], population
    Note: shapefile field names are truncated to 10 characters.
    """
    name_translations = name_translations or []
    out_location = os.path.dirname(out_fc)
    fc_name      = os.path.basename(out_fc)

    # Ensure .shp extension for folder output
    if is_folder and not fc_name.lower().endswith(".shp"):
        fc_name = fc_name + ".shp"
        out_fc  = os.path.join(out_location, fc_name)
    elif is_folder:
        pass  # .shp already present, path is correct

    sr = arcpy.SpatialReference(4326)
    arcpy.management.CreateFeatureclass(out_location, fc_name, "POINT", spatial_reference=sr)

    arcpy.management.AddField(out_fc, "osm_id",     "TEXT",  field_length=12)
    arcpy.management.AddField(out_fc, "code",        "SHORT")
    arcpy.management.AddField(out_fc, "fclass",      "TEXT",  field_length=40)
    arcpy.management.AddField(out_fc, "name",        "TEXT",  field_length=100)
    arcpy.management.AddField(out_fc, "name_en",     "TEXT",  field_length=100)

    # Add selected translation fields (name:fr -> name_fr, etc.)
    for osm_tag in name_translations:
        field_name = osm_tag.replace(":", "_")  # name:fr -> name_fr
        arcpy.management.AddField(out_fc, field_name, "TEXT", field_length=100)

    arcpy.management.AddField(out_fc, "population",  "LONG")

    insert_fields = ["SHAPE@XY", "osm_id", "code", "fclass", "name", "name_en"]
    insert_fields += [t.replace(":", "_") for t in name_translations]
    insert_fields += ["population"]

    written = 0
    with arcpy.da.InsertCursor(out_fc, insert_fields) as cur:
        for el in elements:
            if el.get("type") != "node":
                continue

            tags         = el.get("tags", {})
            fclass, code = _resolve_geofabrik_fclass(tags, selected_meta)

            if code == 0:
                continue

            try:
                pop = int(tags.get("population", 0) or 0)
            except ValueError:
                pop = 0

            row = [
                (el["lon"], el["lat"]),
                str(el.get("id", "")),
                code,
                fclass,
                tags.get("name", ""),
                tags.get("name:en", ""),
            ]
            row += [tags.get(t, "") for t in name_translations]
            row += [pop]

            cur.insertRow(row)
            written += 1

    arcpy.AddMessage("  {} features written.".format(written))
