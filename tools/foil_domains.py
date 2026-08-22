"""Extended, non-diagnostic FOIL domain relevance registry.

This registry only marks task domains as relevant. It never assigns competence,
personality, demographics, or sensitive traits. Unknown domains can still be
created explicitly by the profile/calibration tools.
"""
from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mathematics_pure": (
        "pure mathematics", "number theory", "algebraic geometry", "topology", "combinatorics", "real analysis", "abstract algebra"
    ),
    "formal_methods_theorem_proving": (
        "theorem proving", "formal verification", "lean", "coq", "isabelle", "dafny", "smt", "proof assistant", "model checking"
    ),
    "optimization_operations_research": (
        "optimization", "optimize", "operations research", "linear program", "linear programming", "integer program", "integer programming", "constraint program", "constraint programming", "scheduling model", "scheduling optimization"
    ),
    "databases_data_engineering": (
        "database", "postgres", "sql", "data engineering", "etl", "data warehouse", "query planner", "schema design"
    ),
    "cloud_devops_platform": (
        "cloud", "devops", "kubernetes", "docker", "terraform", "ci/cd", "platform engineering", "site reliability"
    ),
    "computer_vision_graphics": (
        "computer vision", "image processing", "rendering", "computer graphics", "3d graphics", "shader", "vision model"
    ),
    "nlp_language_technology": (
        "natural language processing", "nlp", "language model", "tokenizer", "speech recognition", "text generation", "information extraction"
    ),
    "ai_safety_evaluation": (
        "ai safety", "alignment", "model evaluation", "red teaming model", "jailbreak", "robustness evaluation", "interpretability"
    ),
    "medicine_healthcare": (
        "medicine", "medical", "healthcare", "clinical workflow", "diagnosis", "treatment", "patient care", "public health"
    ),
    "bioinformatics_computational_biology": (
        "bioinformatics", "computational biology", "sequence analysis", "genome assembly", "single cell", "protein structure prediction"
    ),
    "neuroscience_cognitive_science": (
        "neuroscience", "cognitive science", "neural recording", "brain imaging", "cognition", "memory research"
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
    "econometrics_statistics": (
        "econometrics", "panel data", "time series econometrics", "instrumental variables", "regression discontinuity"
    ),
    "mechanical_engineering": (
        "mechanical engineering", "mechanism design", "thermofluids", "finite element", "cad", "solid mechanics"
    ),
    "electrical_electronics": (
        "electrical engineering", "electronics", "circuit design", "signal processing", "rf", "pcb", "power electronics"
    ),
    "chemical_process_engineering": (
        "chemical engineering", "process engineering", "reactor design", "separation process", "process control"
    ),
    "civil_environmental": (
        "civil engineering", "structural engineering", "geotechnical", "environmental engineering", "water resources"
    ),
    "aerospace_engineering": (
        "aerospace", "aerodynamics", "flight dynamics", "spacecraft", "propulsion", "orbital mechanics"
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
    "game_design_interactive_media": (
        "game design", "gameplay", "level design", "interactive narrative", "game engine", "player experience"
    ),
    "music_audio": (
        "music", "composition", "audio engineering", "sound design", "mixing", "music theory"
    ),
    "language_translation": (
        "translation", "linguistics", "language learning", "grammar", "localization", "interpretation"
    ),
    "technical_writing_documentation": (
        "technical writing", "api documentation", "developer documentation", "documentation system", "information architecture"
    ),
    "journalism_media": (
        "journalism", "reporting", "newsroom", "investigative reporting", "media analysis", "fact checking"
    ),
    "law_policy": (
        "legal", "law", "regulation", "statute", "case law", "public policy", "legal research"
    ),
    "public_administration": (
        "public administration", "government operations", "public sector", "program evaluation", "policy implementation"
    ),
    "organizational_management": (
        "organizational design", "management", "leadership", "team structure", "organizational behavior", "change management"
    ),
    "project_program_management": (
        "project management", "program management", "milestone", "workstream", "delivery plan", "dependency management"
    ),
    "product_management": (
        "product management", "product strategy", "product requirements", "user research", "product discovery", "product roadmap"
    ),
    "entrepreneurship": (
        "startup", "entrepreneurship", "founder", "venture", "product market fit", "fundraising"
    ),
    "manufacturing_fabrication": (
        "manufacturing", "fabrication", "machining", "3d printing", "additive manufacturing", "process engineering"
    ),
    "industrial_engineering": (
        "industrial engineering", "quality engineering", "lean manufacturing", "six sigma", "process optimization", "capacity planning"
    ),
    "agriculture_food": (
        "agriculture", "farming", "crop science", "food science", "horticulture", "agronomy"
    ),
    "energy_power": (
        "energy systems", "power grid", "renewable energy", "battery systems", "power electronics", "energy storage"
    ),
    "human_factors": (
        "human factors", "ergonomics", "cognitive load", "usability study", "human computer interaction", "hci"
    ),
    "operations_logistics": (
        "logistics", "supply chain", "routing problem", "inventory", "warehouse operations", "transportation planning"
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
