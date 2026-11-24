from __future__ import annotations

from pathlib import Path

from funding_radar.classification import classify_document
from funding_radar.db import connect
from funding_radar.extraction import extract_grounded_fields
from funding_radar.repository import LedgerRepository, now, uid


def screen_document(document_id: str, actor: str, reason: str, category: str | None = None, path: Path | None = None) -> dict:
    repo = LedgerRepository(path)
    document = repo.rows("SELECT * FROM raw_documents WHERE document_id=?", (document_id,))[0]
    suggested, signals = classify_document(f"{document['title']}\n{document.get('text_or_summary') or ''}")
    chosen = category or suggested
    repo.execute("UPDATE raw_documents SET financing_category=?, relevance_status=?, review_status=? WHERE document_id=?", (chosen,"relevant" if chosen=="primary_equity" else "uncertain","parsed",document_id))
    repo.audit(actor,"screen_document","raw_document",document_id,{"financing_category":document["financing_category"]},{"financing_category":chosen,"signals":signals},reason)
    return {"category":chosen,"suggested":suggested,"signals":signals}


def extract_document(document_id: str, path: Path | None = None) -> int:
    repo = LedgerRepository(path)
    document = repo.rows("SELECT * FROM raw_documents WHERE document_id=?", (document_id,))[0]
    text = document.get("text_or_summary") or ""
    candidates = extract_grounded_fields(text)
    connection = connect(path)
    try:
        with connection:
            for item in candidates:
                connection.execute("INSERT INTO extraction_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (uid(),document_id,item["field_group"],item["field_name"],item["raw_value"],item["normalized_value"],item["span_start"],item["span_end"],item["confidence"],"rules-v1","pending",now()))
    finally:
        connection.close()
    return len(candidates)

