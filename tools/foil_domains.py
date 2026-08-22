"""Extended, non-diagnostic FOIL domain relevance registry.

This registry only marks task domains as relevant. It never assigns competence,
personality, demographics, or sensitive traits. Unknown domains can still be
created explicitly by the profile/calibration tools.
"""
from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "medicine_healthcare": (
        "medicine", "medical", "healthcare", "clinical workflow", "diagnosis", "treatment", "patient care", "public health"
    ),
    "psychology_behavior": (
        "psychology", "behavioral science", "cognitive psychology", "human behavior", "psychometrics", "motivation"
    ),
    "education_learning": (
        "education", "curriculum", "instructional design", "learning science", "classroom", "assessment design", "pedagogy"
    ),
    "social_sciences": (
        "sociology", "political science", "anthropology", "social science", "survey research", "demography"
    ),
    "humanities_history": (
        "history", "historical", "literature analysis", "humanities", "archival research", "cultural studies"
    ),
    "philosophy_ethics": (
        "philosophy", "ethics", "epistemology", "moral reasoning", "philosophy of science"
    ),
    "business_strategy": (
        "business strategy", "competitive strategy", "business model", "go to market", "market analysis", "corporate strategy"
    ),
    "marketing_sales": (
        "marketing", "sales", "customer acquisition", "positioning", "pricing strategy", "funnel", "conversion"
    ),
    "accounting_operations_finance": (
        "accounting", "financial statements", "budgeting", "cash flow", "corporate finance", "financial planning"
    ),
    "mechanical_engineering": (
        "mechanical engineering", "mechanism design", "thermofluids", "finite element", "cad", "solid mechanics"
    ),
    "civil_environmental": (
        "civil engineering", "structural engineering", "geotechnical", "environmental engineering", "water resources"
    ),
    "robotics_control": (
        "robotics", "control theory", "control system", "slam", "motion planning", "autonomous robot"
    ),
    "earth_geospatial": (
        "geology", "earth science", "geospatial", "gis", "remote sensing", "climate science", "meteorology"
    ),
    "architecture_built_environment": (
        "architecture", "building design", "urban design", "construction", "bim", "built environment"
    ),
    "visual_media": (
        "graphic design", "illustration", "photography", "video editing", "animation", "visual storytelling"
    ),
    "music_audio": (
        "music", "composition", "audio engineering", "sound design", "mixing", "music theory"
    ),
    "language_translation": (
        "translation", "linguistics", "language learning", "grammar", "localization", "interpretation"
    ),
    "journalism_media": (
        "journalism", "reporting", "newsroom", "investigative reporting", "media analysis", "fact checking"
    ),
    "public_administration": (
        "public administration", "government operations", "public sector", "program evaluation", "policy implementation"
    ),
    "project_program_management": (
        "project management", "program management", "milestone", "workstream", "delivery plan", "dependency management"
    ),
    "entrepreneurship": (
        "startup", "entrepreneurship", "founder", "venture", "product market fit", "fundraising"
    ),
    "manufacturing_fabrication": (
        "manufacturing", "fabrication", "machining", "3d printing", "additive manufacturing", "process engineering"
    ),
    "agriculture_food": (
        "agriculture", "farming", "crop science", "food science", "horticulture", "agronomy"
    ),
    "energy_power": (
        "energy systems", "power grid", "renewable energy", "battery systems", "power electronics", "energy storage"
    ),
    "geopolitics_international": (
        "geopolitics", "international relations", "foreign policy", "diplomacy", "security studies"
    ),
}


def infer_domains(text: str) -> list[str]:
    low = text.lower()
    return [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(keyword in low for keyword in keywords)
    ]
