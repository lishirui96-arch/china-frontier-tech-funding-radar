from __future__ import annotations
import csv,json,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from funding_radar.db import database_path
from funding_radar.migrations import migrate

ROOT=Path(__file__).resolve().parents[1]; NS=uuid.UUID("bcff9799-50b3-4d7c-afcd-3188fc2a590c")
def uid(s): return str(uuid.uuid5(NS,s))
def now(): return datetime.now(timezone.utc).isoformat()
def platform(url):
    host=urlparse(url).netloc.lower()
    if "pedaily.cn" in host:return "投资界"
    if "36kr.com" in host:return "36氪"
    if "chinaventure.com.cn" in host:return "投中"
    if "qq.com" in host:return "腾讯新闻"
    if "cls.cn" in host:return "财联社"
    return host or "未知"

def main():
    migrate(); db=sqlite3.connect(database_path()); db.row_factory=sqlite3.Row; ts=now()
    with db:
        db.execute("""INSERT OR IGNORE INTO v151_research_policy VALUES (?,?,?,?,?,?,?,?,?,?,?)""",(
          uid("policy:V1.5.1"),"V1.5.1",ts,"2026-11-01","2026-11-25",json.dumps(["投资界","SpaceDaily"],ensure_ascii=False),
          "B级可访问媒体正文为基本入库标准；不要求官方公告覆盖", "媒体正文可明确识别的企业名称；仅排查截断、标题污染、主体误识别、重复简称、明显拼写及括号完整性",
          "投资界或SpaceDaily媒体正文可识别交易双方、比例、金额、披露日与报道状态；无交割证据不得标记完成",
          "保留历史范围外来源但不计入当前来源口径；不再考核多平台覆盖率和官方证据覆盖率",ts))
        queues=[dict(x) for x in db.execute("""SELECT q.review_item_id,q.queue_class,q.batch_number,u.disclosure_date,a.*,
          v12.source_platform FROM v15_funding_review_queue q JOIN v14_event_units u USING(event_unit_id)
          JOIN v13_candidate_quality_audits a USING(audit_id)
          LEFT JOIN v12_funding_candidates v12 ON a.candidate_version='V1.2' AND v12.candidate_id=a.source_candidate_id""")]
        for q in queues:
            url=q["source_url"]; ped="pedaily.cn" in urlparse(url).netloc.lower(); space=(q.get("source_platform") or "")=="SpaceDaily"
            status="in_scope_pedaily" if ped else ("in_scope_spacedaily" if space else "out_of_scope_pending")
            actual="SpaceDaily" if space else platform(url); date_ok="in_scope" if "2026-11-01"<=q["disclosure_date"]<="2026-11-25" else "out_of_scope"
            note="符合当前来源口径" if status!="out_of_scope_pending" else "保留历史记录；来源范围外，待处理；不得计入符合当前来源口径的正式样本"
            db.execute("INSERT OR REPLACE INTO v151_source_scope_checks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(uid("scope:"+q["review_item_id"]),q["review_item_id"],q["candidate_version"],actual,url,int(ped),int(space),status,q["disclosure_date"],date_ok,note,ts))
        # Import the already published batch-one evidence as a new recommendation snapshot; no queue fields are updated.
        path=ROOT/"docs"/"NOVEMBER_2026_V1_5_BATCH1_EVIDENCE_SUMMARY.csv"
        evidence={r["company"]:r for r in csv.DictReader(path.open(encoding="utf-8-sig"))}
        for q in queues:
            if q["queue_class"]!="A" or q["batch_number"]!=1:continue
            name_key=q["normalized_company_name"] if q["normalized_company_name"] in evidence else q["original_company_name"]
            if name_key not in evidence and name_key.startswith("无涯智远"): name_key="无涯智远（Norizon AI）"
            e=evidence[name_key]
            scope=db.execute("SELECT source_scope_status FROM v151_source_scope_checks WHERE review_item_id=?",(q["review_item_id"],)).fetchone()[0]
            name_rec=e["company"] if e["company"]!=q["original_company_name"] else "保持媒体正文名称"
            db.execute("INSERT OR REPLACE INTO v151_batch1_recommendations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
              uid("rec:"+q["review_item_id"]),q["review_item_id"],e["company"],q["original_amount"],e["amount"],q["original_round"],e["round"],q["disclosure_date"],e["date"],e["investors"],name_rec,scope,e["attention"],ts))
    print(json.dumps({"scope_checks":db.execute("select count(*) from v151_source_scope_checks").fetchone()[0],"in_pedaily":db.execute("select count(*) from v151_source_scope_checks where source_scope_status='in_scope_pedaily'").fetchone()[0],"in_spacedaily":db.execute("select count(*) from v151_source_scope_checks where source_scope_status='in_scope_spacedaily'").fetchone()[0],"out_scope":db.execute("select count(*) from v151_source_scope_checks where source_scope_status='out_of_scope_pending'").fetchone()[0],"batch1":db.execute("select count(*) from v151_batch1_recommendations").fetchone()[0]},ensure_ascii=False)); db.close()
if __name__=="__main__":main()
