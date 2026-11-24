from __future__ import annotations

import json
from datetime import date
from difflib import SequenceMatcher


def _date_score(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.3
    days = abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    return 1.0 if days <= 7 else 0.7 if days <= 30 else 0.3 if days <= 45 else 0.0


def compare_events(left: dict, right: dict) -> dict:
    same_company = left["company_id"] == right["company_id"]
    company_score = 1.0 if same_company else 0.0
    round_score = 0.4 if not left.get("round_normalized") or not right.get("round_normalized") else float(left["round_normalized"] == right["round_normalized"])
    date_score = _date_score(left.get("announcement_date"), right.get("announcement_date"))
    left_min, left_max = left.get("amount_min"), left.get("amount_max")
    right_min, right_max = right.get("amount_min"), right.get("amount_max")
    amount_score = 0.4
    if left_min is not None and right_min is not None:
        lmax = left_max if left_max is not None else 10**30
        rmax = right_max if right_max is not None else 10**30
        amount_score = 1.0 if max(left_min, right_min) <= min(lmax, rmax) else 0.0
    text_score = SequenceMatcher(None, left.get("use_of_funds_original") or "", right.get("use_of_funds_original") or "").ratio()
    conflicts = []
    if not same_company:
        conflicts.append("different_company")
    if round_score == 0 and left.get("round_normalized") and right.get("round_normalized"):
        conflicts.append("different_explicit_round")
    total = 0.35*company_score + 0.2*date_score + 0.15*round_score + 0.15*amount_score + 0.15*text_score
    risk = "high" if same_company and total >= 0.75 and not conflicts else "medium" if same_company and total >= 0.5 else "low"
    return {"company_score": company_score, "date_score": date_score, "round_score": round_score, "amount_score": amount_score, "investor_score": 0.0, "text_score": text_score, "citation_score": 0.0, "strong_conflicts_json": json.dumps(conflicts), "feature_details_json": json.dumps({"same_company": same_company}, sort_keys=True), "total_score": total, "risk_level": risk}

