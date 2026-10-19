# RevenueLeak AI — Agentic Settlement Reconciliation PoC

A local Streamlit proof of concept aligned with the CA-3 presentation. It uses transparent Python tools and synthetic data; it requires no paid APIs, Ollama, or internet connection at runtime.

## What it demonstrates
- **Planner Agent:** creates the investigation plan and checks required data groups.
- **Reconciliation Agent:** calculates expected settlement, matches settlement and bank records, detects missing/mismatched/possible duplicate entries.
- **Investigation Agent:** explains each issue from evidence and flags uncertainty.
- **Action Agent:** prioritises cases and recommends next steps for human approval.
- **Critic / Validation Agent:** independently checks settlement arithmetic, case uniqueness, evidence, and recommendations.
- **Orchestrator:** runs the agents in order, passes structured findings, and creates an audit trace.
- **Streamlit dashboard:** metrics, case inspection, evidence, recommendations, validation checks, and downloads.

## Run locally

Use Python 3.10 or later.

### macOS / Linux
```bash
cd RevenueLeak_AI_PoC
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Windows
```powershell
cd RevenueLeak_AI_PoC
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL, usually `http://localhost:8501`. Open it in your browser.

## Demo flow for the presentation
1. Select **Built-in demo data** in the sidebar.
2. Click **Load synthetic demo data**.
3. Inspect the four data tables if desired.
4. Click **Run RevenueLeak AI workflow**.
5. Show the dashboard metrics, then inspect the cases.
6. Open **Agent trace / audit trail** to demonstrate collaboration and decisions.
7. Open **Validation report** and download the CSV case report.

The synthetic examples include a settlement mismatch, a missing settlement, a missing bank deposit, and a possible duplicate deposit. Correct settlements with documented deductions should not create cases.

## Optional CSV uploads
Upload all four files: orders, settlement report, refunds, and bank transactions. Column schemas:

- `orders.csv`: `order_id, order_amount, commission, shipping_fee, other_fee, refund_amount, expected_settlement`
- `settlements.csv`: `order_id, settlement_amount, settlement_date`
- `refunds.csv`: `order_id, refund_amount, refund_status`
- `bank.csv`: `order_id, deposit_amount, deposit_date, bank_reference`

Amounts should be numeric and non-negative. In this PoC, deductions are represented as positive numbers and subtracted from order amount. One order can have multiple settlement or bank rows; the tool sums them. Use a consistent `order_id` across all files.

## Important interpretation notes
- The amount shown as **unexplained difference** is a triage estimate, not a confirmed loss or accounting conclusion.
- Timing differences, bundled deposits, marketplace-specific rules, and partial refunds may require more advanced matching than this demo implements.
- The demo flags duplicate-like bank rows but does not decide that the business has been paid twice.
- Validation checks are explicit. A failed arithmetic check is shown as a review flag, not hidden.
- Recommendations are drafts. The app does not contact a marketplace, update accounting records, or initiate a payment.

## Project structure
```text
RevenueLeak_AI_PoC/
├── app.py             # Streamlit UI
├── revenueleak.py     # Agent workflow, reconciliation tools, synthetic data
├── requirements.txt
└── README.md
```
