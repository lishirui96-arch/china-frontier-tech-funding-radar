from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedAmount:
    original: str
    exact: int | None
    minimum: int | None
    maximum: int | None
    currency: str
    disclosure_type: str
    cumulative: bool
    confidence: float
    rule: str


UNITS = {"元": 1, "万元": 10_000, "万": 10_000, "亿元": 100_000_000, "亿": 100_000_000}


def _currency(text: str) -> str:
    if re.search(r"美元|US\$|USD", text, re.I):
        return "USD"
    if re.search(r"欧元|EUR|€", text, re.I):
        return "EUR"
    if re.search(r"人民币|元|万|亿|CNY|RMB", text, re.I):
        return "CNY"
    return "UNKNOWN"


def parse_amount(text: str) -> ParsedAmount:
    raw = (text or "").strip()
    currency = _currency(raw)
    cumulative = bool(re.search(r"累计|总融资", raw))
    if not raw or re.search(r"未披露|未透露|不予披露", raw):
        return ParsedAmount(raw, None, None, None, currency, "undisclosed", False, 1.0, "undisclosed-v1")
    if cumulative:
        return ParsedAmount(raw, None, None, None, currency, "cumulative_only", True, 1.0, "cumulative-v1")

    normalized = raw.replace(",", "").replace("，", "")
    if re.search(r"近\s*亿元", normalized):
        return ParsedAmount(raw, None, 80_000_000, 99_999_999, currency, "upper_bound", False, 0.8, "near-v1")
    if re.search(r"(?:超|逾)\s*亿元", normalized):
        return ParsedAmount(raw, None, 100_000_000, None, currency, "lower_bound", False, 0.9, "lower-bound-v1")
    exact_match = re.search(r"(?<![约近超逾数])([0-9]+(?:\.[0-9]+)?)\s*(亿元|万元|亿|万|元|万美元|万欧元)", normalized)
    fuzzy = bool(re.search(r"约|近|超|逾|数|级|左右|以上|超过", normalized))
    if exact_match and not fuzzy:
        number = float(exact_match.group(1))
        unit_text = exact_match.group(2).replace("美元", "").replace("欧元", "")
        value = int(number * UNITS[unit_text])
        return ParsedAmount(raw, value, value, value, currency, "exact", False, 1.0, "exact-v1")

    base_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(亿元|万元|亿|万|元)", normalized)
    if base_match:
        value = int(float(base_match.group(1)) * UNITS[base_match.group(2)])
        if re.search(r"超|逾|以上|超过", normalized):
            return ParsedAmount(raw, None, value, None, currency, "lower_bound", False, 0.95, "lower-bound-v1")
        if "近" in normalized:
            return ParsedAmount(raw, None, int(value * 0.8), value - 1, currency, "upper_bound", False, 0.8, "near-v1")
        if "约" in normalized or "左右" in normalized:
            return ParsedAmount(raw, None, int(value * 0.9), int(value * 1.1), currency, "bounded_range", False, 0.75, "approx-v1")

    if re.search(r"数千万元", normalized):
        return ParsedAmount(raw, None, 20_000_000, 90_000_000, currency, "bounded_range", False, 0.75, "several-ten-million-v1")
    if re.search(r"数亿元", normalized):
        return ParsedAmount(raw, None, 200_000_000, 900_000_000, currency, "bounded_range", False, 0.75, "several-hundred-million-v1")
    if re.search(r"亿元级|完成亿元融资", normalized):
        return ParsedAmount(raw, None, 100_000_000, 999_999_999, currency, "order_of_magnitude", False, 0.7, "hundred-million-scale-v1")
    return ParsedAmount(raw, None, None, None, currency, "undisclosed", False, 0.4, "unparsed-v1")

