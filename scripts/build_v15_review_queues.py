from __future__ import annotations
import json,sqlite3,uuid
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate

NS=uuid.UUID("0ed450bf-1c9b-477f-9065-b6f44fe7563f")
def uid(s): return str(uuid.uuid5(NS,s))
def now(): return datetime.now(timezone.utc).isoformat()

def main():
    migrate(); con=sqlite3.connect(database_path()); con.row_factory=sqlite3.Row; ts=now()
    units=[dict(x) for x in con.execute("""select u.*,a.original_company_name,a.source_title,a.source_url,a.evidence_grade,a.quality_issues_json,
      a.normalized_primary_category,a.normalized_secondary_track,r.adjudication_type,r.handling_recommendation
      from v14_event_units u join v13_candidate_quality_audits a using(audit_id)
      left join v14_round_adjudications r using(audit_id)
      where u.sample_eligibility_status in ('A_statistical','B_pending') order by u.sample_eligibility_status,u.disclosure_date desc,u.adjudicated_company_name""")]
    with con:
        # Queue preparation is idempotent and never removes human decisions.
        counts={"A":0,"B":0}
        for u in units:
            q="A" if u["sample_eligibility_status"]=="A_statistical" else "B"; counts[q]+=1
            batch=(counts[q]-1)//20+1
            if q=="A": issue="ready_for_human_review"
            elif u["event_structure_status"]=="split_recommended": issue="multi_round_split"
            elif u.get("adjudication_type")=="E_media_conflict": issue="source_or_round_conflict"
            elif "名称" in (u.get("quality_issues_json") or ""): issue="company_name_question"
            elif u["event_structure_status"]=="conflict_pending": issue="round_conflict"
            else: issue="other_pending_issue"
            snapshot=json.dumps(u,ensure_ascii=False,sort_keys=True)
            con.execute("""insert or ignore into v15_funding_review_queue
              (review_item_id,event_unit_id,queue_class,batch_number,issue_group,original_snapshot_json,
               suggested_company_name,suggested_round,suggested_primary_category,suggested_secondary_track,
               suggested_investors,suggested_notes,review_status,last_reviewed_at,last_reviewed_by,created_at,updated_at)
              values (?,?,?,?,?,?,?,?,?,?,?,'','pending',NULL,NULL,?,?)""",(
              uid("review:"+u["event_unit_id"]),u["event_unit_id"],q,batch,issue,snapshot,u["adjudicated_company_name"],u["adjudicated_round"],u["normalized_primary_category"],u["normalized_secondary_track"],u["investors_original"],ts,ts))
        for a in con.execute("select * from v13_acquisition_verifications order by first_announcement_date desc"):
            snap=json.dumps(dict(a),ensure_ascii=False,sort_keys=True)
            con.execute("insert or ignore into v15_acquisition_review_queue values (?,?,?,NULL,'pending','',NULL,NULL,?,?)",(uid("ma:"+a["acquisition_key"]),a["acquisition_key"],snap,ts,ts))
    print(json.dumps({"A_queue":con.execute("select count(*) from v15_funding_review_queue where queue_class='A'").fetchone()[0],"B_queue":con.execute("select count(*) from v15_funding_review_queue where queue_class='B'").fetchone()[0],"MA_queue":con.execute("select count(*) from v15_acquisition_review_queue").fetchone()[0],"confirmed":con.execute("select count(*) from v15_confirmed_funding_events").fetchone()[0]},ensure_ascii=False)); con.close()
if __name__=="__main__": main()
