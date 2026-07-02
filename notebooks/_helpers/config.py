"""Thornforest-specific constants. Kept separate from the generic helper modules so those
modules stay project-agnostic (they take these as arguments) and can later move to the shared
watershed-analysis-planning package unchanged.

PRIORITY_GROUPS is the project's grouping of USGS parameters/characteristics into the 11 target
variables — an explicitly-new blend, distinct from the verbatim source parameter names.
"""

# group -> {"parameter_codes": set[str], "characteristics": list[str] (lowercase substrings)}
PRIORITY_GROUPS = {
    "conductivity": {"parameter_codes": {"00095", "90095"}, "characteristics": ["specific conductance", "conductivity"]},
    "temperature": {"parameter_codes": {"00010"}, "characteristics": ["temperature, water"]},
    "dissolved_oxygen": {"parameter_codes": {"00300", "00301"}, "characteristics": ["dissolved oxygen"]},
    "dissolved_solids": {"parameter_codes": {"70300", "00515"}, "characteristics": ["total dissolved solids"]},
    "chlorophyll": {"parameter_codes": {"32209", "32210", "32211", "70953"}, "characteristics": ["chlorophyll", "algae"]},
    "pH": {"parameter_codes": {"00400"}, "characteristics": ["ph"]},  # pH matched EXACTLY (see classify_parameter)
    "nitrogen": {
        "parameter_codes": {"00600", "00605", "00608", "00613", "00615", "00618", "00620", "00625", "00630"},
        "characteristics": ["nitrogen", "nitrate", "nitrite", "ammonia", "kjeldahl"],
    },
    "phosphorus": {"parameter_codes": {"00650", "00665", "00666", "00671"}, "characteristics": ["phosphorus", "orthophosphate"]},
    "turbidity": {"parameter_codes": {"00076", "63675", "63676", "63680"}, "characteristics": ["turbidity"]},
    # Water quantity (flow & level)
    "discharge": {
        "parameter_codes": {"00060", "00061", "00055", "70232", "30208", "30209"},  # discharge + velocity
        "characteristics": ["discharge", "stream flow", "streamflow"],
    },
    "water_level": {
        "parameter_codes": {"00065", "00062", "00054", "62611", "62614", "62615", "63160", "72019", "72020", "72148", "72150", "72170"},
        "characteristics": ["gage height", "stream stage", "water level", "water-surface elevation"],
    },
}
PRIORITY_NAMES = list(PRIORITY_GROUPS)

# The three study watersheds (HUC-8 code -> name).
WATERSHEDS = {
    "12110208": "South Laguna Madre",
    "13090001": "Los Olmos",
    "13090002": "Lower Rio Grande",
}

# Plot frame width (px), tuned to fit the Quarto cosmo content column incl. toolbar.
# Lower it (or widen body-width) if any page side-scrolls.
PLOT_WIDTH = 600

# CONUS404 source variable -> our derived presentation label + how we derive it.
# Source names, long_name descriptions, and units are carried verbatim from the dataset's own
# variable attributes (see NB2) — NOT paraphrased here. Docs:
# https://www.usgs.gov/data/conus404-40-years-daily-4-km-resolution-conus-model-simulation-output
CONUS404_VARIABLES = {
    "PREC_ACC_NC": {"derived_label": "precip_mm", "derivation": "monthly precip accumulation (mm); sum 12 → water-year total"},
    "ACETLSM":     {"derived_label": "et_mm", "derivation": "monthly ET accumulation (mm); sum 12 → water-year total"},
    "ACRUNSF":     {"derived_label": "surf_runoff_mm", "derivation": "monthly surface-runoff accumulation (mm)"},
    "ACRUNSB":     {"derived_label": "subsurf_runoff_mm", "derivation": "monthly subsurface-runoff accumulation (mm)"},
    "RECH":        {"derived_label": "recharge_mm", "derivation": "monthly recharge accumulation (mm)"},
    "SMOIS":       {"derived_label": "soil_moisture_m3m3", "derivation": "surface soil-layer volumetric moisture (m³/m³)"},
    "SNOW":        {"derived_label": "snow_kgm2", "derivation": "snow water equivalent (kg/m²)"},
    "CANWAT":      {"derived_label": "canopy_water_kgm2", "derivation": "canopy water (kg/m²)"},
    "T2":          {"derived_label": "t2_degc", "derivation": "2 m air temperature, converted K → °C"},
    "TD2":         {"derived_label": "td2_degc", "derivation": "2 m dewpoint, converted K → °C"},
    "Q2":          {"derived_label": "q2_kgkg", "derivation": "2 m water-vapor mixing ratio (kg/kg)"},
}
