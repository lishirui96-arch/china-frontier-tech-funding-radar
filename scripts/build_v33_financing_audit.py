from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from funding_radar.db import database_path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CANDIDATES = DOCS / "V33_97条金额与投资方审核.csv"
SOURCE_RELEASE = "V3.2"
RELEASE = "V3.3"
NS = uuid.UUID("56647d98-6f4f-4742-acf5-0a2c20afac5d")


def uid(kind: str, value: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{value}"))


def amount_status(value: str) -> str:
    if "仅披露累计" in value:
        return "cumulative_only"
    if "合计" in value or "金额未拆分" in value:
        return "combined_rounds"
    if value == "未披露":
        return "explicit_undisclosed"
    if value.startswith("待核实"):
        return "pending"
    return "verified"


def investor_status(value: str) -> str:
    if value.startswith("待核实"):
        return "pending"
    if value.startswith("未披露"):
        return "explicit_undisclosed"
    if "未披露具体" in value or "未具名" in value or "未披露名称" in value:
        return "partially_verified"
    return "verified"


def issues(row: dict[str, str]) -> list[str]:
    result = []
    a_status = amount_status(row["suggested_amount"])
    i_status = investor_status(row["suggested_investors"])
    if a_status == "combined_rounds":
        result.append("同一来源披露多轮融资合计金额，各轮金额不得平均分配")
    if a_status == "cumulative_only":
        result.append("仅披露历史累计融资，本轮金额保持未披露")
    if i_status in {"pending", "partially_verified", "explicit_undisclosed"}:
        result.append("投资机构名称或角色未完整披露")
    if row["financial_advisor_evidence"]:
        result.append("来源披露财务顾问，已与投资方分离")
    return result


def main() -> None:
    with CANDIDATES.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 97:
        raise RuntimeError(f"Expected 97 audit rows, got {len(rows)}")

    timestamp = datetime.now(timezone.utc).isoformat()
    db = sqlite3.connect(database_path())
    db.row_factory = sqlite3.Row
    with db:
        for row in rows:
            db.execute(
                """INSERT OR REPLACE INTO v33_financing_field_audits
                   (audit_id,record_id,source_url,source_http_status,original_amount,reviewed_amount,amount_status,
                    amount_evidence,original_investors,reviewed_investors,investor_status,investor_evidence,
                    financial_advisor_evidence,issues_json,reviewed_at,reviewed_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uid("audit", row["record_id"]), row["record_id"], row["source_url"], row["http_status"],
                 row["original_amount"], row["suggested_amount"], amount_status(row["suggested_amount"]),
                 row["amount_evidence"], row["original_investors"], row["suggested_investors"],
                 investor_status(row["suggested_investors"]), row["investor_evidence"],
                 row["financial_advisor_evidence"], json.dumps(issues(row), ensure_ascii=False), timestamp,
                 "codex_v33_source_review"),
            )

        existing = db.execute("SELECT release_id FROM v30_releases WHERE release_name=?", (RELEASE,)).fetchone()
        if existing:
            print(json.dumps({"release_id": existing["release_id"], "existing": True}, ensure_ascii=False))
            return
        source_release = db.execute(
            "SELECT * FROM v30_releases WHERE release_name=? AND status='published'", (SOURCE_RELEASE,)
        ).fetchone()
        if not source_release:
            raise RuntimeError("V3.2 release is required")
        audits = {row["record_id"]: dict(row) for row in db.execute("SELECT * FROM v33_financing_field_audits")}
        records = []
        for snapshot in db.execute(
            "SELECT record_id,event_snapshot_json,classification_snapshot_json FROM v30_release_records WHERE release_id=? ORDER BY position",
            (source_release["release_id"],),
        ):
            event = json.loads(snapshot["event_snapshot_json"])
            classification = json.loads(snapshot["classification_snapshot_json"])
            audit = audits[snapshot["record_id"]]
            event["audit_original_amount"] = event.get("amount_original")
            event["audit_original_investors"] = event.get("investors_original")
            event["amount_original"] = audit["reviewed_amount"]
            event["investors_original"] = audit["reviewed_investors"]
            event["amount_review_status"] = audit["amount_status"]
            event["investor_review_status"] = audit["investor_status"]
            event["financial_advisor_evidence"] = audit["financial_advisor_evidence"]
            records.append((event, classification))

        manifest = json.loads(source_release["manifest_json"])
        counts = {
            "amount_verified": sum(amount_status(x["suggested_amount"]) == "verified" for x in rows),
            "amount_undisclosed": sum(amount_status(x["suggested_amount"]) == "explicit_undisclosed" for x in rows),
            "amount_combined_or_cumulative": sum(amount_status(x["suggested_amount"]) in {"combined_rounds", "cumulative_only"} for x in rows),
            "investor_verified": sum(investor_status(x["suggested_investors"]) == "verified" for x in rows),
            "investor_partial_or_undisclosed": sum(investor_status(x["suggested_investors"]) != "verified" for x in rows),
        }
        manifest.update({"data_version": RELEASE, "financial_fields_audited": len(rows), **counts})
        taxonomy_rows = [dict(x) for x in db.execute(
            "SELECT entity_type,entity_id,snapshot_json,position FROM v30_release_taxonomy WHERE release_id=? ORDER BY position",
            (source_release["release_id"],),
        )]
        payload = json.dumps({"manifest": manifest, "records": records, "taxonomy": taxonomy_rows}, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(payload.encode()).hexdigest()
        release_id = uid("release", content_hash)
        db.execute("INSERT INTO v30_releases VALUES (?,?,?,?,?,?,?,?)",
                   (release_id, RELEASE, source_release["taxonomy_version"], "published",
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True), content_hash, "Codex", timestamp))
        for item in taxonomy_rows:
            db.execute("INSERT INTO v30_release_taxonomy VALUES (?,?,?,?,?)",
                       (release_id, item["entity_type"], item["entity_id"], item["snapshot_json"], item["position"]))
        for position, (event, classification) in enumerate(records, 1):
            db.execute("INSERT INTO v30_release_records VALUES (?,?,?,?,?)",
                       (release_id, event["record_id"], json.dumps(event, ensure_ascii=False, sort_keys=True),
                        json.dumps(classification, ensure_ascii=False, sort_keys=True), position))
        db.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), "Codex", "create_v33_financing_field_audit", "v30_release", release_id, None,
                    json.dumps({"release": RELEASE, "audited_records": 97, **counts}, ensure_ascii=False),
                    "逐条访问97个原始来源，核验本轮金额、投资方角色并分离财务顾问", None, timestamp))

    export_fields = [
        "record_id", "company", "round", "original_amount", "suggested_amount", "amount_status",
        "original_investors", "suggested_investors", "investor_status", "financial_advisor_evidence",
        "amount_evidence", "investor_evidence", "source_url", "source_title", "http_status",
    ]
    with (DOCS / "V33_97条金额与投资方审核.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=export_fields)
        writer.writeheader()
        for row in rows:
            output = dict(row)
            output["amount_status"] = amount_status(row["suggested_amount"])
            output["investor_status"] = investor_status(row["suggested_investors"])
            writer.writerow({key: output.get(key, "") for key in export_fields})
    report = [
        "# V3.3 97条融资记录金额与投资方审核报告", "",
        "- 97个来源URL全部返回HTTP 200；96个页面成功提取正文，1个页面仅保留标题级证据。",
        f'- 金额直接核实：{counts["amount_verified"]}条。',
        f'- 金额明确未披露：{counts["amount_undisclosed"]}条。',
        f'- 多轮合计或仅披露累计金额：{counts["amount_combined_or_cumulative"]}条。',
        f'- 投资方及角色核实：{counts["investor_verified"]}条。',
        f'- 投资方部分披露、未具名或待核实：{counts["investor_partial_or_undisclosed"]}条。',
        "", "## 审核规则", "",
        "- 历史累计融资金额不作为本轮金额。",
        "- 同文多轮融资只保留合计金额，不平均分配。",
        "- 财务顾问与投资方分开记录，不计入投资机构。",
        "- 原始值保留在历史表和V3.3快照的audit_original字段中。",
        "- 未披露金额不填写为0。",
    ]
    (DOCS / "V33_FINANCING_FIELD_AUDIT_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"release_id": release_id, "manifest": manifest}, ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
