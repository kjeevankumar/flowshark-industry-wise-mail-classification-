"""Ground-truth labelled benchmark dataset for email intelligence evaluation.

Covers:
- New enquiries (website, pricing, vendor discovery)
- Negotiations (discounts, budget pushback, payment terms)
- Follow-ups (reminders, status checks, pending proposals)
- Business clarifications (scope, technical stack, timeline)
- Purchase orders (formal PO numbers, confirmations)
- Invoices (billing, payment confirmations, remittance)
- Complaints (delays, defects, performance issues)
- Negated statements (e.g. 'not looking for a vendor', 'cannot offer discount')
- Newsletters, automated alerts & spam
"""

from typing import Dict, List, NamedTuple


class BenchmarkSample(NamedTuple):
    id: str
    subject: str
    body: str
    expected_relationship: str
    expected_intent: str
    expected_lead_stage: str
    is_negation_test: bool = False
    notes: str = ""


BENCHMARK_DATASET: List[BenchmarkSample] = [
    # 1. New Enquiries
    BenchmarkSample(
        id="BENCH-001",
        subject="Inquiry regarding custom web application development",
        body="Hi Team,\n\nWe are looking for a website and mobile app development partner for our retail startup. Could you please share your service enquiry brochure and request a quotation for an initial MVP?\n\nBest regards,\nPriya Sharma",
        expected_relationship="new_contact",
        expected_intent="new_enquiry",
        expected_lead_stage="new",
        notes="Standard clear new lead enquiry",
    ),
    BenchmarkSample(
        id="BENCH-002",
        subject="Request for quotation: Cloud Migration Services",
        body="Hello,\n\nOur company is interested in your services for migrating our legacy infrastructure to AWS. We are looking for a vendor who can handle compliance and DevOps.\n\nThanks,\nMichael Brown",
        expected_relationship="new_contact",
        expected_intent="new_enquiry",
        expected_lead_stage="new",
        notes="Enterprise vendor search",
    ),

    # 2. Negotiations
    BenchmarkSample(
        id="BENCH-003",
        subject="Re: Proposal for E-commerce Platform",
        body="Hi Vikram,\n\nWe reviewed the proposal you sent yesterday. While the scope looks comprehensive, the total cost of ₹5,00,000 is slightly out of our budget. Can you offer a 15% discount or reconsider the pricing to reduce the price? We are flexible on the payment terms.\n\nRegards,\nSunil Nair",
        expected_relationship="existing_lead",
        expected_intent="negotiation",
        expected_lead_stage="negotiation",
        notes="Active pricing discount request on proposal",
    ),
    BenchmarkSample(
        id="BENCH-004",
        subject="Re: Web redesign contract discussion",
        body="Hello,\n\nBefore signing, can we negotiate the final price? What is the best price you can offer if we pay 50% upfront?\n\nSincerely,\nKaren White",
        expected_relationship="existing_lead",
        expected_intent="negotiation",
        expected_lead_stage="negotiation",
        notes="Contract price negotiation",
    ),

    # 3. Follow-ups
    BenchmarkSample(
        id="BENCH-005",
        subject="Re: Marketing Automation Proposal",
        body="Hi Rahul,\n\nJust following up on our meeting last Thursday. Any update regarding the revised quotation? Awaiting your response so we can present it to the board.\n\nBest,\nDavid Miller",
        expected_relationship="existing_lead",
        expected_intent="follow_up",
        expected_lead_stage="proposal_sent",
        notes="Gentle reminder awaiting response",
    ),
    BenchmarkSample(
        id="BENCH-006",
        subject="Checking on project timeline & deliverables",
        body="Hello team,\n\nGentle reminder to check the status update on our contract draft. Did you get a chance to review the legal comments?\n\nThanks,\nAnita Roy",
        expected_relationship="existing_lead",
        expected_intent="follow_up",
        expected_lead_stage="proposal_sent",
        notes="Timeline check on contract",
    ),

    # 4. Business Clarifications
    BenchmarkSample(
        id="BENCH-007",
        subject="Questions regarding API architecture and delivery timeline",
        body="Hi Team,\n\nPlease clarify what is included in the Phase 1 delivery timeline. Could you also explain the scope of automated testing and technical requirements for hosting?\n\nRegards,\nGeorge Chen",
        expected_relationship="existing_lead",
        expected_intent="business_clarification",
        expected_lead_stage="qualified",
        notes="Scope and architecture clarification",
    ),
    BenchmarkSample(
        id="BENCH-008",
        subject="Clarification on ongoing maintenance details",
        body="Hello,\n\nCould you clarify the SLA response times in your maintenance details? Does the package include 24/7 server monitoring?\n\nThanks,\nFatima Al-Mansoor",
        expected_relationship="existing_lead",
        expected_intent="business_clarification",
        expected_lead_stage="qualified",
        notes="SLA and maintenance clarification",
    ),

    # 5. Purchase Orders
    BenchmarkSample(
        id="BENCH-009",
        subject="Purchase Order #PO-2026-8942 Attached",
        body="Dear Team,\n\nPlease find enclosed PO #PO-2026-8942 for the approved security audit project. Please send order confirmation and initiate onboarding.\n\nRegards,\nCorporate Procurement Dept",
        expected_relationship="existing_customer",
        expected_intent="purchase_order",
        expected_lead_stage="won",
        notes="Official purchase order dispatch",
    ),

    # 6. Invoices & Payments
    BenchmarkSample(
        id="BENCH-010",
        subject="Invoice #INV-4410: Payment Confirmation",
        body="Hi Accounts,\n\nAttached is the wire transfer payment confirmation for invoice #INV-4410. Outstanding amount is now cleared.\n\nThank you,\nFinance Operations",
        expected_relationship="existing_customer",
        expected_intent="invoice",
        expected_lead_stage="won",
        notes="Invoice settlement advice",
    ),

    # 7. Complaints
    BenchmarkSample(
        id="BENCH-011",
        subject="URGENT: Production Server Downtime & Issue With Database",
        body="Hello,\n\nThe production reporting dashboard is not working since this morning. This is an unacceptable delay for our operations. Please look into this critical bug immediately.\n\nRegards,\nOperations Lead",
        expected_relationship="existing_customer",
        expected_intent="complaint",
        expected_lead_stage="qualified",
        notes="Severity 1 customer issue",
    ),

    # 8. Negations & False-Positive Traps
    BenchmarkSample(
        id="BENCH-012",
        subject="Not looking for website services at this time",
        body="Hi,\n\nWe received your cold pitch. Please note we are NOT interested in your services and we are not looking for a website redesign right now. Please remove us from your list.\n\nThanks,\nAlex",
        expected_relationship="unknown",
        expected_intent="other",
        expected_lead_stage="lost",
        is_negation_test=True,
        notes="Explicit negation: contains 'interested' and 'looking for a website' but prefixed by NOT",
    ),
    BenchmarkSample(
        id="BENCH-013",
        subject="Budget is non-negotiable / Cannot reduce price",
        body="Dear Vendor,\n\nWe reviewed your counter proposal. Our budget is fixed and we cannot offer a discount or reduce the price any further.\n\nRegards,\nDirector",
        expected_relationship="existing_lead",
        expected_intent="negotiation",
        expected_lead_stage="negotiation",
        is_negation_test=True,
        notes="Pricing rigidity negotiation signal",
    ),

    # 9. Promotional / Spam / Automated Newsletters
    BenchmarkSample(
        id="BENCH-014",
        subject="Your 20% Cyber Month discount is waiting inside!",
        body="Exclusive savings for you! Click here to view in browser.\nUse promo code CYBER20 to save on selected courses.\nIf you no longer wish to receive these emails, unsubscribe here.\nPrivacy policy | Terms and conditions",
        expected_relationship="unknown",
        expected_intent="other",
        expected_lead_stage="unknown",
        notes="Marketing broadcast email",
    ),
    BenchmarkSample(
        id="BENCH-015",
        subject="Weekly Tech Digest: Issue #412",
        body="Here is your weekly summary of artificial intelligence news.\nRead the full issue online.\nTo manage preferences or unsubscribe, visit our portal.\nCopyright 2026 Tech Weekly Inc.",
        expected_relationship="unknown",
        expected_intent="other",
        expected_lead_stage="unknown",
        notes="Content newsletter",
    ),
]

