# /usr/bin/env python
import asyncio

import structlog
from weaviate.classes.config import Configure, DataType, Property

from wallstr.documents.weaviate import get_weaviate_client
from wallstr.logging import configure_logging

configure_logging(name="migrate_weaviate")

logger = structlog.get_logger()


async def migrate_weaviate() -> None:
    logger.info("Migrating Weaviate")
    wvc = get_weaviate_client(with_openai=True)
    await wvc.connect()
    if not await wvc.collections.exists("Documents"):
        logger.info("Creating collection [Documents]")
        await wvc.collections.create(
            "Documents",
            multi_tenancy_config=Configure.multi_tenancy(
                enabled=True, auto_tenant_creation=True
            ),
            vectorizer_config=Configure.Vectorizer.text2vec_openai(
                model="text-embedding-3-small",
            ),
            properties=[
                Property(name="record_id", data_type=DataType.UUID),
                Property(name="user_id", data_type=DataType.UUID),
                Property(name="document_id", data_type=DataType.UUID),
            ],
        )

    if not await wvc.collections.exists("Prompts"):
        logger.info("Creating collection [Prompts]")
        prompts_collection = await wvc.collections.create(
            "Prompts",
            vectorizer_config=Configure.Vectorizer.text2vec_openai(
                model="text-embedding-3-small",
            ),
            properties=[
                Property(name="prompt", data_type=DataType.TEXT),
                Property(name="data_set", data_type=DataType.TEXT),
                Property(name="sources", data_type=DataType.TEXT),
                Property(name="reply", data_type=DataType.TEXT),
            ],
        )
        await prompts_collection.data.insert_many(objects=prompts)
    await wvc.close()
    logger.info("Migrating Weaviate done")


prompts = [
    {
        "prompt": "What does the business do?",
        "data_set": "Business description, segment details, industry classification",
        "sources": "10-K, Investor Presentations, Industry Reports",
        "reply": "Company X operates in the cloud computing sector, providing SaaS solutions for enterprise clients, with $5B ARR and 20% YoY growth.",
        "tags": ["high_level"],
    },
    {
        "prompt": "What are key factors affecting capital recovery?",
        "data_set": "ROI metrics, cash flow sustainability (3-5 years)",
        "sources": "10-K (Cash Flow Statement), Earnings Calls",
        "reply": "Company X has an ROIC of 15%, FCF margin of 18%, and reinvests 30% of revenue into R&D, ensuring long-term scalability.",
        "tags": ["high_level"],
    },
    {
        "prompt": "What does the product/service do?",
        "data_set": "Core functionality, customer pain points solved",
        "sources": "Investor Presentations, Customer Reviews",
        "reply": "Company X provides AI-driven analytics to optimize supply chains, reducing costs by 20%.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "Does the product solve a real problem?",
        "data_set": "Efficiency gains, cost savings, regulatory compliance impact",
        "sources": "Customer Feedback, Case Studies",
        "reply": "Company X's platform reduces processing times by 50%, ensuring compliance with new regulations.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "Is demand discretionary or non-discretionary?",
        "data_set": "Retention rates, cyclicality trends (5 years)",
        "sources": "10-K, Market Reports",
        "reply": "85% of revenue comes from multi-year contracts, indicating non-discretionary demand.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "Is the product a fad?",
        "data_set": "Historical demand trends, industry stability",
        "sources": "Market Research, Competitor Analysis",
        "reply": "Growth has remained consistent at ~12% CAGR over the last decade, indicating a sustainable market.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "Who is the typical customer?",
        "data_set": "B2B: Size, location, employee count, industry mix. B2C: Age, income, credit score, geography",
        "sources": "10-K, Industry Reports, Customer Surveys",
        "reply": "Company X serves mid-to-large enterprises in the financial sector, with an average contract value of $500K annually.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "How frequently are purchasing decisions made?",
        "data_set": "Purchase cycle, repeat order frequency",
        "sources": "Customer Surveys, Financial Reports",
        "reply": "Customers typically renew contracts every 2 years, with an 80% retention rate.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "What are the company’s liabilities if the product fails?",
        "data_set": "Legal liabilities, customer refund risks",
        "sources": "10-K (Risk Section), Legal Filings",
        "reply": "Company X has a $50M insurance fund for liability claims.",
        "tags": ["product_analysis"],
    },
    {
        "prompt": "Who is the typical customer?",
        "data_set": "B2B: Size, location, employee count, industry mix. B2C: Age, income, credit score, geography",
        "sources": "10-K, Industry Reports, Customer Surveys",
        "reply": "Company X serves mid-to-large enterprises in the financial sector, with an average contract value of $500K annually.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "Is there DIY risk for customers?",
        "data_set": "Competitive threats from in-house solutions",
        "sources": "Customer Surveys, Industry Analysis",
        "reply": "Only 5% of clients attempt in-house solutions due to complexity.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "What is the customer concentration risk?",
        "data_set": "% of revenue from top 1, 5, 10 customers",
        "sources": "10-K, Earnings Calls",
        "reply": "The top 10 customers contribute 40% of total revenue, with the largest single client accounting for 8%.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "Is the business contractual or transactional?",
        "data_set": "Contract length, break costs, contract value trends",
        "sources": "10-K, Earnings Reports",
        "reply": "80% of revenue comes from 3-year contracts, with a 90% renewal rate.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "Are end-users and purchasers the same?",
        "data_set": "Description of decision-making process, procurement structure",
        "sources": "Customer Research, CRM Data",
        "reply": "Purchasers are procurement teams, while end-users are operations teams requiring extensive onboarding support.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "Are customers exclusive to the company?",
        "data_set": "Multi-provider usage, vendor stickiness",
        "sources": "Industry Reports, Market Surveys",
        "reply": "60% of customers use multiple vendors, but Company X retains the largest share.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "Does geography matter for customers?",
        "data_set": "Regional demand, cost sensitivity, localization needs",
        "sources": "Market Research, Customer Data",
        "reply": "North America contributes 70% of revenue, with Europe showing the highest growth at 15% YoY.",
        "tags": ["customer_profile"],
    },
    {
        "prompt": "What is the revenue model?",
        "data_set": "Recurring vs. one-time revenue split (3-5 years), revenue from new vs. repeat customers, upsells, and volume-based revenue share",
        "sources": "10-K, Earnings Reports, Investor Presentations",
        "reply": "70% of revenue is recurring, with an average contract length of 2.5 years. Upsells contribute 20% of ARR growth.",
        "tags": ["gtm"],
    },
    {
        "prompt": "How does the company reach customers?",
        "data_set": "Sales vs. marketing-led, direct vs. intermediaries/distributors",
        "sources": "10-K, Investor Presentations, Sales Data",
        "reply": "Company X relies on a hybrid model: 60% of sales from direct enterprise reps and 40% from channel partners.",
        "tags": ["gtm"],
    },
    {
        "prompt": "How long is the sales cycle?",
        "data_set": "Average deal closure time, complexity of procurement (RFPs, multiple rounds)",
        "sources": "CRM Data, Sales Reports, Earnings Calls",
        "reply": "The sales cycle for enterprise deals averages 6 months with multiple decision-makers.",
        "tags": ["gtm"],
    },
    {
        "prompt": "Product implementation timeline",
        "data_set": "Implementation costs (covered by customer or company), historical delays, integration depth, switching costs",
        "sources": "Customer Feedback, Financial Reports",
        "reply": "Company X's average implementation time is 3 months, with $10K implementation costs covered by the customer.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What is the company’s backlog?",
        "data_set": "Value of contracted but unrecognized revenue",
        "sources": "Earnings Reports, Investor Calls",
        "reply": "Backlog stands at $500M, with a 12-month revenue conversion cycle.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What are historical win rates?",
        "data_set": "Absolute win rates and competitive head-to-head success rates",
        "sources": "Sales Reports, CRM Data",
        "reply": "Company X wins 35% of competitive RFPs, outperforming competitors in 2 out of 3 cases.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What are LTV and CAC trends?",
        "data_set": "5-year trend of LTV, CAC ratio, payback period",
        "sources": "Earnings Calls, Analyst Coverage Reports",
        "reply": "LTV/CAC ratio has improved from 3.2x to 4.5x, with CAC payback period at 9 months.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What is customer churn (gross and net)?",
        "data_set": "Gross churn, net retention (3-5 years), controllable vs. uncontrollable churn breakdown, cohort analysis",
        "sources": "Internal KPIs, Earnings Reports",
        "reply": "Net revenue retention is 115%, with a gross churn of 5% annually. 60% of churn is due to customer bankruptcy.",
        "tags": ["gtm"],
    },
    {
        "prompt": "How have target customers evolved?",
        "data_set": "Shifts in ideal customer profile, evolution of sales and marketing approach",
        "sources": "Investor Presentations, Market Reports",
        "reply": "Company X shifted from SMB to mid-market clients, improving ARPU by 30%.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What are cross-selling/unbundling trends?",
        "data_set": "% of customers buying multiple products, unbundling impact",
        "sources": "Internal Sales Data, Earnings Calls",
        "reply": "Cross-sell penetration increased from 25% to 40% in three years.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What is the pricing power?",
        "data_set": "Ability to pass cost increases to customers, power dynamics in relationships, transparency of input costs",
        "sources": "Pricing Reports, Industry Analysis",
        "reply": "Company X raised prices by 5% last year without impacting retention rates.",
        "tags": ["gtm"],
    },
    {
        "prompt": "Is there a maintenance revenue tail post-initial sale?",
        "data_set": "Revenue from maintenance contracts, customer support fees",
        "sources": "10-K, Earnings Reports",
        "reply": "Post-sale maintenance contributes 10% of annual revenue, with an average contract length of 5 years.",
        "tags": ["gtm"],
    },
    {
        "prompt": "B2C-specific: Any concerns about aggressive selling practices?",
        "data_set": "Regulatory risks, customer complaints, financing partner practices",
        "sources": "Consumer Protection Reports, Legal Filings",
        "reply": "Company X faced a class-action lawsuit for deceptive marketing to elderly consumers in 2021.",
        "tags": ["gtm"],
    },
    {
        "prompt": "What is the total addressable market (TAM)?",
        "data_set": "TAM, SAM, SOM (5-year forecast)",
        "sources": "Industry Reports, Market Research",
        "reply": "$50B TAM, with Company X addressing a $10B segment growing at 15% CAGR.",
        "tags": ["market"],
    },
    {
        "prompt": "What drives demand?",
        "data_set": "Population trends, economic indicators, regulatory impact",
        "sources": "Census Data, Economic Reports",
        "reply": "Growth in e-commerce adoption has driven a 20% YoY increase in demand for logistics solutions.",
        "tags": ["market"],
    },
    {
        "prompt": "How cyclical is the market?",
        "data_set": "Market cyclicality trends, macroeconomic sensitivity",
        "sources": "Economic Reports, Earnings Calls",
        "reply": "Demand for luxury goods is highly cyclical, contracting by 15% during recessions.",
        "tags": ["market"],
    },
    {
        "prompt": "What external factors impact demand?",
        "data_set": "Regulations, supply chain constraints, weather dependencies",
        "sources": "Government Reports, Industry Analysis",
        "reply": "New environmental regulations are expected to increase production costs by 10%.",
        "tags": ["market"],
    },
    {
        "prompt": "Are there physical constraints on growth?",
        "data_set": "Land availability, infrastructure limitations",
        "sources": "Real Estate Reports, Infrastructure Studies",
        "reply": "Limited warehouse space in urban areas may cap e-commerce growth rates.",
        "tags": ["market"],
    },
    {
        "prompt": "What are the most attractive market segments?",
        "data_set": "Revenue potential by customer type, industry-specific growth",
        "sources": "Market Research, Competitive Intelligence",
        "reply": "The mid-market segment is the fastest-growing, with 25% CAGR in the past 3 years.",
        "tags": ["market"],
    },
    {
        "prompt": "Who are the main competitors?",
        "data_set": "Market share, revenue, customer base",
        "sources": "Analyst Reports, 10-Ks",
        "reply": "Company X holds 25% of the market, competing with Company Y (30%) and Company Z (20%).",
        "tags": ["market"],
    },
    {
        "prompt": "How strong is pricing pressure from competitors?",
        "data_set": "Price sensitivity, freemium competition impact",
        "sources": "Competitor Pricing Studies, Customer Feedback",
        "reply": "Freemium alternatives have reduced Company X’s conversion rate by 5%.",
        "tags": ["market"],
    },
    {
        "prompt": "What are the key differentiators vs. competition?",
        "data_set": "Unique value propositions, product advantages",
        "sources": "Competitor Analysis, Customer Surveys",
        "reply": "Company X differentiates with superior AI-driven analytics and a 99% uptime guarantee.",
        "tags": ["market"],
    },
    {
        "prompt": "Where do new customers come from?",
        "data_set": "Competitor churn, organic market expansion",
        "sources": "Customer Acquisition Data, Industry Reports",
        "reply": "40% of new customers switched from Competitor Y due to better pricing.",
        "tags": ["market"],
    },
    {
        "prompt": "Who are the major ecosystem players beyond direct competitors?",
        "data_set": "Supply chain dependencies, adjacent industry threats",
        "sources": "Industry Analysis, M&A Reports",
        "reply": "Cloud service providers such as AWS are increasing their direct market presence.",
        "tags": ["market"],
    },
    {
        "prompt": "Can ecosystem players enter the space?",
        "data_set": "Vertical integration risks, supplier leverage",
        "sources": "Analyst Reports, Market Studies",
        "reply": "Major retailers are investing in private-label solutions, reducing reliance on external vendors.",
        "tags": ["market"],
    },
    {
        "prompt": "Are there licensing or regulatory requirements?",
        "data_set": "Compliance needs, industry certifications",
        "sources": "Government Filings, Legal Reports",
        "reply": "Company X must comply with GDPR and SOC 2 security standards to operate in the EU market.",
        "tags": ["market"],
    },
    {
        "prompt": "Who are the major ecosystem players beyond direct competitors?",
        "data_set": "Supply chain dependencies, adjacent industry threats",
        "sources": "Industry Analysis, M&A Reports",
        "reply": "Cloud service providers such as AWS are increasing their direct market presence.",
        "tags": ["market"],
    },
    {
        "prompt": "Can ecosystem players enter the space?",
        "data_set": "Vertical integration risks, supplier leverage",
        "sources": "Analyst Reports, Market Studies",
        "reply": "Major retailers are investing in private-label solutions, reducing reliance on external vendors.",
        "tags": ["market"],
    },
    {
        "prompt": "Are there licensing or regulatory requirements?",
        "data_set": "Compliance needs, industry certifications",
        "sources": "Government Filings, Legal Reports",
        "reply": "Company X must comply with GDPR and SOC 2 security standards to operate in the EU market.",
        "tags": ["market"],
    },
    {
        "prompt": "Organizational chart from CEO down",
        "data_set": "Key executives, reporting structure",
        "sources": "10-K, Investor Presentations, Company Filings",
        "reply": "Company X is led by CEO John Doe, with direct reports including CFO Jane Smith, CTO Alex Johnson, and CMO Emily White.",
        "tags": ["organization"],
    },
    {
        "prompt": "Key function concentration risks (sales, engineers, etc.)",
        "data_set": "% of workforce in critical functions",
        "sources": "10-K, Earnings Calls, Glassdoor Reviews",
        "reply": "Company X has 45% of its workforce in R&D, posing a risk if key engineers leave.",
        "tags": ["organization"],
    },
    {
        "prompt": "Staff retention rates",
        "data_set": "Employee turnover, average tenure (3-5 years)",
        "sources": "HR Reports, Glassdoor, LinkedIn Data",
        "reply": "The company’s retention rate for engineers is 88%, with an average tenure of 4.2 years.",
        "tags": ["organization"],
    },
    {
        "prompt": "Revenue per employee—any dependency on key personnel?",
        "data_set": "Revenue per employee, productivity metrics",
        "sources": "10-K, Analyst Reports",
        "reply": "Revenue per employee stands at $500K, with key sales personnel driving 30% of total bookings.",
        "tags": ["organization"],
    },
    {
        "prompt": "Compensation, benefits, stock options, and retention incentives",
        "data_set": "Salary benchmarks, equity incentives",
        "sources": "Proxy Statements, 10-K, Glassdoor Reviews",
        "reply": "Company X offers RSUs to all employees, with a 4-year vesting schedule and a 10% annual bonus structure.",
        "tags": ["organization"],
    },
    {
        "prompt": "Union exposure—% of workforce, relationships, contract details",
        "data_set": "% of employees unionized, contract terms",
        "sources": "10-K (Labor Relations), Industry Reports",
        "reply": "15% of the workforce is unionized, with contract negotiations due next year.",
        "tags": ["organization"],
    },
    {
        "prompt": "On-the-job training requirements",
        "data_set": "Training programs, onboarding period",
        "sources": "HR Reports, Company Website",
        "reply": "New hires undergo a 3-month technical training program to ensure knowledge transfer.",
        "tags": ["organization"],
    },
    {
        "prompt": "Facility footprint—location, purpose, rationale",
        "data_set": "Office locations, manufacturing sites, strategic rationale",
        "sources": "10-K, Investor Presentations",
        "reply": "Company X operates in 12 global locations, with HQ in San Francisco and R&D hubs in Berlin and Bangalore.",
        "tags": ["property"],
    },
    {
        "prompt": "Capacity utilization trends",
        "data_set": "% of capacity used vs. total available (3-5 years)",
        "sources": "Earnings Reports, Industry Reports",
        "reply": "Factory utilization is at 85%, with seasonal peaks reaching 95% in Q4.",
        "tags": ["property"],
    },
    {
        "prompt": "Own vs. lease facilities—any recent sale-and-leasebacks?",
        "data_set": "% of owned vs. leased properties, recent transactions",
        "sources": "10-K, SEC Filings, Real Estate Disclosures",
        "reply": "Company X owns 60% of its facilities, with a recent $200M sale-and-leaseback transaction to free up capital.",
        "tags": ["property"],
    },
    {
        "prompt": "Provide historical financial statements (annual & quarterly) for the last 3 years.",
        "data_set": "Revenue, EBITDA, Net Income, Cash Flow, Balance Sheet",
        "sources": "10-K, Earnings Reports, SEC Filings",
        "reply": "Revenue CAGR of 18% over the last 5 years, growing from $1B to $2.2B.",
        "tags": ["financials"],
    },
    {
        "prompt": "Price and volume trends (including GFC & COVID impact).",
        "data_set": "Stock price movements, trading volumes over macroeconomic cycles",
        "sources": "Bloomberg, Market Data Reports",
        "reply": "Stock price dropped 30% during COVID, recovered 50% post-2021.",
        "tags": ["financials"],
    },
    {
        "prompt": "Expense breakdown—fixed vs. variable costs.",
        "data_set": "Cost of goods sold (COGS), SG&A, R&D as % of revenue",
        "sources": "10-K, Investor Presentations",
        "reply": "Fixed costs account for 60% of total operating expenses, with R&D at 12% of revenue.",
        "tags": ["financials"],
    },
    {
        "prompt": "Key input costs as % of total expense.",
        "data_set": "Breakdown of raw material, labor, energy costs",
        "sources": "10-K, Cost Reports",
        "reply": "Raw materials represent 40% of COGS, labor 25%, and energy 10%.",
        "tags": ["financials"],
    },
    {
        "prompt": "Significant accounting policies (e.g., revenue recognition, deferred revenues).",
        "data_set": "Accounting methods, IFRS/GAAP compliance",
        "sources": "10-K, Financial Notes",
        "reply": "Revenue recognized over time for subscription contracts, with deferred revenue at $200M.",
        "tags": ["financials"],
    },
    {
        "prompt": "Working capital needs—DSO, DPO, inventory trends.",
        "data_set": "Days Sales Outstanding (DSO), Days Payable Outstanding (DPO), inventory turnover",
        "sources": "10-K, Analyst Reports",
        "reply": "DSO is 45 days, DPO is 60 days, inventory turnover is 4.2x annually.",
        "tags": ["financials"],
    },
    {
        "prompt": "Credit risk—receivables aging, % written off.",
        "data_set": "Aging schedule of receivables, bad debt expense",
        "sources": "10-K, Risk Disclosures",
        "reply": "Receivables past due 90+ days account for 5%, with 2% written off annually.",
        "tags": ["financials"],
    },
    {
        "prompt": "Leverage history—debt instruments trading levels.",
        "data_set": "Debt-to-equity ratio, bond ratings, interest coverage ratio",
        "sources": "10-K, Credit Rating Reports",
        "reply": "Company X has a D/E ratio of 0.8, with interest coverage of 6.5x.",
        "tags": ["financials"],
    },
    {
        "prompt": "FX exposure and hedging strategy.",
        "data_set": "Foreign exchange (FX) risk, hedge effectiveness",
        "sources": "10-K, Currency Risk Reports",
        "reply": "50% of revenue is in EUR, with hedging covering 80% of exposure.",
        "tags": ["financials"],
    },
    {
        "prompt": "Unfunded pension liabilities (esp. Europe).",
        "data_set": "Pension obligations vs. assets",
        "sources": "10-K, Annual Reports",
        "reply": "Company has $500M in pension liabilities, 80% funded, with a shortfall of $100M.",
        "tags": ["financials"],
    },
    {
        "prompt": "Acquisition history—timing, multiples, business mix changes.",
        "data_set": "Acquisition deals, revenue impact, EV/EBITDA multiples",
        "sources": "10-K, Press Releases, Deal Reports",
        "reply": "Acquired Company Y for $2.1B in 2022 at a 6x EV/EBITDA multiple, adding 15% to revenue.",
        "tags": ["m&a"],
    },
    {
        "prompt": "M&A strategy—branding, integration, financing.",
        "data_set": "Post-acquisition integration, financing structure",
        "sources": "10-K, CEO Interviews",
        "reply": "Integration completed within 12 months, financing split between cash & equity (60/40).",
        "tags": ["m&a"],
    },
    {
        "prompt": "Earn-outs—balances, tracking against targets.",
        "data_set": "Earn-out contingent liabilities, milestones achieved",
        "sources": "10-K, M&A Reports",
        "reply": "$100M earn-out contingent on 20% revenue growth, 75% achieved to date.",
        "tags": ["m&a"],
    },
    {
        "prompt": "Pending litigation, environmental, or reputational risks",
        "data_set": "Ongoing legal cases, regulatory penalties, PR issues",
        "sources": "10-K (Risk Factors), News Reports, SEC Filings",
        "reply": "Company X faces a $100M class-action lawsuit related to data privacy violations.",
        "tags": ["other"],
    },
    {
        "prompt": "Safety risks associated with the product",
        "data_set": "Recall history, regulatory fines, compliance breaches",
        "sources": "Consumer Safety Reports, Industry Regulations, 10-K",
        "reply": "Product Y was recalled due to safety concerns, costing the company $50M in settlements.",
        "tags": ["other"],
    },
    {
        "prompt": "Bankruptcy history",
        "data_set": "Previous financial distress, Chapter 11 filings",
        "sources": "SEC Filings, 10-K, News Reports",
        "reply": "Company X filed for Chapter 11 in 2018 but restructured under new ownership.",
        "tags": ["other"],
    },
    {
        "prompt": "Dataroom access availability",
        "data_set": "Extent of financial and operational disclosures for due diligence",
        "sources": "M&A Documents, NDA Agreements",
        "reply": "Dataroom includes audited financials, IP agreements, and supplier contracts.",
        "tags": ["other"],
    },
    {
        "prompt": "Employee and customer reviews",
        "data_set": "Glassdoor ratings, customer sentiment analysis, NPS scores",
        "sources": "Glassdoor, Google Reviews, Industry Surveys",
        "reply": "Company X has a 3.2/5 Glassdoor rating with frequent complaints about leadership turnover.",
        "tags": ["other"],
    },
    {
        "prompt": "Current ownership—equity split",
        "data_set": "Cap table, % ownership of key investors",
        "sources": "SEC Filings, 10-K, Investor Relations",
        "reply": "Founder retains 25% ownership, with PE firm Y holding a 40% stake.",
        "tags": ["transactions"],
    },
    {
        "prompt": "Reasons for sale—strategic, founder exit, etc.",
        "data_set": "Justifications for transaction",
        "sources": "Press Releases, Investor Calls, M&A Filings",
        "reply": "Company X is divesting its B2C division to focus on enterprise solutions.",
        "tags": ["transactions"],
    },
    {
        "prompt": "Post-sale seller ties—IP, facilities, SLAs",
        "data_set": "Retained assets, service obligations",
        "sources": "M&A Agreements, SEC Filings",
        "reply": "Company X retains key patents but grants buyer perpetual licensing rights.",
        "tags": ["transactions"],
    },
    {
        "prompt": "Buyer details—fund size, IRR, investment thesis",
        "data_set": "PE/VC fund size, expected return metrics",
        "sources": "PE Reports, Investor Filings, News Reports",
        "reply": "Buyer is a $10B PE fund targeting 20% IRR in tech investments.",
        "tags": ["transactions"],
    },
    {
        "prompt": "Exit strategy",
        "data_set": "Expected monetization plan",
        "sources": "IPO Filings, M&A Announcements",
        "reply": "Buyer plans to take Company X public within 5 years at a $5B valuation.",
        "tags": ["transactions"],
    },
    {
        "prompt": "Spin-out plans—tech stack continuity?",
        "data_set": "Retention of core IP, product roadmap",
        "sources": "M&A Agreements, Investor Calls",
        "reply": "Company X will continue using its proprietary AI models under a licensing deal with Buyer.",
        "tags": ["transactions"],
    },
]

if __name__ == "__main__":
    asyncio.run(migrate_weaviate())
