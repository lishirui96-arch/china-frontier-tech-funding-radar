from __future__ import annotations

import re

from funding_radar.amounts import parse_amount

ROUND_PATTERN = re.compile(r"(种子轮|天使轮|Pre[- ]?A轮|A\+?轮|B\+?轮|C\+?轮|D轮|战略融资|新一轮融资)", re.I)
AMOUNT_PATTERN = re.compile(r"((?:约|近|超|逾|数)?\s*(?:\d+(?:\.\d+)?|数)?\s*(?:万|亿)?(?:美元|欧元|元)(?:级|以上|左右)?)")


def extract_grounded_fields(text: str) -> list[dict]:
    value = text or ""
    results = []
    match = ROUND_PATTERN.search(value)
    if match:
        results.append({"field_group":"funding","field_name":"round_original","raw_value":match.group(0),"normalized_value":match.group(0),"span_start":match.start(),"span_end":match.end(),"confidence":0.95})
    for match in AMOUNT_PATTERN.finditer(value):
        raw = match.group(0).strip()
        if not raw:
            continue
        parsed = parse_amount(raw)
        results.append({"field_group":"funding","field_name":"amount_original","raw_value":raw,"normalized_value":parsed.disclosure_type,"span_start":match.start(),"span_end":match.end(),"confidence":parsed.confidence})
        break
    return results

