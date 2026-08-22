"""Extended, non-diagnostic FOIL domain relevance registry.

The registry marks only what a task appears to involve. It does not infer
competence, personality, demographics, or sensitive traits. Arbitrary domains
remain supported through explicit profile observations.
"""
from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "medicine_healthcare": ("medicine", "medical", "healthcare", "clinical workflow", "patient care", "public health"),
    "biomedical_biotech": ("biotech", "biomedical", "bioengineering", "therapeutic", "diagnostic assay", "medical device"),
    "psychology_behavior": ("psychology", "behavioral science", "cognitive psychology", "human behavior", "psychometrics", "motivation"),
    "education_learning": ("education", "curriculum", "instructional design", "learning science", "classroom", "assessment design", "pedagogy"),
    "social_sciences": ("sociology", "political science", "anthropology", "social science", "survey research", "demography"),
    "humanities_history": ("history", "historical", "literature analysis", "humanities", "archival research", "cultural studies"),
    "philosophy_ethics": ("philosophy", "ethics", "epistemology", "moral reasoning", "philosophy of science"),
    "mathematics_theory": ("pure mathematics", "combinatorics", "number theory", "algebraic geometry", "topology", "mathematical proof"),
    "statistics_analytics": ("data analysis", "statistical modeling", "regression analysis", "time series", "bayesian analysis", "analytics"),
    "business_strategy": ("business strategy", "competitive strategy", "business model", "go to market", "market analysis", "corporate strategy"),
    "marketing_sales": ("marketing", "sales", "customer acquisition", "positioning", "pricing strategy", "conversion funnel"),
    "accounting_operations_finance": ("accounting", "financial statements", "budgeting", "cash flow", "corporate finance", "financial planning"),
    "organizational_hr": ("human resources", "organizational design", "hiring", "performance management", "people operations", "workforce planning"),
    "customer_service_ops": ("customer support", "service operations", "call center", "support workflow", "customer success"),
    "mechanical_engineering": ("mechanical engineering", "mechanism design", "thermofluids", "finite element", "cad", "solid mechanics"),
    "civil_environmental": ("civil engineering", "structural engineering", "geotechnical", "environmental engineering", "water resources"),
    "electrical_electronics": ("electrical engineering", "electronics", "analog circuit", "digital circuit", "pcb", "signal processing"),
    "chemical_process_engineering": ("chemical engineering", "process design", "reactor", "separation process", "process control", "unit operation"),
    "aerospace_space": ("aerospace", "aerodynamics", "spacecraft", "orbital", "propulsion", "flight dynamics"),
    "robotics_control": ("robotics", "control theory", "control system", "slam", "motion planning", "autonomous robot"),
    "earth_geospatial": ("geology", "earth science", "geospatial", "gis", "remote sensing", "climate science", "meteorology"),
    "environment_sustainability": ("sustainability", "carbon accounting", "life cycle assessment", "environmental impact", "decarbonization"),
    "architecture_built_environment": ("architecture", "building design", "urban design", "construction", "bim", "built environment"),
    "manufacturing_fabrication": ("manufacturing", "fabrication", "machining", "3d printing", "additive manufacturing", "process engineering"),
    "energy_power": ("energy systems", "power grid", "renewable energy", "battery systems", "power electronics", "energy storage"),
    "databases_data_engineering": ("data engineering", "data warehouse", "etl", "database design", "query optimization", "data pipeline"),
    "cloud_devops": ("devops", "cloud infrastructure", "kubernetes", "terraform", "ci/cd", "site reliability"),
    "game_interactive_media": ("game design", "game development", "level design", "gameplay system", "interactive media", "game engine"),
    "visual_media": ("graphic design", "illustration", "photography", "video editing", "animation", "visual storytelling"),
    "music_audio": ("music", "composition", "audio engineering", "sound design", "mixing", "music theory"),
    "language_translation": ("translation", "linguistics", "language learning", "grammar", "localization", "interpretation"),
    "journalism_media": ("journalism", "reporting", "newsroom", "investigative reporting", "media analysis", "fact checking"),
    "law_compliance": ("legal research", "compliance", "contract review", "regulatory analysis", "case law", "statutory interpretation"),
    "public_administration": ("public administration", "government operations", "public sector", "program evaluation", "policy implementation"),
    "project_program_management": ("project management", "program management", "milestone", "workstream", "delivery plan", "dependency management"),
    "entrepreneurship": ("startup", "entrepreneurship", "founder", "venture", "product market fit", "fundraising"),
    "procurement_supply_chain": ("procurement", "supply chain", "inventory", "warehouse", "transportation planning", "logistics"),
    "agriculture_food": ("agriculture", "farming", "crop science", "food science", "horticulture", "agronomy"),
    "culinary_hospitality": ("cooking", "culinary", "recipe development", "hospitality", "restaurant operations", "menu design"),
    "sports_performance": ("sports performance", "coaching", "training plan", "strength conditioning", "athletic performance", "sports analytics"),
    "geopolitics_international": ("geopolitics", "international relations", "foreign policy", "diplomacy", "security studies"),
}


def infer_domains(text: str) -> list[str]:
    low = text.lower()
    return [domain for domain, keywords in DOMAIN_KEYWORDS.items() if any(keyword in low for keyword in keywords)]
