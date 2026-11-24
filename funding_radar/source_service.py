from __future__ import annotations

import json
from pathlib import Path

from funding_radar.db import connect
from funding_radar.repository import LedgerRepository, now, uid


def create_source(data: dict, actor: str, reason: str, path: Path | None = None) -> str:
    source_id = uid()
    connection = connect(path)
    try:
        with connection:
            connection.execute("""INSERT INTO sources(source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at,is_active,allowed_scope,min_interval_seconds,failure_count)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""", (source_id,data["name"],data["source_type"],data["source_family"],data["grade"],data.get("base_url"),data.get("terms_status","review_required"),now(),1,data.get("allowed_scope","metadata_only"),int(data.get("min_interval_seconds",3600))))
    finally:
        connection.close()
    LedgerRepository(path).audit(actor,"create_source","source",source_id,None,data,reason)
    return source_id


def update_source(source_id: str, changes: dict, actor: str, reason: str, path: Path | None = None) -> None:
    allowed = {"name","source_type","source_family","evidence_default_grade","base_url","terms_status","is_active","allowed_scope","min_interval_seconds"}
    if not changes or not set(changes).issubset(allowed):
        raise ValueError("Unsupported source fields")
    repo = LedgerRepository(path)
    before = repo.rows("SELECT * FROM sources WHERE source_id=?", (source_id,))[0]
    sql = ",".join(f"{key}=?" for key in changes)
    repo.execute(f"UPDATE sources SET {sql} WHERE source_id=?", tuple(changes.values())+(source_id,))
    repo.audit(actor,"update_source","source",source_id,before,{**before,**changes},reason)

