"""Centralized, configurable Industry Taxonomy and Keyword Knowledge Base for FlowShark.

Defines:
- 15 Core B2B Industries + Other + Unknown.
- Comprehensive sub-industries per core industry.
- Domain patterns, keywords, and phrase signals distinguishing Sender Industry vs Target Industry.
- Validation, normalization, and lookup utilities.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
import re

# Centralized Industry Taxonomy
INDUSTRY_TAXONOMY: Dict[str, List[str]] = {
    "IT & Software": [
        "Software Development",
        "SaaS",
        "IT Consulting",
        "Web Development",
        "Cybersecurity",
        "Cloud Services",
        "Mobile App Development",
        "AI & Machine Learning",
        "DevOps & Infrastructure",
    ],
    "Healthcare": [
        "Hospitals",
        "Clinics",
        "Pharmaceuticals",
        "Medical Equipment",
        "Healthcare Technology",
        "Hospital Services",
        "Diagnostics & Labs",
        "Telemedicine",
    ],
    "Banking & Finance": [
        "Banking",
        "Accounting",
        "Financial Services",
        "Taxation",
        "Fintech",
        "Investment Banking",
        "Auditing",
        "Wealth Management",
    ],
    "Insurance": [
        "Life Insurance",
        "Health Insurance",
        "General Insurance",
        "Property & Casualty",
        "Commercial Insurance",
        "Underwriting",
    ],
    "Education": [
        "Schools",
        "Colleges",
        "E-learning",
        "Educational Technology",
        "Training Institutes",
        "Universities",
        "EdTech Platforms",
    ],
    "Manufacturing": [
        "Automotive",
        "Electronics",
        "Industrial Machinery",
        "Consumer Goods",
        "Chemical Manufacturing",
        "Textiles & Apparel",
        "Aerospace & Defense",
        "Plastics & Polymers",
    ],
    "Retail & E-commerce": [
        "Online Retail",
        "Fashion",
        "Consumer Products",
        "Wholesale",
        "Retail Stores",
        "Apparel & Clothing",
        "Direct-to-Consumer",
        "Supermarkets & Groceries",
    ],
    "Real Estate & Construction": [
        "Residential Property",
        "Commercial Property",
        "Construction",
        "Property Management",
        "Architecture & Interior Design",
        "Real Estate Brokerage",
        "Civil Engineering",
    ],
    "Logistics & Transportation": [
        "Shipping",
        "Warehousing",
        "Supply Chain",
        "Transportation",
        "Freight Forwarding",
        "Fleet Management",
        "Couriers & Express Delivery",
    ],
    "Telecommunications": [
        "Telecom Services",
        "Networking",
        "Communication Technology",
        "Wireless Carriers",
        "VoIP & Unified Communications",
        "Broadband & Internet",
    ],
    "Hospitality & Tourism": [
        "Hotels",
        "Restaurants",
        "Travel Agencies",
        "Tourism",
        "Resorts & Leisure",
        "Event Management & Catering",
        "Fitness & Gyms",
    ],
    "Agriculture": [
        "Farming",
        "AgriTech",
        "Agricultural Equipment",
        "Food Production",
        "Crop Cultivation",
        "Livestock & Dairy",
        "Fertilizers & Pesticides",
    ],
    "Energy & Utilities": [
        "Renewable Energy",
        "Electricity",
        "Oil & Gas",
        "Utilities",
        "Solar Energy",
        "CleanTech",
        "Water & Waste Management",
    ],
    "Marketing & Advertising": [
        "Digital Marketing",
        "Advertising",
        "Branding",
        "SEO",
        "Social Media Marketing",
        "Public Relations",
        "Content Marketing",
    ],
    "Legal & Professional Services": [
        "Legal Services",
        "Consulting",
        "Recruitment",
        "Business Services",
        "Corporate Law",
        "HR Consulting & Staffing",
        "Management Consulting",
    ],
    "Other": [
        "Other",
        "Government & Public Sector",
        "Non-Profit & NGO",
        "Media & Entertainment",
    ],
    "Unknown": [
        "Unknown",
    ],
}

PRIMARY_INDUSTRIES: List[str] = list(INDUSTRY_TAXONOMY.keys())

# Standard normalized lookup map (lowercase -> canonical title)
_NORMALIZED_LOOKUP: Dict[str, str] = {
    ind.lower(): ind for ind in PRIMARY_INDUSTRIES
}
_NORMALIZED_LOOKUP.update({
    "it": "IT & Software",
    "software": "IT & Software",
    "it and software": "IT & Software",
    "tech": "IT & Software",
    "technology": "IT & Software",
    "finance": "Banking & Finance",
    "banking": "Banking & Finance",
    "retail": "Retail & E-commerce",
    "ecommerce": "Retail & E-commerce",
    "e-commerce": "Retail & E-commerce",
    "real estate": "Real Estate & Construction",
    "construction": "Real Estate & Construction",
    "logistics": "Logistics & Transportation",
    "transport": "Logistics & Transportation",
    "transportation": "Logistics & Transportation",
    "telecom": "Telecommunications",
    "hospitality": "Hospitality & Tourism",
    "tourism": "Hospitality & Tourism",
    "energy": "Energy & Utilities",
    "utilities": "Energy & Utilities",
    "marketing": "Marketing & Advertising",
    "advertising": "Marketing & Advertising",
    "legal": "Legal & Professional Services",
    "professional services": "Legal & Professional Services",
    "automotive": "Manufacturing",
    "hospital": "Healthcare",
    "pharma": "Healthcare",
    "agritech": "Agriculture",
    "farming": "Agriculture",
    "agriculture": "Agriculture",
    "telecommunications": "Telecommunications",
    "broadband": "Telecommunications",
    "telecom": "Telecommunications",
})


def get_all_industries() -> List[str]:
    """Return all canonical primary industry names."""
    return list(PRIMARY_INDUSTRIES)


def get_taxonomy() -> Dict[str, List[str]]:
    """Return complete taxonomy structure."""
    return {k: list(v) for k, v in INDUSTRY_TAXONOMY.items()}


def get_sub_industries(industry: str) -> List[str]:
    """Return sub-industries for a given primary industry."""
    canonical = normalize_industry(industry)
    return INDUSTRY_TAXONOMY.get(canonical, ["Unknown"])


def normalize_industry(name: Optional[str]) -> str:
    """Normalize input industry string to canonical taxonomy name, defaulting to Unknown."""
    if not name or not name.strip():
        return "Unknown"
    cleaned = name.strip().lower()
    if cleaned in _NORMALIZED_LOOKUP:
        return _NORMALIZED_LOOKUP[cleaned]

    # Use word boundary search to avoid substring bleed (e.g. 'tech' in 'agritech', 'it' in 'hospital')
    for key, canonical in _NORMALIZED_LOOKUP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", cleaned):
            return canonical

    return "Other" if cleaned not in ["unknown", "none", "n/a"] else "Unknown"


def is_valid_industry(name: str) -> bool:
    """Check if name matches a primary industry."""
    return normalize_industry(name) in PRIMARY_INDUSTRIES


# Keyword Signals mapping for rules & LLM hints
INDUSTRY_SIGNALS: Dict[str, Dict[str, Any]] = {
    "Healthcare": {
        "keywords": [
            "hospital", "hospitals", "clinic", "clinics", "patient", "patients",
            "medical", "medicine", "doctor", "doctors", "physician", "healthcare",
            "health care", "pharmaceutical", "pharma", "clinical", "nursing",
            "ehr", "emr", "telehealth", "telemedicine", "pathology", "radiology",
            "surgical", "biotech", "dental", "ambulatory",
        ],
        "phrases": [
            "patient management", "hospital management", "medical equipment",
            "electronic health record", "clinical trial", "healthcare tech",
            "medical center", "healthcare facility", "operate a hospital",
            "run a clinic", "dental practice", "health clinic", "medical practice",
        ],
        "sub_industry_map": {
            "hospital": "Hospitals",
            "clinic": "Clinics",
            "pharma": "Pharmaceuticals",
            "equipment": "Medical Equipment",
            "software": "Healthcare Technology",
            "patient": "Hospital Services",
        },
    },
    "IT & Software": {
        "keywords": [
            "software", "saas", "application", "apps", "developer", "developers",
            "it consulting", "cloud", "aws", "azure", "cybersecurity", "api",
            "database", "backend", "frontend", "devops", "coding", "web development",
            "mobile app", "tech company", "it services", "digital agency",
        ],
        "phrases": [
            "it company", "software company", "software development", "tech startup",
            "web development", "mobile application", "cloud infrastructure",
            "it consulting firm", "develop software", "custom software",
            "system integration", "digital solutions", "saas platform",
        ],
        "sub_industry_map": {
            "saas": "SaaS",
            "web": "Web Development",
            "cloud": "Cloud Services",
            "security": "Cybersecurity",
            "consulting": "IT Consulting",
            "software": "Software Development",
        },
    },
    "Banking & Finance": {
        "keywords": [
            "bank", "banking", "finance", "financial", "accounting", "accountant",
            "taxation", "taxes", "fintech", "wealth", "investment", "audit",
            "auditing", "payroll", "cpa", "ledger", "bookkeeping", "lending",
            "loans", "mortgage", "treasury",
        ],
        "phrases": [
            "financial services", "accounting firm", "wealth management",
            "tax consulting", "core banking", "payment gateway", "investment firm",
            "fintech solution", "chartered accountant", "audit report",
        ],
        "sub_industry_map": {
            "bank": "Banking",
            "account": "Accounting",
            "tax": "Taxation",
            "fintech": "Fintech",
            "finance": "Financial Services",
        },
    },
    "Insurance": {
        "keywords": [
            "insurance", "insurer", "underwriting", "policy", "premium", "claim",
            "claims", "actuary", "coverage", "reinsurance",
        ],
        "phrases": [
            "life insurance", "health insurance", "general insurance", "claims management",
            "insurance policy", "insurance broker", "property insurance",
        ],
        "sub_industry_map": {
            "life": "Life Insurance",
            "health": "Health Insurance",
            "general": "General Insurance",
            "claim": "General Insurance",
        },
    },
    "Education": {
        "keywords": [
            "school", "schools", "college", "colleges", "university", "universities",
            "student", "students", "teacher", "teachers", "faculty", "e-learning",
            "elearning", "edtech", "academy", "curriculum", "campus", "tuition",
            "institute", "lms",
        ],
        "phrases": [
            "learning management system", "training institute", "educational technology",
            "online courses", "school management", "student portal", "higher education",
        ],
        "sub_industry_map": {
            "school": "Schools",
            "college": "Colleges",
            "elearning": "E-learning",
            "lms": "Educational Technology",
            "institute": "Training Institutes",
        },
    },
    "Manufacturing": {
        "keywords": [
            "manufacture", "manufacturing", "manufacturer", "factory", "industrial",
            "machinery", "automotive", "automobile", "assembly", "fabrication",
            "oem", "production line", "components", "electronics", "chemicals",
        ],
        "phrases": [
            "automotive components", "industrial machinery", "manufacturing plant",
            "component manufacturing", "parts manufacturer", "electronics manufacturing",
            "consumer goods manufacturing", "chemical production", "oem supplier",
        ],
        "sub_industry_map": {
            "automotive": "Automotive",
            "automobile": "Automotive",
            "machinery": "Industrial Machinery",
            "electronic": "Electronics",
            "chemical": "Chemical Manufacturing",
            "consumer": "Consumer Goods",
        },
    },
    "Retail & E-commerce": {
        "keywords": [
            "retail", "retailer", "ecommerce", "e-commerce", "store", "stores",
            "shop", "shopping", "merchandise", "fashion", "clothing", "apparel",
            "boutique", "wholesale", "cart", "catalog", "checkout", "garments",
        ],
        "phrases": [
            "clothing business", "e-commerce website", "online retail", "fashion brand",
            "retail store", "online shop", "apparel store", "wholesale supplier",
            "direct to consumer", "ecommerce platform", "shopping portal",
        ],
        "sub_industry_map": {
            "fashion": "Fashion",
            "clothing": "Fashion",
            "apparel": "Fashion",
            "ecommerce": "Online Retail",
            "online": "Online Retail",
            "wholesale": "Wholesale",
            "retail": "Retail Stores",
        },
    },
    "Real Estate & Construction": {
        "keywords": [
            "property", "properties", "real estate", "realtor", "realty", "builder",
            "construction", "residential", "commercial", "housing", "apartments",
            "architect", "architecture", "interior design", "civil engineering",
        ],
        "phrases": [
            "real estate agency", "property management", "residential property",
            "commercial property", "construction company", "building contractor",
            "interior design studio", "property listings",
        ],
        "sub_industry_map": {
            "residential": "Residential Property",
            "commercial": "Commercial Property",
            "construction": "Construction",
            "property": "Property Management",
        },
    },
    "Logistics & Transportation": {
        "keywords": [
            "logistics", "shipping", "freight", "warehouse", "warehousing",
            "transport", "transportation", "cargo", "courier", "fleet",
            "supply chain", "trucking", "dispatch",
        ],
        "phrases": [
            "freight forwarding", "supply chain management", "courier services",
            "warehouse management", "shipping company", "fleet tracking",
        ],
        "sub_industry_map": {
            "shipping": "Shipping",
            "warehouse": "Warehousing",
            "supply chain": "Supply Chain",
            "transport": "Transportation",
        },
    },
    "Telecommunications": {
        "keywords": [
            "telecom", "telecommunications", "networking", "broadband", "voip",
            "cellular", "fiber", "isp", "wireless", "telephony",
        ],
        "phrases": [
            "telecom services", "unified communications", "network infrastructure",
            "broadband provider", "voip system",
        ],
        "sub_industry_map": {
            "network": "Networking",
            "voip": "Communication Technology",
            "telecom": "Telecom Services",
        },
    },
    "Hospitality & Tourism": {
        "keywords": [
            "hotel", "hotels", "resort", "resorts", "restaurant", "restaurants",
            "cafe", "tourism", "tourist", "travel", "hospitality", "catering",
            "gym", "gyms", "fitness", "booking", "guest",
        ],
        "phrases": [
            "hotel management", "travel agency", "restaurant chain", "tour operator",
            "gym business", "fitness center", "hospitality services",
        ],
        "sub_industry_map": {
            "hotel": "Hotels",
            "restaurant": "Restaurants",
            "travel": "Travel Agencies",
            "tourism": "Tourism",
            "gym": "Fitness & Gyms",
            "fitness": "Fitness & Gyms",
        },
    },
    "Agriculture": {
        "keywords": [
            "agriculture", "farming", "farm", "crops", "agritech", "dairy",
            "livestock", "fertilizer", "pesticide", "cultivation", "harvest",
        ],
        "phrases": [
            "agricultural equipment", "smart farming", "crop management",
            "food production", "agritech startup",
        ],
        "sub_industry_map": {
            "farm": "Farming",
            "equipment": "Agricultural Equipment",
            "tech": "AgriTech",
            "food": "Food Production",
        },
    },
    "Energy & Utilities": {
        "keywords": [
            "energy", "electricity", "solar", "renewable", "power", "grid",
            "utilities", "oil", "gas", "cleantech", "wind energy",
        ],
        "phrases": [
            "renewable energy", "solar power", "oil and gas", "utility company",
            "clean energy", "power generation",
        ],
        "sub_industry_map": {
            "solar": "Solar Energy",
            "renewable": "Renewable Energy",
            "electricity": "Electricity",
            "oil": "Oil & Gas",
            "utility": "Utilities",
        },
    },
    "Marketing & Advertising": {
        "keywords": [
            "marketing", "advertising", "branding", "seo", "pr", "creative agency",
            "campaign", "adwords", "social media", "public relations",
        ],
        "phrases": [
            "digital marketing agency", "advertising campaign", "brand identity",
            "social media marketing", "seo services", "content marketing",
        ],
        "sub_industry_map": {
            "digital": "Digital Marketing",
            "advertising": "Advertising",
            "brand": "Branding",
            "seo": "SEO",
            "social": "Social Media Marketing",
        },
    },
    "Legal & Professional Services": {
        "keywords": [
            "legal", "lawyer", "attorney", "law firm", "consultant", "consulting",
            "recruitment", "staffing", "litigation", "corporate law", "advisory",
        ],
        "phrases": [
            "law firm", "legal services", "management consulting", "recruitment agency",
            "staffing services", "corporate legal",
        ],
        "sub_industry_map": {
            "legal": "Legal Services",
            "consult": "Consulting",
            "recruit": "Recruitment",
            "staff": "Recruitment",
        },
    },
}
