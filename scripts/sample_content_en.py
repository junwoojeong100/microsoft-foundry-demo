"""Sample content for the Contoso (fictional company) policy documents - English edition.

This is fictional demo data, not a real company or real policies. `build_sample_docs.py --lang en` turns it into
PDFs, and src/web/seed_en/evals/dataset.jsonl restates the same facts as questions and answers.
It mirrors scripts/sample_content.py (the Korean source): if you change a number, change both files and the datasets.
"""

COMPANY = "Contoso Ltd."

DOCS = [
    {
        "file": "HR-001_Employment_Rules_and_Leave_Policy.pdf",
        "id": "HR-001",
        "title": "Employment Rules and Leave Policy",
        "owner": "HR Team",
        "rev": "2026-03-01",
        "level": "Internal",
        "sections": [
            ("1. Purpose and Scope", [
                ("p", "This policy sets out the rules on working hours, leave, and leaves of absence for employees of Contoso Ltd. and its domestic affiliates. Where this policy differs from applicable law, the standard that is more favorable to the employee applies."),
            ]),
            ("2. Working Hours and Flexible Work", [
                ("ul", [
                    "Standard working hours are 40 hours per week (8 hours per day).",
                    "Employees on flexible work schedules must still be working during core hours (10:00–16:00).",
                    "Remote work is allowed up to 2 days per week; register it in the groupware 'Attendance' menu by the previous day. Separate approval from the Team Lead is not required.",
                    "Overtime, night work, and holiday work must be approved in advance; keeping monthly overtime within 12 hours is recommended.",
                ]),
            ]),
            ("3. Annual Leave", [
                ("p", "Employees with less than 1 year of service earn 1 day of annual leave for each month of full attendance (up to 11 days). Employees with 1 year or more of service receive 15 days of annual leave, and from 3 years of service onward, 1 additional day is added for every 2 years of continuous service, up to a maximum of 25 days."),
                ("table", ["Years of service", "Days of annual leave"], [
                    ["1 year or more, under 3 years", "15 days"],
                    ["3 years or more, under 5 years", "16 days"],
                    ["5 years or more, under 7 years", "17 days"],
                    ["7 years or more, under 9 years", "18 days"],
                    ["9 years or more, under 11 years", "19 days"],
                    ["11 years or more, under 13 years", "20 days"],
                    ["13 years or more, under 15 years", "21 days"],
                    ["15 years or more, under 17 years", "22 days"],
                    ["17 years or more, under 19 years", "23 days"],
                    ["19 years or more, under 21 years", "24 days"],
                    ["21 years or more", "25 days (maximum)"],
                ]),
                ("ul", [
                    "Annual leave can be used in full days, or split into half-day leave (4 hours) and quarter-day leave (2 hours).",
                    "Submit requests in the groupware 'Attendance' menu at least 1 business day before the planned date; the Team Lead approves them. In urgent cases, the leave can be registered after the fact by 10 a.m. on the day itself.",
                    "The company encourages employees to use their leave by notifying them of unused annual leave 6 months and 2 months before the end of the fiscal year. Annual leave that is still unused after this notice expires, and the statutory annual leave allowance is paid.",
                ]),
            ]),
            ("4. Special Leave", [
                ("table", ["Type", "Days", "Notes"], [
                    ["Own marriage", "5 days", "Paid; within 3 months before or after the wedding date"],
                    ["Child's marriage", "1 day", "Paid"],
                    ["Spouse's childbirth leave", "20 days", "Paid; may be split and used within 120 days of the birth date"],
                    ["Death of a parent, spouse, or child", "5 days", "Paid"],
                    ["Death of a grandparent or sibling", "3 days", "Paid"],
                    ["Own birthday", "1 half-day leave", "Use within the month of the birthday"],
                    ["Refresh leave", "5 days + KRW 1,000,000 support payment", "Once each at 5, 10, 15, and 20 years of service"],
                ]),
            ]),
            ("5. Parental Leave and Family Care", [
                ("ul", [
                    "Employees with a child aged 8 or younger (Grade 2 of elementary school or below) can take up to 1 year of parental leave.",
                    "For the first 3 months of parental leave, the company tops up pay to 100% of ordinary wages (capped at KRW 3,000,000 per month, including the government benefit).",
                    "Family care leave is 10 days per year (unpaid). Employees who need to care for a family member may also apply for reduced working hours, for up to 90 days per year.",
                ]),
            ]),
            ("6. Sick Leave", [
                ("p", "Sick leave may be taken for up to 30 days per year, of which 10 days are paid. A medical certificate must be submitted when sick leave lasts 3 or more consecutive days."),
            ]),
            ("7. Inquiries", [
                ("p", "Please contact the HR Team's HR Help Desk (ext. 3100, or the company messenger 'HR Team Inquiries')."),
            ]),
        ],
    },
    {
        "file": "FIN-002_Travel_and_Expense_Policy.pdf",
        "id": "FIN-002",
        "title": "Travel and Expense Policy",
        "owner": "Finance Team",
        "rev": "2026-03-01",
        "level": "Internal",
        "sections": [
            ("1. Basic Principles", [
                ("ul", [
                    "All expenses must be business-related and reported through 'Contoso Pay' with qualified supporting documents.",
                    "The corporate card is the default payment method. If you pay with a personal card, you must state the reason.",
                ]),
            ]),
            ("2. Meal Limits (per person, VAT included)", [
                ("table", ["Meal", "Limit per person", "Notes"], [
                    ["Breakfast", "KRW 10,000", ""],
                    ["Lunch", "KRW 15,000", ""],
                    ["Dinner", "KRW 30,000", "The same limit applies to team dinners (evening)"],
                ]),
                ("ul", [
                    "Team dinners are reimbursable up to 2 times per month. When submitting the expense report, you must enter the attendee list and the headcount.",
                    "The per-person amount is calculated as 'total amount paid ÷ number of attendees'. Any amount over the limit is borne by the individual.",
                ]),
                ("note", "Alcohol is generally not reimbursable. It is recognized only when an 'entertainment expense pre-approval request' has been approved for the purpose of entertaining customers. For team dinners without a pre-approval request, all alcohol costs are borne by the individual."),
            ]),
            ("3. Entertainment Expenses", [
                ("ul", [
                    "Customer entertainment is recognized up to KRW 50,000 per person per occasion. If the amount is expected to exceed this, a pre-approval request to the Division Head is required.",
                    "Entertainment expenses cannot be reimbursed without a pre-approval request. Record the customer's company, name, and the purpose of the entertainment.",
                ]),
            ]),
            ("4. Business Travel Expenses", [
                ("table", ["Item", "Domestic", "International"], [
                    ["Daily allowance", "KRW 50,000", "USD 80 (executives: USD 120)"],
                    ["Lodging cap (per night)", "Seoul KRW 150,000 / metropolitan cities KRW 120,000 / elsewhere KRW 100,000", "USD 250"],
                    ["Transportation", "Actual cost (KTX standard class; first class for executives)", "Actual cost (economy class; business class for executives)"],
                ]),
                ("p", "Taxis are recognized only for travel between 22:00 and 06:00 the next day, or when public transportation is difficult to use."),
            ]),
            ("5. Supporting Documents and Submission Deadline", [
                ("ul", [
                    "Expenses over KRW 30,000 require qualified supporting documents (corporate card sales slip, tax invoice, or cash receipt). Simplified receipts are accepted only for amounts of KRW 30,000 or less.",
                    "Submit the expense report within 7 days of the expense date. After the deadline, a late-submission explanation and the Team Lead's approval are required.",
                ]),
            ]),
            ("6. Approval Authority (by amount per transaction)", [
                ("table", ["Amount", "Approver"], [
                    ["KRW 300,000 or less", "Team Lead"],
                    ["Over KRW 300,000 up to KRW 1,000,000", "Division Head"],
                    ["Over KRW 1,000,000 up to KRW 3,000,000", "Executive in charge"],
                    ["Over KRW 3,000,000", "CEO"],
                ]),
            ]),
            ("7. Payment and Violations", [
                ("ul", [
                    "Once approved, payment is made to your payroll account within 3 business days.",
                    "Expense reports that violate this policy are rejected and must be rewritten. Repeated violations may result in disciplinary action.",
                ]),
            ]),
        ],
    },
    {
        "file": "SEC-003_Information_Security_and_Generative_AI_Guidelines.pdf",
        "id": "SEC-003",
        "title": "Information Security and Generative AI Guidelines",
        "owner": "Information Security Team",
        "rev": "2026-04-01",
        "level": "Internal",
        "sections": [
            ("1. Information Classification", [
                ("table", ["Classification", "Examples", "Handling rule"], [
                    ["Public", "Press releases, product catalogs", "No restrictions"],
                    ["Internal", "Company policies, general business documents", "Use only on the corporate network and in approved services"],
                    ["Confidential", "Unreleased business plans, costs, customer contract terms", "Share only with those who need to know; prior approval required"],
                    ["Top secret", "M&A, core source code, performance review results", "In principle, may not be entered into AI services"],
                ]),
            ]),
            ("2. Principles for Using Generative AI", [
                ("ul", [
                    "For work, use only 'Contoso AI' (built on Microsoft Azure), the company-approved service.",
                    "Entering work materials into publicly available external generative AI services is prohibited (including through personal accounts).",
                    "Public and Internal materials may be entered into the portal. Confidential materials may be used only with prior approval from the Information Security Team and only within the knowledge sources designated in the portal.",
                    "Top secret materials may not be entered.",
                ]),
                ("note", "Customer personal information must not be entered: this includes resident registration numbers (RRNs), phone numbers, addresses, and any other identifiable data. Unreleased financial information, performance reviews, and core source code are also prohibited. If it is absolutely necessary, mask or de-identify names and contact details before use."),
            ]),
            ("3. Verifying Outputs", [
                ("ul", [
                    "A person must always verify AI answers. When sources are provided, check the original text.",
                    "Do not rely on an AI answer as the sole basis for a final decision on legal, financial, or HR matters.",
                ]),
            ]),
            ("4. Incident Response", [
                ("p", "If personal or confidential information has been leaked, or a leak is suspected, report it to the Information Security Team (ext. 7777) within 1 hour and submit an incident report within 24 hours."),
            ]),
            ("5. Accounts and Access Control", [
                ("ul", [
                    "All business systems require Microsoft Entra ID sign-in (SSO) and multi-factor authentication (MFA).",
                    "Passwords must be at least 12 characters long and changed every 90 days.",
                    "AI portal query logs are retained for 1 year, with personal information masked before storage.",
                ]),
            ]),
            ("6. Transfer Outside the Company", [
                ("p", "Sending documents classified Confidential or above outside the company requires DLP approval. USB storage devices may not be used."),
            ]),
        ],
    },
    {
        "file": "CS-004_Product_and_After-Sales_Service_Guide.pdf",
        "id": "CS-004",
        "title": "Product and After-Sales Service Guide",
        "owner": "Customer Service Team",
        "rev": "2026-02-15",
        "level": "Public",
        "sections": [
            ("1. Main Products", [
                ("table", ["Product", "Key specifications", "Warranty"], [
                    ["Contoso AirPure AP-500 (Air Purifier)", "50 m² coverage area, HEPA H13 filter, 24 dB sleep mode", "Main unit 1 year, BLDC motor 3 years"],
                    ["Contoso SmartCook SC-30 (Air Fryer)", "6.5 L capacity, app recipe integration", "Main unit 1 year, coating 1 year"],
                    ["Contoso RoboClean R7 (Robot Vacuum)", "5,200 mAh battery, 130 minutes of continuous runtime", "Main unit 2 years, battery 1 year"],
                ]),
            ]),
            ("2. AirPure AP-500 Filter Care", [
                ("ul", [
                    "Wash the pre-filter with water every 6 months.",
                    "Replace the HEPA (H13) filter and the deodorizing filter every 12 months. When replacement is due, the indicator light on the unit turns orange.",
                    "After replacing a filter, reset the indicator light by tapping 'Reset filter' in the app or by holding the filter button on the unit for 3 seconds.",
                ]),
            ]),
            ("3. RoboClean R7 Battery", [
                ("p", "If the battery capacity drops below 70% of its capacity at the time of purchase, the battery is replaced free of charge within the warranty period (1 year). Symptoms such as the unit not charging, or shutting off within 5 minutes after charging, qualify for a battery inspection."),
            ]),
            ("4. Service Requests and Fees", [
                ("ul", [
                    "To request service, call the Customer Service Center (1588-0000, an example number) or use the 'Contoso Care' app or the website.",
                    "On-site repairs are carried out on weekdays from 09:00 to 18:00. Within the warranty period, the service-call fee and parts are free of charge.",
                    "After the warranty period, a visit fee of KRW 20,000 plus the cost of parts is charged.",
                ]),
            ]),
            ("5. Exchanges and Refunds", [
                ("ul", [
                    "Within 7 days of purchase, a refund is available for a simple change of mind, but only if the product is unused and unopened.",
                    "Defective products are exchanged for a new one or refunded within 30 days of purchase.",
                    "Cases are handled in accordance with the Consumer Dispute Resolution Standards, and you will be notified of the result within 3 business days of the request date.",
                ]),
            ]),
        ],
    },
    {
        "file": "LEG-005_Contract_Review_Checklist.pdf",
        "id": "LEG-005",
        "title": "Contract Review Checklist",
        "owner": "Legal Team",
        "rev": "2026-01-15",
        "level": "Internal",
        "sections": [
            ("1. Review and Approval Criteria", [
                ("table", ["Contract value", "Required procedure"], [
                    ["Under KRW 50 million", "Department head approval (Legal Team review is optional)"],
                    ["KRW 50 million or more, under KRW 500 million", "Legal Team review required"],
                    ["KRW 500 million or more", "Legal Team review + CFO approval"],
                ]),
            ]),
            ("2. Required Clauses to Check", [
                ("table", ["Item", "Contoso standard"], [
                    ["Payment", "Within 60 days after acceptance (for subcontracting transactions, comply with the statutory deadline)"],
                    ["Liquidated damages", "0.1% of the contract amount per day of delay, capped at 10% of the contract amount"],
                    ["Defect repair", "12 months after acceptance; the defect repair bond is 5% of the contract amount"],
                    ["Damages", "Capped at 100% of the contract amount (excluding willful misconduct and gross negligence)"],
                    ["Intellectual property", "As a rule, deliverables belong to Contoso"],
                    ["Confidentiality", "Remains in force for 3 years after the contract ends"],
                    ["Personal data", "If processing is outsourced, a separate outsourcing agreement and a security review of the processor are required"],
                    ["Governing law and jurisdiction", "Laws of the Republic of Korea; Seoul Central District Court"],
                ]),
            ]),
            ("3. Clauses Requiring Caution", [
                ("ul", [
                    "Clauses allowing unilateral unit-price reductions, or providing for unlimited damages",
                    "Foreign governing-law or foreign arbitration clauses",
                    "Automatic renewal clauses: register the termination notice deadline (60 days in advance) in your calendar.",
                    "Clauses that allow re-subcontracting without restriction",
                ]),
            ]),
        ],
    },
    {
        "file": "HR-006_New_Hire_Onboarding_Guide.pdf",
        "id": "HR-006",
        "title": "New Hire Onboarding Guide",
        "owner": "HR Team",
        "rev": "2026-02-01",
        "level": "Internal",
        "sections": [
            ("1. Your First Week", [
                ("ul", [
                    "Your groupware, VPN, and Contoso AI accounts are created automatically 3 business days before your start date.",
                    "On your first morning you attend the HR Team orientation; in the afternoon you are introduced to your team and meet your mentor (buddy).",
                    "The probation period is 3 months, and your Team Lead meets with you in weeks 4 and 12.",
                ]),
            ]),
            ("2. Required Training (within 30 days of joining)", [
                ("table", ["Training", "Duration"], [
                    ["Information security training (including the generative AI usage guidelines)", "2 hours"],
                    ["Workplace harassment prevention training", "1 hour"],
                    ["Occupational health and safety training", "2 hours"],
                ]),
            ]),
            ("3. Corporate Card and Expenses", [
                ("ul", [
                    "Assistant Managers and above are issued a corporate card as soon as they join. Associates receive theirs within 3 business days after Team Lead approval.",
                    "Submit expense reports in 'Contoso Pay'. See FIN-002 for the policy.",
                ]),
            ]),
            ("4. Frequently Used Company Systems", [
                ("table", ["System", "Purpose"], [
                    ["Groupware", "Email, approvals, attendance (leave requests)"],
                    ["Contoso Pay", "Expense reimbursement, corporate card statements"],
                    ["Contoso AI", "Company knowledge Q&A, document drafting, data analysis"],
                    ["IT Service Desk", "Account, equipment, and software requests"],
                ]),
            ]),
        ],
    },
    {
        "file": "IT-007_IT_Service_Desk_FAQ.pdf",
        "id": "IT-007",
        "title": "IT Service Desk FAQ",
        "owner": "IT Operations Team",
        "rev": "2026-03-10",
        "level": "Internal",
        "sections": [
            ("1. Accounts and Authentication", [
                ("ul", [
                    "You can reset your password yourself on the self-service portal (password.contoso.example).",
                    "If you lose your MFA device, contact the Service Desk (ext. 7000) immediately to remove your existing authentication method and register a new device.",
                ]),
            ]),
            ("2. Remote Work", [
                ("ul", [
                    "When working from home, use business systems only while connected to the company VPN (Always-on VPN).",
                    "Do not store work materials on a personal PC.",
                ]),
            ]),
            ("3. Equipment and Software", [
                ("ul", [
                    "Laptops are replaced on a 4-year cycle.",
                    "Request software installation through the 'SW Request' menu in the IT portal; after a security review, requests are processed within 3 business days.",
                    "Unapproved software (such as personal cloud-sync apps or external AI extensions) may not be installed.",
                ]),
            ]),
            ("4. Security Incidents", [
                ("p", "If you suspect malware, disconnect the network cable or Wi-Fi and report it to the Information Security Team (ext. 7777) immediately."),
            ]),
        ],
    },
    {
        "file": "PUR-008_Purchasing_and_Supplier_Evaluation_Policy.pdf",
        "id": "PUR-008",
        "title": "Purchasing and Supplier Evaluation Policy",
        "owner": "Procurement Team",
        "rev": "2026-02-20",
        "level": "Internal",
        "sections": [
            ("1. Purchasing Methods", [
                ("table", ["Purchase amount", "Method"], [
                    ["Under KRW 5 million", "Single-source contract allowed"],
                    ["KRW 5 million or more, under KRW 50 million", "Comparison of quotes from 3 vendors"],
                    ["KRW 50 million or more", "Electronic competitive bidding"],
                ]),
                ("p", "Urgent purchases may be handled as an exception; report them to the Procurement Team after the fact within 5 business days."),
            ]),
            ("2. Supplier Registration", [
                ("p", "Submit a business registration certificate, your most recent financial statements, and an ESG self-assessment form, and pass the Procurement Team's review."),
            ]),
            ("3. Supplier Evaluation", [
                ("table", ["Criterion", "Points"], [
                    ["Quality", "40 points"],
                    ["On-time delivery", "25 points"],
                    ["Price", "20 points"],
                    ["Safety & ESG", "15 points"],
                ]),
                ("table", ["Grade", "Score"], [
                    ["S", "90 points or more"],
                    ["A", "80–89 points"],
                    ["B", "70–79 points"],
                    ["C", "Under 70 points"],
                ]),
                ("p", "Suppliers that receive a C grade 2 times in a row are considered for suspension of business dealings."),
            ]),
            ("4. Payment", [
                ("p", "Supplier payments are made within 60 days after the monthly closing, in compliance with the Subcontracting Act."),
            ]),
        ],
    },
]
