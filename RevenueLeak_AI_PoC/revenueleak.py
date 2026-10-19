from __future__ import annotations

import io
from typing import Any
import pandas as pd

REQUIRED_COLUMNS = {
    "orders": ["order_id", "order_amount", "commission", "shipping_fee", "other_fee", "refund_amount", "expected_settlement"],
    "settlements": ["order_id", "settlement_amount", "settlement_date"],
    "refunds": ["order_id", "refund_amount", "refund_status"],
    "bank": ["order_id", "deposit_amount", "deposit_date", "bank_reference"],
}
TOLERANCE = 0.01


def create_demo_data() -> dict[str, pd.DataFrame]:
    # Deliberately synthetic records designed to exercise several investigation paths.
    orders = pd.DataFrame([
        ["ORD-1001", 1000.00, 100.00, 30.00, 0.00, 0.00, 870.00],
        ["ORD-1002", 1500.00, 150.00, 40.00, 10.00, 0.00, 1300.00],
        ["ORD-1003", 2000.00, 200.00, 40.00, 0.00, 100.00, 1660.00],
        ["ORD-1004", 800.00, 80.00, 20.00, 0.00, 0.00, 700.00],
        ["ORD-1005", 1200.00, 120.00, 30.00, 0.00, 0.00, 1050.00],
        ["ORD-1006", 650.00, 65.00, 20.00, 0.00, 0.00, 565.00],
    ], columns=REQUIRED_COLUMNS["orders"])
    settlements = pd.DataFrame([
        ["ORD-1001", 870.00, "2026-10-15"],
        ["ORD-1002", 1280.00, "2026-10-15"],  # unexplained 20 short
        ["ORD-1003", 1660.00, "2026-10-16"],
        ["ORD-1004", 700.00, "2026-10-16"],
        ["ORD-1005", 1050.00, "2026-10-17"],
        # ORD-1006 deliberately missing settlement
    ], columns=REQUIRED_COLUMNS["settlements"])
    refunds = pd.DataFrame([
        ["ORD-1003", 100.00, "processed"],
        ["ORD-1002", 0.00, "none"],
        ["ORD-1001", 0.00, "none"],
        ["ORD-1004", 0.00, "none"],
        ["ORD-1005", 0.00, "none"],
        # ORD-1006 refund evidence is absent; the case is escalated as incomplete evidence
    ], columns=REQUIRED_COLUMNS["refunds"])
    bank = pd.DataFrame([
        ["ORD-1001", 870.00, "2026-10-16", "BNK-501"],
        ["ORD-1002", 1280.00, "2026-10-16", "BNK-502"],
        ["ORD-1003", 1660.00, "2026-10-17", "BNK-503"],
        ["ORD-1004", 700.00, "2026-10-17", "BNK-504"],
        ["ORD-1004", 700.00, "2026-10-17", "BNK-504-DUP"],  # duplicate deposit
        # ORD-1005 deposit is missing
    ], columns=REQUIRED_COLUMNS["bank"])
    return {"orders": orders, "settlements": settlements, "refunds": refunds, "bank": bank}


def validate_upload(data: dict[str, pd.DataFrame]) -> list[str]:
    errors = []
    for name, required in REQUIRED_COLUMNS.items():
        if name not in data:
            errors.append(f"Missing {name} file.")
            continue
        missing = [c for c in required if c not in data[name].columns]
        if missing:
            errors.append(f"{name}: missing columns {missing}.")
        if data[name].empty:
            errors.append(f"{name}: file contains no records.")
    if errors:
        return errors
    for name in ["orders", "settlements", "refunds", "bank"]:
        df = data[name]
        if df["order_id"].isna().any():
            errors.append(f"{name}: order_id contains blank values.")
    numeric_columns = {
        "orders": ["order_amount", "commission", "shipping_fee", "other_fee", "refund_amount", "expected_settlement"],
        "settlements": ["settlement_amount"],
        "refunds": ["refund_amount"],
        "bank": ["deposit_amount"],
    }
    for name, cols in numeric_columns.items():
        for col in cols:
            converted = pd.to_numeric(data[name][col], errors="coerce")
            if converted.isna().any():
                errors.append(f"{name}: {col} contains non-numeric or blank values.")
            if (converted.dropna() < 0).any():
                errors.append(f"{name}: {col} contains negative values; this PoC expects deductions as positive amounts.")
    return errors


def _sum_for(df: pd.DataFrame, order_id: str, column: str) -> float:
    rows = df.loc[df["order_id"].astype(str) == str(order_id), column]
    return float(pd.to_numeric(rows, errors="coerce").fillna(0).sum())


def _first_for(df: pd.DataFrame, order_id: str, column: str, default: Any = None) -> Any:
    rows = df.loc[df["order_id"].astype(str) == str(order_id), column]
    return rows.iloc[0] if len(rows) else default


def _has(df: pd.DataFrame, order_id: str) -> bool:
    return bool((df["order_id"].astype(str) == str(order_id)).any())


def run_agentic_workflow(data: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Transparent multi-agent workflow: specialist functions exchange structured findings."""
    orders, settlements, refunds, bank = (data[k].copy() for k in ["orders", "settlements", "refunds", "bank"])
    trace = []

    # Planner Agent: establishes scope and validates input before tool execution.
    plan = {
        "steps": ["validate schemas", "calculate expected settlements", "match settlement and bank records",
                  "investigate evidence", "prioritise follow-up", "independently validate findings"],
        "order_count": int(orders["order_id"].nunique()),
    }
    trace.append({"step": 1, "agent": "Planner Agent", "status": "complete",
                  "message": "Created an investigation plan and checked that all required record groups are present.",
                  "details": plan})

    # Reconciliation Agent: deterministic Python tool calculations and record matching.
    cases = []
    ids = orders["order_id"].astype(str).tolist()
    duplicate_bank_ids = set(bank.loc[bank.duplicated(["order_id", "deposit_amount", "deposit_date"], keep=False), "order_id"].astype(str))
    for idx, row in orders.iterrows():
        oid = str(row["order_id"])
        expected_formula = float(row["order_amount"]) - float(row["commission"]) - float(row["shipping_fee"]) - float(row["other_fee"]) - float(row["refund_amount"])
        stated_expected = float(row["expected_settlement"])
        has_settlement = _has(settlements, oid)
        has_refund = _has(refunds, oid)
        has_bank = _has(bank, oid)
        settlement_amt = _sum_for(settlements, oid, "settlement_amount") if has_settlement else 0.0
        bank_amt = _sum_for(bank, oid, "deposit_amount") if has_bank else 0.0
        evidence = []
        issue_types = []
        if abs(expected_formula - stated_expected) > TOLERANCE:
            issue_types.append("Expected settlement formula mismatch")
            evidence.append(f"Order arithmetic gives ₹{expected_formula:.2f}, but expected_settlement field says ₹{stated_expected:.2f}.")
        if not has_settlement:
            issue_types.append("Missing settlement record")
            evidence.append("No settlement row exists for this order.")
        elif abs(stated_expected - settlement_amt) > TOLERANCE:
            issue_types.append("Settlement amount mismatch")
            evidence.append(f"Expected ₹{stated_expected:.2f}; settlement report records ₹{settlement_amt:.2f}.")
        if not has_refund and float(row["refund_amount"]) > TOLERANCE:
            issue_types.append("Missing refund evidence")
            evidence.append(f"Order records a ₹{float(row['refund_amount']):.2f} refund deduction, but no refund record exists.")
        if not has_bank:
            issue_types.append("Missing bank deposit")
            evidence.append("No bank deposit row exists for this order.")
        elif has_settlement and abs(settlement_amt - bank_amt) > TOLERANCE:
            issue_types.append("Bank deposit mismatch")
            evidence.append(f"Settlement total is ₹{settlement_amt:.2f}; bank deposit total is ₹{bank_amt:.2f}.")
        if oid in duplicate_bank_ids:
            issue_types.append("Possible duplicate bank deposit")
            evidence.append("Multiple bank rows share the same order, amount and date; verify whether this is a duplicate posting.")
        # Legitimate deductions are not discrepancies if the arithmetic and records agree.
        if not issue_types:
            continue
        unexplained = round(max(abs(stated_expected - settlement_amt) if has_settlement else stated_expected,
                                abs(settlement_amt - bank_amt) if has_bank and has_settlement else (settlement_amt if has_settlement and not has_bank else 0.0)), 2)
        if not has_settlement:
            unexplained = round(max(unexplained, stated_expected), 2)
        cases.append({
            "case_id": f"CASE-{len(cases)+1:03d}", "order_id": oid,
            "issue_type": "; ".join(dict.fromkeys(issue_types)),
            "expected_settlement": round(stated_expected, 2),
            "formula_settlement": round(expected_formula, 2),
            "settlement_amount": round(settlement_amt, 2) if has_settlement else 0.0,
            "deposit_amount": round(bank_amt, 2) if has_bank else 0.0,
            "unexplained_difference": unexplained,
            "evidence": evidence, "has_settlement": has_settlement, "has_refund": has_refund,
            "has_bank": has_bank, "duplicate_bank": oid in duplicate_bank_ids,
        })
    trace.append({"step": 2, "agent": "Reconciliation Agent", "status": "complete",
                  "message": "Calculated expected settlement from order amount minus deductions, matched settlement and bank records, and flagged missing or duplicate rows.",
                  "details": {"orders_processed": len(orders), "candidate_cases": len(cases),
                              "tolerance_rupees": TOLERANCE}})

    # Investigation Agent: evidence-based explanation, with uncertainty called out explicitly.
    for case in cases:
        evidence_text = " ".join(case["evidence"]).lower()
        if not case["has_settlement"] or not case["has_refund"]:
            case["explanation"] = "Evidence is incomplete. The records are insufficient to determine the cause; obtain the missing settlement/refund report before concluding."
        elif case["duplicate_bank"]:
            case["explanation"] = "Potential duplicate bank posting detected. Confirm the bank reference and statement before treating the extra row as an actual duplicate payment."
        elif "settlement amount mismatch" in evidence_text:
            case["explanation"] = "The settlement report is lower or different from the expected amount. Compare fee, refund and adjustment details; the current input does not establish why the amount differs."
        elif "missing bank deposit" in evidence_text:
            case["explanation"] = "A settlement exists but no corresponding bank deposit row is present in the supplied data. This may be a timing difference or missing record; verify the bank statement and settlement date."
        else:
            case["explanation"] = "A record mismatch was found. Review source reports and transaction references before concluding that money is missing."
    trace.append({"step": 3, "agent": "Investigation Agent", "status": "complete",
                  "message": "Used transaction evidence to explain likely issue categories and explicitly preserved uncertainty where records are incomplete.",
                  "details": {"investigated_cases": len(cases)}})

    # Action Agent: recommends next steps and prioritises by potential amount and evidence risk.
    for case in cases:
        if not case["has_settlement"] or not case["has_refund"]:
            case["priority"] = "High"
            case["recommendation"] = "Request the missing settlement/refund evidence, keep the case open, and do not estimate a final loss until evidence is complete."
        elif case["duplicate_bank"]:
            case["priority"] = "High"
            case["recommendation"] = "Check both bank references against the actual bank statement; confirm or dismiss the suspected duplicate before any adjustment."
        elif case["unexplained_difference"] >= 100:
            case["priority"] = "High"
            case["recommendation"] = "Review the settlement and bank statement first; prepare an evidence-backed query for the marketplace if the mismatch remains unexplained."
        elif case["unexplained_difference"] >= 20:
            case["priority"] = "Medium"
            case["recommendation"] = "Review fee and adjustment lines, then draft a marketplace support query if no documented explanation is found."
        else:
            case["priority"] = "Low"
            case["recommendation"] = "Check source references and monitor for the next settlement cycle before escalating."
        case["case_status"] = "Needs human review"
    trace.append({"step": 4, "agent": "Action Agent", "status": "complete",
                  "message": "Ranked candidate cases and drafted follow-up actions. No message was sent and no financial action was taken.",
                  "details": {"human_approval_required": True}})

    # Critic/Validation Agent: independently recomputes core arithmetic and checks case evidence.
    validation_checks = []
    arithmetic_ok = all(abs((float(r["order_amount"]) - float(r["commission"]) - float(r["shipping_fee"]) -
                                  float(r["other_fee"]) - float(r["refund_amount"])) - float(r["expected_settlement"])) <= TOLERANCE
                        for _, r in orders.iterrows())
    validation_checks.append({"name": "Expected settlement arithmetic", "passed": arithmetic_ok,
                              "details": "Recomputed order amount minus commission, shipping, other fees and refunds."})
    unique_cases = len({c["order_id"] for c in cases}) == len(cases)
    validation_checks.append({"name": "One case per affected order", "passed": unique_cases,
                              "details": "Checked that each affected order has a single consolidated case."})
    evidence_present = all(isinstance(c["evidence"], list) and len(c["evidence"]) > 0 for c in cases)
    validation_checks.append({"name": "Evidence attached to every case", "passed": evidence_present,
                              "details": "Every reported case must include at least one observable evidence statement."})
    recommendations_present = all(bool(c.get("recommendation")) and bool(c.get("priority")) for c in cases)
    validation_checks.append({"name": "Recommendation and priority present", "passed": recommendations_present,
                              "details": "Every case has a priority and a proposed human follow-up."})
    for case in cases:
        case["validation_status"] = "Passed" if evidence_present and recommendations_present and unique_cases else "Needs review"
    overall = "Passed with review flags" if all(c["passed"] for c in validation_checks) else "Review required"
    trace.append({"step": 5, "agent": "Critic / Validation Agent", "status": overall,
                  "message": "Independently checked arithmetic, case uniqueness, evidence and recommendations. An arithmetic failure is surfaced rather than silently accepted.",
                  "details": {"checks": validation_checks}})
    trace.append({"step": 6, "agent": "Orchestrator", "status": "complete",
                  "message": "Aggregated validated findings for the dashboard. All candidate cases remain subject to human review.",
                  "details": {"published_cases": len(cases), "no_external_actions": True}})

    case_df = pd.DataFrame(cases)
    if case_df.empty:
        case_df = pd.DataFrame(columns=["case_id", "order_id", "issue_type", "expected_settlement",
            "settlement_amount", "deposit_amount", "unexplained_difference", "priority",
            "validation_status", "case_status", "explanation", "recommendation", "evidence"])
    summary = {
        "orders_analysed": int(orders["order_id"].nunique()),
        "cases_detected": len(cases),
        "validated_cases": sum(1 for c in cases if c.get("validation_status") == "Passed"),
        "net_unexplained_difference": round(sum(float(c["unexplained_difference"]) for c in cases), 2),
    }
    return {"cases": case_df, "summary": summary, "trace": trace,
            "validation": {"overall_status": overall, "checks": validation_checks}}


def build_case_report_csv(cases: pd.DataFrame) -> bytes:
    output = io.StringIO()
    export = cases.copy()
    if "evidence" in export.columns:
        export["evidence"] = export["evidence"].apply(lambda x: " | ".join(x) if isinstance(x, list) else str(x))
    export.to_csv(output, index=False)
    return output.getvalue().encode("utf-8")
