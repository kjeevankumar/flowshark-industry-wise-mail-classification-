"""Ground-truth labelled benchmark dataset for Industry-Wise Email Classification evaluation.

Covers:
- All 15 B2B industries in the FlowShark taxonomy.
- Cross-industry B2B service inquiries (e.g. IT developing for Hospitals).
- Single-industry domain inquiries.
- Ambiguous & low-signal emails (abstention tests expecting 'Unknown').
- Contextual inquiries.
"""

from typing import List, NamedTuple, Optional


class IndustryBenchmarkSample(NamedTuple):
    id: str
    sender: str
    subject: str
    body: str
    expected_sender_industry: str
    expected_target_industry: str
    expected_sub_industry: Optional[str] = None
    is_cross_industry: bool = False
    is_ambiguous: bool = False
    notes: str = ""


INDUSTRY_BENCHMARK_DATASET: List[IndustryBenchmarkSample] = [
    # 1. IT & Software
    IndustryBenchmarkSample(
        id="IND-001",
        sender="CloudScale Systems <sales@cloudscale.io>",
        subject="SaaS Cloud Migration & Cybersecurity Audit",
        body="Hello, we are a cloud services and cybersecurity software provider offering enterprise cloud infrastructure migration.",
        expected_sender_industry="IT & Software",
        expected_target_industry="IT & Software",
        expected_sub_industry="Cloud Services",
        notes="Pure IT & Software cloud vendor",
    ),

    # 2. Healthcare
    IndustryBenchmarkSample(
        id="IND-002",
        sender="Apex Diagnostics <admin@apexhealth.org>",
        subject="Hospital patient records management system",
        body="We are a multi-speciality hospital and clinic network in need of an electronic medical records management platform.",
        expected_sender_industry="Healthcare",
        expected_target_industry="Healthcare",
        expected_sub_industry="Hospitals",
        notes="Healthcare organization seeking healthcare solution",
    ),

    # 3. Banking & Finance
    IndustryBenchmarkSample(
        id="IND-003",
        sender="Premier Capital <invest@premiercapital.com>",
        subject="Fintech banking gateway integration and taxation portal",
        body="Our investment banking firm needs automated accounting, loan calculation and taxation compliance reporting software.",
        expected_sender_industry="Banking & Finance",
        expected_target_industry="Banking & Finance",
        expected_sub_industry="Fintech",
        notes="Financial institution requesting fintech platform",
    ),

    # 4. Insurance
    IndustryBenchmarkSample(
        id="IND-004",
        sender="Shield Life <claims@shieldlife.com>",
        subject="Health insurance policy underwriting portal",
        body="We are an insurance firm looking to develop a customer portal for life insurance claims and health insurance policy renewals.",
        expected_sender_industry="Insurance",
        expected_target_industry="Insurance",
        expected_sub_industry="Life Insurance",
        notes="Insurance company policy portal",
    ),

    # 5. Education
    IndustryBenchmarkSample(
        id="IND-005",
        sender="Horizon Academy <dean@horizon.edu>",
        subject="E-learning management system for college students",
        body="Our university and colleges require an LMS e-learning platform with automated student grading and training courses.",
        expected_sender_industry="Education",
        expected_target_industry="Education",
        expected_sub_industry="E-learning",
        notes="Higher education e-learning requirement",
    ),

    # 6. Manufacturing
    IndustryBenchmarkSample(
        id="IND-006",
        sender="Precision Dynamics <rfq@precisionmfg.com>",
        subject="Automotive component manufacturing and CNC machinery supply",
        body="We manufacture automotive components, industrial machinery and precision engineering spare parts for assembly plants.",
        expected_sender_industry="Manufacturing",
        expected_target_industry="Manufacturing",
        expected_sub_industry="Automotive",
        notes="Automotive parts manufacturing supplier",
    ),

    # 7. Retail & E-commerce
    IndustryBenchmarkSample(
        id="IND-007",
        sender="Velvet Threads <team@velvetthreads.store>",
        subject="Shopify e-commerce online retail clothing store",
        body="We run an online retail fashion boutique and require a modern Shopify e-commerce shopping website with inventory sync.",
        expected_sender_industry="Retail & E-commerce",
        expected_target_industry="Retail & E-commerce",
        expected_sub_industry="Online Retail",
        notes="Fashion apparel e-commerce store",
    ),

    # 8. Real Estate & Construction
    IndustryBenchmarkSample(
        id="IND-008",
        sender="Landmark Developers <info@landmarkbuilders.com>",
        subject="Commercial property and residential construction listing site",
        body="We are commercial real estate developers constructing luxury residential apartments and need a property management booking site.",
        expected_sender_industry="Real Estate & Construction",
        expected_target_industry="Real Estate & Construction",
        expected_sub_industry="Construction",
        notes="Real estate builders and developers",
    ),

    # 9. Logistics & Transportation
    IndustryBenchmarkSample(
        id="IND-009",
        sender="Global Freight Logistics <dispatch@globalfreight.net>",
        subject="Supply chain freight tracking and warehousing logistics",
        body="Our shipping and logistics company manages sea freight, fleet trucking, and nationwide warehousing dispatch operations.",
        expected_sender_industry="Logistics & Transportation",
        expected_target_industry="Logistics & Transportation",
        expected_sub_industry="Shipping",
        notes="Freight logistics and fleet dispatch",
    ),

    # 10. Telecommunications
    IndustryBenchmarkSample(
        id="IND-010",
        sender="NexWave Telecom <support@nexwavetel.com>",
        subject="Broadband telecom network infrastructure expansion",
        body="We provide fiber broadband telecommunications and 5G networking services to metropolitan enterprise networks.",
        expected_sender_industry="Telecommunications",
        expected_target_industry="Telecommunications",
        expected_sub_industry="Telecom Services",
        notes="Telecom provider networking",
    ),

    # 11. Hospitality & Tourism
    IndustryBenchmarkSample(
        id="IND-011",
        sender="Golden Sands Resort <concierge@goldensands.com>",
        subject="Luxury hotel room booking and restaurant dining system",
        body="Our luxury beach resort hotel and fine dining restaurant require an integrated online room reservation and travel guest portal.",
        expected_sender_industry="Hospitality & Tourism",
        expected_target_industry="Hospitality & Tourism",
        expected_sub_industry="Hotels",
        notes="Resort hotel and restaurant reservation",
    ),

    # 12. Agriculture
    IndustryBenchmarkSample(
        id="IND-012",
        sender="AgriHarvest Corp <ops@agriharvest.in>",
        subject="AgriTech smart farming crop sensors and greenhouse equipment",
        body="We are an agritech company providing precision farming sensors, irrigation equipment, and organic crop food production solutions.",
        expected_sender_industry="Agriculture",
        expected_target_industry="Agriculture",
        expected_sub_industry="AgriTech",
        notes="AgriTech farming equipment",
    ),

    # 13. Energy & Utilities
    IndustryBenchmarkSample(
        id="IND-013",
        sender="SunPower Renewables <clean@sunpowerrenew.com>",
        subject="Solar solar power grid utility monitoring system",
        body="We operate commercial solar renewable energy power plants and electricity utility distribution infrastructure.",
        expected_sender_industry="Energy & Utilities",
        expected_target_industry="Energy & Utilities",
        expected_sub_industry="Renewable Energy",
        notes="Solar renewable utility power plant",
    ),

    # 14. Marketing & Advertising
    IndustryBenchmarkSample(
        id="IND-014",
        sender="Pixel Wave Media <growth@pixelwave.agency>",
        subject="Digital marketing SEO and social media advertising campaign",
        body="Our digital marketing agency specializes in SEO ranking, PPC performance advertising, branding, and content creation.",
        expected_sender_industry="Marketing & Advertising",
        expected_target_industry="Marketing & Advertising",
        expected_sub_industry="Digital Marketing",
        notes="Digital marketing and branding agency",
    ),

    # 15. Legal & Professional Services
    IndustryBenchmarkSample(
        id="IND-015",
        sender="Blackstone Legal LLP <counsel@blackstonelegal.com>",
        subject="Corporate legal litigation and attorney consulting services",
        body="We are a corporate law firm providing business contract drafting, dispute litigation, and regulatory compliance consulting.",
        expected_sender_industry="Legal & Professional Services",
        expected_target_industry="Legal & Professional Services",
        expected_sub_industry="Legal Services",
        notes="Corporate law firm legal services",
    ),

    # ==========================================
    # Cross-Industry Scenarios (Sender != Target)
    # ==========================================

    # 16. IT developing software for Healthcare
    IndustryBenchmarkSample(
        id="IND-016",
        sender="DevStudio Technologies <contact@devstudio.com>",
        subject="Software development for hospitals and patient care clinics",
        body="We are an IT services company. We want to develop custom medical software for multi-speciality hospitals.",
        expected_sender_industry="IT & Software",
        expected_target_industry="Healthcare",
        expected_sub_industry="Healthcare Technology",
        is_cross_industry=True,
        notes="IT company building software for Healthcare",
    ),

    # 17. IT building e-commerce for Retail
    IndustryBenchmarkSample(
        id="IND-017",
        sender="ByteCraft Labs <info@bytecraft.io>",
        subject="Custom web app development for online retail clothing stores",
        body="We are a software development agency building automated checkout systems for e-commerce and retail fashion brands.",
        expected_sender_industry="IT & Software",
        expected_target_industry="Retail & E-commerce",
        expected_sub_industry="Online Retail",
        is_cross_industry=True,
        notes="Software agency building retail platform",
    ),

    # 18. Marketing agency serving Hospitality & Tourism
    IndustryBenchmarkSample(
        id="IND-018",
        sender="Echo Marketing <hello@echomedia.com>",
        subject="Promotional advertising campaign for boutique hotels and resorts",
        body="We are a digital marketing and advertising agency running social media campaigns for hotels, travel resorts, and tourism.",
        expected_sender_industry="Marketing & Advertising",
        expected_target_industry="Hospitality & Tourism",
        expected_sub_industry="Hotels",
        is_cross_industry=True,
        notes="Marketing agency targeting hospitality resorts",
    ),

    # 19. Consulting firm advising Banking & Finance
    IndustryBenchmarkSample(
        id="IND-019",
        sender="Apex Management Advisory <advisory@apexconsulting.com>",
        subject="Regulatory audit and compliance advisory for commercial banks",
        body="We provide corporate legal and management consulting advisory services for commercial banks and fintech lenders.",
        expected_sender_industry="Legal & Professional Services",
        expected_target_industry="Banking & Finance",
        expected_sub_industry="Banking",
        is_cross_industry=True,
        notes="Professional consulting firm serving banking",
    ),

    # ==========================================
    # Ambiguous & Low-Signal Abstention Cases
    # ==========================================

    # 20. Short ambiguous quote request
    IndustryBenchmarkSample(
        id="IND-020",
        sender="John Doe <john.doe@gmail.com>",
        subject="Quotation enquiry",
        body="Please share the quotation and pricing details at your earliest convenience.",
        expected_sender_industry="Unknown",
        expected_target_industry="Unknown",
        expected_sub_industry=None,
        is_ambiguous=True,
        notes="Generic request with zero industry indicators",
    ),

    # 21. Scheduling request
    IndustryBenchmarkSample(
        id="IND-021",
        sender="David Miller <david@somewhere.com>",
        subject="Meeting availability",
        body="Can we schedule a 15-minute quick call tomorrow afternoon to discuss next steps?",
        expected_sender_industry="Unknown",
        expected_target_industry="Unknown",
        expected_sub_industry=None,
        is_ambiguous=True,
        notes="Generic calendar invite without industry mention",
    ),

    # 22. Acknowledgement
    IndustryBenchmarkSample(
        id="IND-022",
        sender="Sarah Jenkins <sarah@domain.org>",
        subject="Thank you",
        body="Thank you for sharing the document. We will review internally and get back to you.",
        expected_sender_industry="Unknown",
        expected_target_industry="Unknown",
        expected_sub_industry=None,
        is_ambiguous=True,
        notes="Short conversational thank you email",
    ),
]
