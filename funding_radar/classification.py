from __future__ import annotations

import re

CATEGORIES = {
    "merger_acquisition": ("收购", "并购", "控股权"),
    "ipo": ("IPO", "上市申请", "招股书"),
    "private_placement": ("定向增发", "定增"),
    "bond": ("债券", "可转债"),
    "bank_credit": ("授信", "贷款"),
    "government_subsidy": ("补贴", "专项资金"),
    "research_grant": ("科研项目", "基金资助", "课题资助"),
}
EQUITY_TERMS = ("完成融资", "获得投资", "新一轮融资", "天使轮", "Pre-A", "A轮", "B轮", "战略融资", "独家投资")


def classify_document(text: str) -> tuple[str, list[str]]:
    value = text or ""
    matches = []
    for category, terms in CATEGORIES.items():
        found = [term for term in terms if term.lower() in value.lower()]
        if found:
            matches.extend(found)
            return category, matches
    equity = [term for term in EQUITY_TERMS if term.lower() in value.lower()]
    if equity:
        return "primary_equity", equity
    if re.search(r"融资|投资", value, re.I):
        return "undetermined", []
    return "non_financing", []

