from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from funding_radar.db import connect
from funding_radar.repository import LedgerRepository, now, uid


class SampleLibraryService:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.repo = LedgerRepository(path)

    def categories(self) -> list[dict[str, Any]]:
        return self.repo.rows("SELECT * FROM industry_categories WHERE is_active=1 ORDER BY sort_order")

    def v231_admission_reviews(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT r.*,t.candidate_name,t.technical_boundary,
            f.name AS field_name,i.name AS industry_name
          FROM v231_topic_admission_reviews r
          JOIN v22_topics t ON t.topic_id=r.source_topic_id
          JOIN v22_fields f ON f.field_id=t.field_id
          JOIN v22_industries i ON i.industry_id=f.industry_id
          ORDER BY i.sort_order,f.sort_order,t.candidate_name""")

    def v231_member_quality(self, topic_id: str = "") -> list[dict[str, Any]]:
        where = "WHERE q.source_topic_id=?" if topic_id else ""
        params = (topic_id,) if topic_id else ()
        return self.repo.rows(f"""SELECT q.*,t.candidate_name,c.display_name,
            p.primary_business,l.product_basis,l.technology_basis,l.evidence_basis,
            p.evidence_urls_json
          FROM v231_member_quality q
          JOIN v22_topics t ON t.topic_id=q.source_topic_id
          JOIN v22_companies c USING(company_id)
          JOIN v22_company_profiles p USING(company_id)
          JOIN v22_company_topic_links l ON l.topic_id=q.source_topic_id AND l.company_id=q.company_id
          {where} ORDER BY t.candidate_name,c.display_name""", params)

    def v231_entity_reviews(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT r.*,l.display_name AS left_name,
            rr.display_name AS right_name FROM v231_entity_reviews r
          JOIN v22_companies l ON l.company_id=r.left_company_id
          JOIN v22_companies rr ON rr.company_id=r.right_company_id
          ORDER BY l.display_name,rr.display_name""")

    def v231_cross_topic_reviews(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT r.*,c.display_name,t.candidate_name
          FROM v231_cross_topic_reviews r JOIN v22_companies c USING(company_id)
          JOIN v22_topics t ON t.topic_id=r.source_topic_id
          ORDER BY c.display_name,t.candidate_name""")

    def source_coverage(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT r.source_name,r.source_column,COUNT(DISTINCT p.page_id) AS pages_traversed,
            SUM(p.article_count) AS articles_seen,
            SUM(CASE WHEN p.http_status=200 THEN 0 ELSE 1 END) AS inaccessible_pages,
            MIN(p.oldest_date) AS oldest_date,MAX(p.newest_date) AS newest_date
          FROM source_audit_runs r LEFT JOIN source_audit_pages p USING(run_id)
          GROUP BY r.run_id ORDER BY r.source_name,r.source_column""")

    def v11_candidates(self, status: str = "") -> list[dict[str, Any]]:
        where = "WHERE c.candidate_status=?" if status else ""
        params = (status,) if status else ()
        return self.repo.rows(f"""SELECT c.*,d.title,d.original_url,a.source_column,a.original_access_status
          FROM v11_funding_candidates c JOIN raw_documents d ON d.document_id=c.source_document_id
          LEFT JOIN source_document_audit a USING(document_id) {where}
          ORDER BY c.disclosure_date DESC,c.company_name_original""", params)

    def v11_summary(self) -> dict[str, Any]:
        rows = self.repo.rows("SELECT candidate_status,COUNT(*) AS n FROM v11_funding_candidates GROUP BY candidate_status")
        result = {row["candidate_status"]: row["n"] for row in rows}
        result["pedaily_documents"] = self.repo.rows("SELECT COUNT(*) AS n FROM source_document_audit WHERE discovery_channel='投资界公开分页'")[0]["n"]
        result["spacedaily_records"] = self.repo.rows("SELECT COUNT(*) AS n FROM source_event_observations WHERE source_name='SpaceDaily融资数据库'")[0]["n"]
        return result

    def v12_platform_audits(self) -> list[dict[str, Any]]:
        return self.repo.rows("SELECT * FROM v12_platform_audits ORDER BY platform")

    def v12_candidates(self, platform: str = "", status: str = "") -> list[dict[str, Any]]:
        clauses = ["1=1"]; params: list[Any] = []
        if platform:
            clauses.append("source_platform=?"); params.append(platform)
        if status:
            clauses.append("candidate_status=?"); params.append(status)
        return self.repo.rows(f"SELECT * FROM v12_funding_candidates WHERE {' AND '.join(clauses)} ORDER BY disclosure_date DESC,source_platform,company_name_original",tuple(params))

    def v12_summary(self) -> dict[str, Any]:
        return self.repo.rows("""SELECT COUNT(*) AS candidate_observations,
            SUM(candidate_status='new') AS new_candidates,
            SUM(candidate_status='duplicate_v1_v11') AS duplicates,
            SUM(verification_status='verified') AS verified,
            SUM(verification_status='partially_verified') AS partially_verified,
            SUM(verification_status='pending') AS pending
          FROM v12_funding_candidates""")[0]

    def v13_summary(self) -> dict[str, Any]:
        summary = self.repo.rows("""SELECT COUNT(*) AS candidates,
            SUM(name_quality_status='accurate') AS accurate_names,
            SUM(name_quality_status='corrected') AS corrected_names,
            SUM(name_quality_status IN ('suspected_error','pending')) AS unresolved_names,
            SUM(overall_verification_status='complete') AS complete,
            SUM(overall_verification_status='partial') AS partial,
            SUM(overall_verification_status='pending') AS pending,
            SUM(overall_verification_status='conflict') AS conflicts
          FROM v13_candidate_quality_audits""")[0]
        summary["companies"] = self.repo.rows("SELECT COUNT(*) AS n FROM v13_company_entities")[0]["n"]
        summary["confirmed_duplicates"] = self.repo.rows(
            "SELECT COUNT(*) AS n FROM v13_candidate_relations WHERE relation_type='confirmed_duplicate'"
        )[0]["n"]
        return summary

    def v13_candidate_audits(self, status: str = "") -> list[dict[str, Any]]:
        where = "WHERE overall_verification_status=?" if status else ""
        params = (status,) if status else ()
        return self.repo.rows(f"""SELECT * FROM v13_candidate_quality_audits {where}
          ORDER BY normalized_disclosure_date DESC,normalized_company_name""", params)

    def v13_field_verifications(self, field_name: str = "", status: str = "") -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if field_name:
            clauses.append("v.field_name=?"); params.append(field_name)
        if status:
            clauses.append("v.verification_status=?"); params.append(status)
        return self.repo.rows(f"""SELECT a.normalized_company_name,a.normalized_disclosure_date,
            a.normalized_round,v.* FROM v13_field_verifications v
          JOIN v13_candidate_quality_audits a USING(audit_id)
          WHERE {' AND '.join(clauses)} ORDER BY a.normalized_company_name,v.field_name""", tuple(params))

    def v13_relations(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT r.*,l.normalized_company_name AS left_company,
            l.normalized_round AS left_round,x.normalized_company_name AS right_company,
            x.normalized_round AS right_round
          FROM v13_candidate_relations r
          JOIN v13_candidate_quality_audits l ON l.audit_id=r.left_audit_id
          JOIN v13_candidate_quality_audits x ON x.audit_id=r.right_audit_id
          ORDER BY r.relation_type,l.normalized_company_name""")

    def v13_acquisition_verifications(self) -> list[dict[str, Any]]:
        return self.repo.rows("SELECT * FROM v13_acquisition_verifications ORDER BY first_announcement_date DESC,buyer_name")

    def v14_review_queue(self, eligibility: str = "") -> list[dict[str, Any]]:
        where = "WHERE u.sample_eligibility_status=?" if eligibility else ""
        params = (eligibility,) if eligibility else ()
        return self.repo.rows(f"""SELECT u.*,a.original_company_name,a.source_title,a.source_url,a.evidence_grade,
            a.original_round,a.quality_issues_json,r.adjudication_type,r.handling_recommendation,
            GROUP_CONCAT(DISTINCT rel.relation_type) AS duplicate_relations
          FROM v14_event_units u JOIN v13_candidate_quality_audits a USING(audit_id)
          LEFT JOIN v14_round_adjudications r USING(audit_id)
          LEFT JOIN v13_candidate_relations rel ON rel.left_audit_id=a.audit_id OR rel.right_audit_id=a.audit_id
          {where} GROUP BY u.event_unit_id ORDER BY
          CASE u.sample_eligibility_status WHEN 'B_pending' THEN 1 WHEN 'C_excluded' THEN 2 ELSE 3 END,
          u.disclosure_date DESC,u.adjudicated_company_name""", params)

    def v14_summary(self) -> dict[str, Any]:
        rows=self.repo.rows("SELECT sample_eligibility_status,COUNT(*) n FROM v14_event_units WHERE is_current=1 GROUP BY sample_eligibility_status")
        result={r["sample_eligibility_status"]:r["n"] for r in rows}
        result["split_recommended"]=self.repo.rows("SELECT COUNT(*) n FROM v14_event_units WHERE event_structure_status='split_recommended'")[0]["n"]
        result["merge_sources"]=self.repo.rows("SELECT COUNT(*) n FROM v14_duplicate_decisions WHERE final_decision='merge_sources'")[0]["n"]
        return result

    def review_v14_event(self, event_unit_id: str, *, action: str, actor: str, reason: str, value: str = "") -> None:
        allowed={"confirm_company","rename_company","confirm_round","split_event","merge_duplicate","mark_statistical","hold","exclude"}
        if action not in allowed: raise ValueError("Unsupported V1.4 action")
        if not actor.strip() or not reason.strip(): raise ValueError("Actor and reason are required")
        connection=connect(self.path)
        try:
            with connection:
                row=connection.execute("SELECT * FROM v14_event_units WHERE event_unit_id=? AND is_current=1",(event_unit_id,)).fetchone()
                if not row: raise ValueError("Unknown current event unit")
                before=dict(row)
                updates={}
                if action=="rename_company":
                    if not value.strip(): raise ValueError("Normalized company name is required")
                    updates["adjudicated_company_name"]=value.strip()
                elif action=="confirm_round":
                    if not value.strip(): raise ValueError("Round is required")
                    updates["adjudicated_round"]=value.strip()
                elif action=="mark_statistical": updates.update(sample_eligibility_status="A_statistical",eligibility_reason=reason)
                elif action=="hold": updates.update(sample_eligibility_status="B_pending",eligibility_reason=reason)
                elif action=="exclude": updates.update(sample_eligibility_status="C_excluded",eligibility_reason=reason)
                elif action=="split_event": updates["event_structure_status"]="split_recommended"
                elif action=="merge_duplicate": updates["event_structure_status"]="duplicate_source"
                updates.update(decision_status="human_modified",updated_at=now())
                clause=",".join(f"{k}=?" for k in updates)
                connection.execute(f"UPDATE v14_event_units SET {clause} WHERE event_unit_id=?",(*updates.values(),event_unit_id))
                after=dict(connection.execute("SELECT * FROM v14_event_units WHERE event_unit_id=?",(event_unit_id,)).fetchone())
                action_id=uid()
                connection.execute("INSERT INTO v14_review_actions VALUES (?,?,?,?,?,?,?,?)",(action_id,event_unit_id,action,actor,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,now()))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor,"v14_"+action,"v14_event_unit",event_unit_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,now()))
        finally: connection.close()

    def v15_funding_queue(self, queue_class: str, batch: int = 0, issue_group: str = "") -> list[dict[str, Any]]:
        clauses=["q.queue_class=?"]; params: list[Any]=[queue_class]
        if batch: clauses.append("q.batch_number=?"); params.append(batch)
        if issue_group: clauses.append("q.issue_group=?"); params.append(issue_group)
        return self.repo.rows(f"""SELECT q.*,u.company_id,u.disclosure_date,u.amount_original,
            a.original_company_name,a.source_title,a.source_url,a.evidence_grade,a.quality_issues_json,
            e.primary_business,e.core_products,e.primary_category,e.secondary_track,
            GROUP_CONCAT(DISTINCT fv.field_name||':'||fv.verification_status) AS field_verifications,
            GROUP_CONCAT(DISTINCT CASE WHEN a2.audit_id<>a.audit_id THEN a2.source_url END) AS cross_sources
          FROM v15_funding_review_queue q JOIN v14_event_units u USING(event_unit_id)
          JOIN v13_candidate_quality_audits a USING(audit_id) JOIN v13_company_entities e USING(company_id)
          LEFT JOIN v13_field_verifications fv USING(audit_id)
          LEFT JOIN v13_candidate_relations rel ON rel.left_audit_id=a.audit_id OR rel.right_audit_id=a.audit_id
          LEFT JOIN v13_candidate_quality_audits a2 ON a2.audit_id=CASE WHEN rel.left_audit_id=a.audit_id THEN rel.right_audit_id ELSE rel.left_audit_id END
          WHERE {' AND '.join(clauses)} GROUP BY q.review_item_id ORDER BY q.batch_number,u.disclosure_date DESC,e.short_name""",tuple(params))

    def review_v15_funding(self, review_item_id: str, *, decision: str, actor: str, reason: str,
                           company_name: str, round_name: str, primary_category: str,
                           secondary_track: str, investors: str, notes: str) -> None:
        if decision not in {"confirm","hold","exclude","edit"}: raise ValueError("Unsupported review decision")
        if not actor.strip() or not reason.strip(): raise ValueError("审核人和审核依据不能为空")
        if decision=="confirm" and (not company_name.strip() or not round_name.strip()): raise ValueError("确认纳入前必须确认企业名称和融资轮次")
        connection=connect(self.path)
        try:
            with connection:
                row=connection.execute("""SELECT q.*,u.company_id,u.disclosure_date,u.amount_original
                  FROM v15_funding_review_queue q JOIN v14_event_units u USING(event_unit_id)
                  WHERE q.review_item_id=?""",(review_item_id,)).fetchone()
                if not row: raise ValueError("Unknown review item")
                before=dict(row); status={"confirm":"confirmed","hold":"held","exclude":"excluded","edit":row["review_status"]}[decision]; timestamp=now()
                connection.execute("""UPDATE v15_funding_review_queue SET suggested_company_name=?,suggested_round=?,
                  suggested_primary_category=?,suggested_secondary_track=?,suggested_investors=?,suggested_notes=?,
                  review_status=?,last_reviewed_at=?,last_reviewed_by=?,updated_at=? WHERE review_item_id=?""",
                  (company_name.strip(),round_name.strip(),primary_category.strip(),secondary_track.strip(),investors.strip(),notes.strip(),status,timestamp,actor.strip(),timestamp,review_item_id))
                after=dict(connection.execute("SELECT * FROM v15_funding_review_queue WHERE review_item_id=?",(review_item_id,)).fetchone())
                connection.execute("INSERT INTO v15_funding_review_actions VALUES (?,?,?,?,?,?,?,?)",(uid(),review_item_id,decision,actor,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,timestamp))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor,"v15_funding_"+decision,"v15_funding_review",review_item_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,timestamp))
                if decision=="confirm":
                    confirmed_id="v15-"+review_item_id
                    connection.execute("""INSERT OR REPLACE INTO v15_confirmed_funding_events
                      VALUES (?,?,?,?,?,?,?,?,NULL,NULL,?,?,?,?,?,?,1)""",(confirmed_id,review_item_id,row["company_id"],company_name.strip(),row["disclosure_date"],before["suggested_round"],round_name.strip(),row["amount_original"],investors.strip(),primary_category.strip(),secondary_track.strip(),notes.strip(),actor.strip(),timestamp))
                    entity=connection.execute("SELECT * FROM v13_company_entities WHERE company_id=?",(row["company_id"],)).fetchone()
                    connection.execute("""INSERT OR REPLACE INTO v15_technology_analysis VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      ("tech-"+confirmed_id,confirmed_id,row["company_id"],company_name.strip(),entity["primary_business"],entity["core_products"],"待人工补充","待人工补充","待人工补充","待人工补充",primary_category.strip(),secondary_track.strip(),entity["evidence_urls_json"],secondary_track.strip(),"pending",timestamp,timestamp))
                elif decision in {"hold","exclude"}:
                    connection.execute("UPDATE v15_confirmed_funding_events SET is_active=0 WHERE review_item_id=?",(review_item_id,))
        finally: connection.close()

    def v15_review_summary(self) -> dict[str, Any]:
        result={r["review_status"]:r["n"] for r in self.repo.rows("SELECT review_status,COUNT(*) n FROM v15_funding_review_queue GROUP BY review_status")}
        result["confirmed_events"]=self.repo.rows("SELECT COUNT(*) n FROM v15_confirmed_funding_events WHERE is_active=1")[0]["n"]
        return result

    def v15_confirmed_statistics(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT round_confirmed,primary_category,secondary_track,amount_currency,
          COUNT(*) event_count,COUNT(DISTINCT company_id) company_count,
          SUM(CASE WHEN amount_cny IS NOT NULL THEN amount_cny END) disclosed_amount_cny,
          SUM(CASE WHEN amount_original IN ('未披露','') THEN 1 ELSE 0 END) undisclosed_amount_count
          FROM v15_confirmed_funding_events WHERE is_active=1
          GROUP BY round_confirmed,primary_category,secondary_track,amount_currency ORDER BY event_count DESC""")

    def v15_acquisition_queue(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT q.*,v.* FROM v15_acquisition_review_queue q
          JOIN v13_acquisition_verifications v USING(acquisition_key) ORDER BY v.first_announcement_date DESC""")

    def review_v15_acquisition(self, review_item_id: str, *, decision: str, transaction_status: str, actor: str, reason: str, notes: str) -> None:
        if decision not in {"confirm_status","hold","exclude","edit"}: raise ValueError("Unsupported acquisition decision")
        if not actor.strip() or not reason.strip(): raise ValueError("审核人和审核依据不能为空")
        connection=connect(self.path)
        try:
            with connection:
                row=connection.execute("SELECT * FROM v15_acquisition_review_queue WHERE review_item_id=?",(review_item_id,)).fetchone()
                if not row: raise ValueError("Unknown acquisition review item")
                before=dict(row); status={"confirm_status":"confirmed","hold":"held","exclude":"excluded","edit":row["review_status"]}[decision]; timestamp=now()
                connection.execute("""UPDATE v15_acquisition_review_queue SET confirmed_transaction_status=?,review_status=?,human_notes=?,
                  last_reviewed_at=?,last_reviewed_by=?,updated_at=? WHERE review_item_id=?""",(transaction_status,status,notes,timestamp,actor,timestamp,review_item_id))
                after=dict(connection.execute("SELECT * FROM v15_acquisition_review_queue WHERE review_item_id=?",(review_item_id,)).fetchone())
                connection.execute("INSERT INTO v15_acquisition_review_actions VALUES (?,?,?,?,?,?,?,?)",(uid(),review_item_id,decision,actor,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,timestamp))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor,"v15_acquisition_"+decision,"v15_acquisition_review",review_item_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,timestamp))
        finally: connection.close()

    def v15_technology_analysis(self) -> list[dict[str, Any]]:
        return self.repo.rows("SELECT * FROM v15_technology_analysis ORDER BY primary_category,secondary_track,company_name")

    def v15_actions(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT 'funding' action_scope,action_id,review_item_id,decision,actor,reason,occurred_at
          FROM v15_funding_review_actions UNION ALL
          SELECT 'acquisition',action_id,review_item_id,decision,actor,reason,occurred_at
          FROM v15_acquisition_review_actions ORDER BY occurred_at DESC""")

    def v151_progress(self) -> dict[str, Any]:
        result={}
        result["pedaily_candidates"]=self.repo.rows("SELECT COUNT(*) n FROM v151_source_scope_checks WHERE source_scope_status='in_scope_pedaily'")[0]["n"]
        result["spacedaily_candidates"]=self.repo.rows("SELECT COUNT(*) n FROM v151_source_scope_checks WHERE source_scope_status='in_scope_spacedaily'")[0]["n"]
        result["out_of_scope_sources"]=self.repo.rows("SELECT COUNT(*) n FROM v151_source_scope_checks WHERE source_scope_status='out_of_scope_pending'")[0]["n"]
        result["date_in_scope"]=self.repo.rows("SELECT COUNT(*) n FROM v151_source_scope_checks WHERE date_scope_status='in_scope'")[0]["n"]
        result["name_checked"]=self.repo.rows("SELECT COUNT(*) n FROM v13_candidate_quality_audits WHERE name_quality_status IN ('accurate','corrected')")[0]["n"]
        result.update(self.v15_review_summary())
        result["a_total"]=self.repo.rows("SELECT COUNT(*) n FROM v15_funding_review_queue WHERE queue_class='A'")[0]["n"]
        result["a_reviewed"]=self.repo.rows("SELECT COUNT(*) n FROM v15_funding_review_queue WHERE queue_class='A' AND review_status<>'pending'")[0]["n"]
        result["b_total"]=self.repo.rows("SELECT COUNT(*) n FROM v15_funding_review_queue WHERE queue_class='B'")[0]["n"]
        result["b_resolved"]=self.repo.rows("SELECT COUNT(*) n FROM v15_funding_review_queue WHERE queue_class='B' AND review_status<>'pending'")[0]["n"]
        result["acquisitions"]=self.repo.rows("SELECT COUNT(*) n FROM v15_acquisition_review_queue")[0]["n"]
        result["technology_classified"]=self.repo.rows("SELECT COUNT(*) n FROM v15_technology_analysis")[0]["n"]
        return result

    def v2_theme_summary(self) -> dict[str, Any]:
        return self.repo.rows("""SELECT
          (SELECT COUNT(*) FROM v2_company_profiles) profile_count,
          (SELECT COUNT(DISTINCT company_name) FROM v2_company_profiles) company_count,
          (SELECT COUNT(*) FROM v2_industry_directions) industry_count,
          (SELECT COUNT(*) FROM v2_technology_fields) field_count,
          (SELECT COUNT(*) FROM v2_candidate_topics) topic_count,
          (SELECT COUNT(*) FROM v2_candidate_topics WHERE topic_kind='single_company_observation') observation_count,
          (SELECT COUNT(*) FROM v2_company_profiles WHERE profile_status='pending_supplement') unclassified_count,
          (SELECT COUNT(DISTINCT event_ref) FROM v2_event_topic_links WHERE event_source_type='formal') formal_events,
          (SELECT COUNT(DISTINCT event_ref) FROM v2_event_topic_links WHERE event_source_type='A_candidate') a_events,
          (SELECT COUNT(DISTINCT event_ref) FROM v2_event_topic_links WHERE event_source_type='B_candidate') b_events""")[0]

    def v2_topics(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT t.*,i.name industry_name,f.name field_name,
          COUNT(DISTINCT l.profile_id) company_count,COUNT(DISTINCT e.event_ref) event_count,
          COUNT(DISTINCT CASE WHEN e.event_source_type='formal' THEN e.event_ref END) formal_count,
          COUNT(DISTINCT CASE WHEN e.event_source_type='A_candidate' THEN e.event_ref END) a_count,
          COUNT(DISTINCT CASE WHEN e.event_source_type='B_candidate' THEN e.event_ref END) b_count,
          GROUP_CONCAT(DISTINCT p.company_name) companies,GROUP_CONCAT(DISTINCT e.round_original) rounds
          FROM v2_candidate_topics t JOIN v2_industry_directions i USING(industry_id)
          JOIN v2_technology_fields f USING(field_id)
          LEFT JOIN v2_company_topic_links l ON l.topic_id=t.topic_id AND l.is_current=1
          LEFT JOIN v2_company_profiles p USING(profile_id) LEFT JOIN v2_event_topic_links e USING(topic_id)
          GROUP BY t.topic_id ORDER BY company_count DESC,event_count DESC,t.candidate_name""")

    def v2_profiles(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT p.*,i.name industry_name,f.name field_name,
          GROUP_CONCAT(DISTINCT t.candidate_name) topics
          FROM v2_company_profiles p JOIN v2_industry_directions i USING(industry_id)
          JOIN v2_technology_fields f USING(field_id)
          LEFT JOIN v2_company_topic_links l ON l.profile_id=p.profile_id AND l.is_current=1
          LEFT JOIN v2_candidate_topics t USING(topic_id) GROUP BY p.profile_id
          ORDER BY i.sort_order,p.company_name""")

    def v2_events(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT e.*,GROUP_CONCAT(DISTINCT t.candidate_name) topics
          FROM v2_event_topic_links e JOIN v2_candidate_topics t USING(topic_id)
          GROUP BY e.event_source_type,e.event_ref ORDER BY e.disclosure_date DESC,e.company_name""")

    def v21_topic_audits(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT a.*,t.candidate_name,i.name industry_name,f.name field_name,
          COUNT(DISTINCT l.profile_id) company_count,COUNT(DISTINCT e.event_ref) event_count,
          COUNT(DISTINCT CASE WHEN e.event_source_type='formal' THEN e.event_ref END) formal_count,
          COUNT(DISTINCT CASE WHEN e.event_source_type='A_candidate' THEN e.event_ref END) a_count,
          COUNT(DISTINCT CASE WHEN e.event_source_type='B_candidate' THEN e.event_ref END) b_count,
          GROUP_CONCAT(DISTINCT p.company_name) companies
          FROM v21_topic_audits a JOIN v2_candidate_topics t USING(topic_id)
          JOIN v2_industry_directions i USING(industry_id) JOIN v2_technology_fields f USING(field_id)
          LEFT JOIN v2_company_topic_links l ON l.topic_id=t.topic_id AND l.is_current=1
          LEFT JOIN v2_company_profiles p USING(profile_id) LEFT JOIN v2_event_topic_links e USING(topic_id)
          GROUP BY a.audit_id ORDER BY i.sort_order,t.candidate_name""")

    def v21_overlap_matrix(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT o.*,l.candidate_name left_name,r.candidate_name right_name
          FROM v21_topic_overlaps o JOIN v2_candidate_topics l ON l.topic_id=o.left_topic_id
          JOIN v2_candidate_topics r ON r.topic_id=o.right_topic_id
          ORDER BY shared_company_count DESC,jaccard DESC,left_name,right_name""")

    def v21_taxonomy(self) -> list[dict[str, Any]]:
        return self.repo.rows("SELECT * FROM v21_taxonomy_proposals ORDER BY level,proposal_type,current_name")

    def v21_profile_triage(self, group: str = "") -> list[dict[str, Any]]:
        clause={"pending":"WHERE x.was_pending=1","other":"WHERE x.was_other=1"}.get(group,"")
        return self.repo.rows(f"""SELECT x.*,p.company_name,p.primary_business,p.core_products,p.core_technologies,
          p.application_scenarios,p.value_chain_position,p.profile_status,i.name current_industry,f.name current_field
          FROM v21_profile_triage x JOIN v2_company_profiles p USING(profile_id)
          JOIN v2_industry_directions i USING(industry_id) JOIN v2_technology_fields f USING(field_id)
          {clause} ORDER BY p.company_name""")

    def review_v2_topic(self, topic_id: str, *, action: str, actor: str, reason: str,
                        value: str = "", target_topic_id: str = "", profile_id: str = "") -> None:
        allowed={"confirm","rename","hold","exclude","restore","change_industry","merge","move_company","split_company","add_tag"}
        if action not in allowed: raise ValueError("Unsupported V2 topic action")
        if not actor.strip() or not reason.strip(): raise ValueError("审核人和审核理由不能为空")
        connection=connect(self.path); timestamp=now()
        try:
            with connection:
                row=connection.execute("SELECT * FROM v2_candidate_topics WHERE topic_id=?",(topic_id,)).fetchone()
                if not row: raise ValueError("Unknown topic")
                before=dict(row)
                if action=="confirm": connection.execute("UPDATE v2_candidate_topics SET review_status='confirmed',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="hold": connection.execute("UPDATE v2_candidate_topics SET review_status='held',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="exclude": connection.execute("UPDATE v2_candidate_topics SET review_status='excluded',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="restore": connection.execute("UPDATE v2_candidate_topics SET review_status='pending',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="rename":
                    if not value.strip(): raise ValueError("主题名称不能为空")
                    connection.execute("UPDATE v2_candidate_topics SET final_name=?,final_name_locked=1,updated_at=? WHERE topic_id=?",(value.strip(),timestamp,topic_id))
                elif action=="change_industry":
                    field=connection.execute("SELECT field_id,industry_id FROM v2_technology_fields WHERE field_id=?",(value,)).fetchone()
                    if not field: raise ValueError("请选择有效技术领域")
                    connection.execute("UPDATE v2_candidate_topics SET industry_id=?,field_id=?,updated_at=? WHERE topic_id=?",(field["industry_id"],field["field_id"],timestamp,topic_id))
                elif action in {"move_company","split_company"}:
                    if not profile_id or not target_topic_id: raise ValueError("请选择企业和目标主题")
                    connection.execute("UPDATE v2_company_topic_links SET is_current=0 WHERE topic_id=? AND profile_id=?",(topic_id,profile_id))
                    connection.execute("INSERT OR REPLACE INTO v2_company_topic_links VALUES (?,?,?,?,?)",(target_topic_id,profile_id,reason,1,timestamp))
                elif action=="merge":
                    if not target_topic_id: raise ValueError("请选择合并目标")
                    for member in connection.execute("SELECT * FROM v2_company_topic_links WHERE topic_id=? AND is_current=1",(topic_id,)).fetchall():
                        connection.execute("INSERT OR IGNORE INTO v2_company_topic_links VALUES (?,?,?,?,?)",(target_topic_id,member["profile_id"],reason,1,timestamp))
                    connection.execute("UPDATE v2_candidate_topics SET review_status='merged',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="add_tag":
                    if not profile_id or not value.strip(): raise ValueError("请选择企业并输入标签")
                    profile=connection.execute("SELECT keywords_json FROM v2_company_profiles WHERE profile_id=?",(profile_id,)).fetchone(); tags=json.loads(profile[0] or "[]")
                    if value.strip() not in tags: tags.append(value.strip())
                    connection.execute("UPDATE v2_company_profiles SET keywords_json=?,updated_at=? WHERE profile_id=?",(json.dumps(tags,ensure_ascii=False),timestamp,profile_id))
                after=dict(connection.execute("SELECT * FROM v2_candidate_topics WHERE topic_id=?",(topic_id,)).fetchone())
                connection.execute("INSERT INTO v2_topic_actions VALUES (?,?,?,?,?,?,?,?)",(uid(),topic_id,action,actor.strip(),json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,timestamp))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor.strip(),"v2_topic_"+action,"v2_candidate_topic",topic_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,timestamp))
        finally: connection.close()

    def v211_profile_reviews(self, quality: str = "") -> list[dict[str, Any]]:
        where="WHERE r.quality_status=?" if quality else "";params=(quality,) if quality else ()
        return self.repo.rows(f"""SELECT r.*,p.source_entity_type,p.source_entity_id FROM v211_profile_reviews r
          JOIN v2_company_profiles p USING(profile_id) {where} ORDER BY r.quality_status,r.suggested_name""",params)

    def v211_duplicate_checks(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT d.*,l.company_name left_name,r.company_name right_name
          FROM v211_entity_duplicate_checks d JOIN v2_company_profiles l ON l.profile_id=d.left_profile_id
          JOIN v2_company_profiles r ON r.profile_id=d.right_profile_id ORDER BY left_name,right_name""")

    def v211_shared_reviews(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT s.*,p.company_name FROM v211_shared_company_reviews s
          JOIN v2_company_profiles p USING(profile_id) ORDER BY s.topic_count DESC,p.company_name""")

    def v211_split_proposals(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT s.*,t.candidate_name source_topic,GROUP_CONCAT(p.company_name) companies
          FROM v211_split_proposals s JOIN v2_candidate_topics t ON t.topic_id=s.source_topic_id
          LEFT JOIN v211_split_members m USING(proposal_id) LEFT JOIN v2_company_profiles p USING(profile_id)
          GROUP BY s.proposal_id ORDER BY source_topic,s.subtopic_name""")

    def review_v211_profile(self, review_id: str, *, action: str, actor: str, reason: str,
                            business: str, products: str, technologies: str, scenarios: str, chain: str) -> None:
        if action not in {"confirm","modify","hold"}: raise ValueError("不支持的画像审核动作")
        if not actor.strip() or not reason.strip(): raise ValueError("审核人和审核理由不能为空")
        connection=connect(self.path);timestamp=now()
        try:
            with connection:
                row=connection.execute("SELECT * FROM v211_profile_reviews WHERE review_id=?",(review_id,)).fetchone()
                if not row: raise ValueError("未知画像审核记录")
                before=dict(row);status={"confirm":"confirmed","modify":"modified","hold":"held"}[action]
                connection.execute("""UPDATE v211_profile_reviews SET suggested_business=?,suggested_products=?,suggested_technologies=?,
                  suggested_scenarios=?,suggested_chain=?,review_status=? WHERE review_id=?""",
                  (business.strip() or "待补充",products.strip() or "待补充",technologies.strip() or "待补充",scenarios.strip() or "待补充",chain.strip() or "待补充",status,review_id))
                after=dict(connection.execute("SELECT * FROM v211_profile_reviews WHERE review_id=?",(review_id,)).fetchone())
                connection.execute("INSERT INTO v211_profile_actions VALUES (?,?,?,?,?,?,?,?)",(uid(),review_id,action,actor.strip(),json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,timestamp))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor.strip(),"v211_profile_"+action,"v211_profile_review",review_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,timestamp))
        finally: connection.close()

    def v22_taxonomy_tree(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT i.code,i.name industry_name,f.name field_name,t.*,
          COUNT(DISTINCT l.company_id) company_count,COUNT(DISTINCT et.event_id) event_count,
          COUNT(DISTINCT CASE WHEN e.data_status='formal' THEN e.event_id END) formal_count,
          COUNT(DISTINCT CASE WHEN e.data_status='A_candidate' THEN e.event_id END) a_count,
          COUNT(DISTINCT CASE WHEN e.data_status='B_candidate' THEN e.event_id END) b_count,
          GROUP_CONCAT(DISTINCT c.display_name) companies,GROUP_CONCAT(DISTINCT g.tag) tags
          FROM v22_topics t JOIN v22_fields f USING(field_id) JOIN v22_industries i USING(industry_id)
          LEFT JOIN v22_company_topic_links l USING(topic_id) LEFT JOIN v22_companies c USING(company_id)
          LEFT JOIN v22_company_tags g USING(company_id) LEFT JOIN v22_event_topics et USING(topic_id)
          LEFT JOIN v22_events e USING(event_id) GROUP BY t.topic_id ORDER BY i.sort_order,f.sort_order,t.candidate_name""")

    def v22_company_classifications(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT c.company_id,c.display_name,c.entity_status,p.*,i.name industry_name,f.name field_name,t.candidate_name primary_topic,
          GROUP_CONCAT(DISTINCT x.candidate_name) linked_topics,GROUP_CONCAT(DISTINCT g.tag) auxiliary_tags
          FROM v22_companies c JOIN v22_company_profiles p USING(company_id)
          LEFT JOIN v22_industries i ON i.industry_id=p.primary_industry_id LEFT JOIN v22_fields f ON f.field_id=p.primary_field_id
          LEFT JOIN v22_topics t ON t.topic_id=p.primary_topic_id LEFT JOIN v22_company_topic_links l USING(company_id)
          LEFT JOIN v22_topics x ON x.topic_id=l.topic_id LEFT JOIN v22_company_tags g USING(company_id)
          GROUP BY c.company_id ORDER BY p.classification_status,c.display_name""")

    def v22_topic_relations(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT r.*,l.candidate_name left_name,x.candidate_name right_name
          FROM v22_topic_relations r JOIN v22_topics l ON l.topic_id=r.left_topic_id
          JOIN v22_topics x ON x.topic_id=r.right_topic_id ORDER BY r.relation_type,left_name""")

    def review_v22_topic(self, topic_id: str, *, action: str, actor: str, reason: str, value: str = "", company_id: str = "") -> None:
        allowed={"confirm_multi","confirm_observation","hold_split","exclude","rename","change_field","merge_suggestion","split_suggestion","move_company","add_tag"}
        if action not in allowed: raise ValueError("不支持的V2.2操作")
        if not actor.strip() or not reason.strip(): raise ValueError("审核人和审核依据不能为空")
        connection=connect(self.path);timestamp=now()
        try:
            with connection:
                row=connection.execute("SELECT * FROM v22_topics WHERE topic_id=?",(topic_id,)).fetchone()
                if not row: raise ValueError("未知V2.2主题")
                before=dict(row)
                if action=="confirm_multi": connection.execute("UPDATE v22_topics SET management_status='A_multi_company',review_status='confirmed',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="confirm_observation": connection.execute("UPDATE v22_topics SET management_status='B_observation',review_status='confirmed',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="hold_split": connection.execute("UPDATE v22_topics SET management_status='C_needs_further_split',review_status='held',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="exclude": connection.execute("UPDATE v22_topics SET review_status='excluded',updated_at=? WHERE topic_id=?",(timestamp,topic_id))
                elif action=="rename":
                    if not value.strip(): raise ValueError("新名称不能为空")
                    connection.execute("UPDATE v22_topics SET candidate_name=?,updated_at=? WHERE topic_id=?",(value.strip(),timestamp,topic_id))
                elif action=="change_field":
                    if not connection.execute("SELECT 1 FROM v22_fields WHERE field_id=?",(value,)).fetchone(): raise ValueError("目标领域无效")
                    connection.execute("UPDATE v22_topics SET field_id=?,updated_at=? WHERE topic_id=?",(value,timestamp,topic_id))
                elif action=="move_company":
                    if not company_id or not value: raise ValueError("请选择企业与目标主题")
                    link=connection.execute("SELECT * FROM v22_company_topic_links WHERE company_id=? AND topic_id=?",(company_id,topic_id)).fetchone()
                    if not link: raise ValueError("企业不属于当前主题")
                    connection.execute("DELETE FROM v22_company_topic_links WHERE company_id=? AND topic_id=?",(company_id,topic_id))
                    connection.execute("INSERT OR REPLACE INTO v22_company_topic_links VALUES (?,?,?,?,?,?,?)",(company_id,value,link["link_role"],link["product_basis"],link["technology_basis"],reason,"pending"))
                elif action=="add_tag":
                    if not company_id or not value.strip(): raise ValueError("请选择企业并输入标签")
                    connection.execute("INSERT OR REPLACE INTO v22_company_tags VALUES (?,?,?,?)",(company_id,value.strip(),reason,"pending"))
                after=dict(connection.execute("SELECT * FROM v22_topics WHERE topic_id=?",(topic_id,)).fetchone())
                connection.execute("INSERT INTO v22_topic_history VALUES (?,?,?,?,?,?,?,?)",(uid(),topic_id,action,actor.strip(),json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,timestamp))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor.strip(),"v22_"+action,"v22_topic",topic_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,timestamp))
        finally: connection.close()

    def v23_review_cards(self, candidate_class: str = "") -> list[dict[str, Any]]:
        where="WHERE c.candidate_class=?" if candidate_class else "";params=(candidate_class,) if candidate_class else ()
        return self.repo.rows(f"""SELECT c.*,t.candidate_name,t.technical_boundary,t.management_status,t.review_status,
          i.name industry_name,f.name field_name,COUNT(DISTINCT l.company_id) company_count,COUNT(DISTINCT et.event_id) event_count,
          COUNT(DISTINCT CASE WHEN e.data_status='formal' THEN e.event_id END) formal_count,
          COUNT(DISTINCT CASE WHEN e.data_status='A_candidate' THEN e.event_id END) a_count,
          COUNT(DISTINCT CASE WHEN e.data_status='B_candidate' THEN e.event_id END) b_count
          FROM v23_review_cards c JOIN v22_topics t ON t.topic_id=c.source_topic_id JOIN v22_fields f USING(field_id)
          JOIN v22_industries i USING(industry_id) LEFT JOIN v22_company_topic_links l ON l.topic_id=t.topic_id
          LEFT JOIN v22_event_topics et ON et.topic_id=t.topic_id LEFT JOIN v22_events e USING(event_id)
          {where} GROUP BY c.card_id ORDER BY i.sort_order,f.sort_order,t.candidate_name""",params)

    def v23_merge_previews(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT p.*,l.candidate_name left_name,r.candidate_name right_name
          FROM v23_merge_previews p JOIN v22_topics l ON l.topic_id=p.left_topic_id
          JOIN v22_topics r ON r.topic_id=p.right_topic_id ORDER BY p.proposed_name""")

    def v23_formal_directory(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT t.*,i.name industry_name,f.name field_name,GROUP_CONCAT(s.source_topic_id) source_topic_ids
          FROM v23_formal_topics t JOIN v22_fields f USING(field_id) JOIN v22_industries i USING(industry_id)
          LEFT JOIN v23_formal_topic_sources s USING(formal_topic_id) WHERE t.is_active=1 GROUP BY t.formal_topic_id
          ORDER BY i.sort_order,f.sort_order,t.formal_name""")

    def adjudicate_v23_topic(self, source_topic_id: str, *, decision: str, actor: str, reason: str,
                             formal_name: str = "", field_id: str = "") -> None:
        allowed={"confirm_formal","confirm_observation","hold","exclude","rename_and_confirm","change_field_and_confirm"}
        if decision not in allowed: raise ValueError("不支持的V2.3裁决")
        if not actor.strip() or not reason.strip(): raise ValueError("审核人和审核依据不能为空")
        connection=connect(self.path);timestamp=now()
        try:
            with connection:
                topic=connection.execute("SELECT * FROM v22_topics WHERE topic_id=?",(source_topic_id,)).fetchone()
                if not topic: raise ValueError("未知来源主题")
                before=dict(topic);result_id=None;after={"decision":decision}
                if decision in {"confirm_formal","confirm_observation","rename_and_confirm","change_field_and_confirm"}:
                    name=formal_name.strip() or topic["candidate_name"]
                    target_field=field_id or topic["field_id"]
                    if decision=="rename_and_confirm" and not formal_name.strip(): raise ValueError("请填写确认后的主题名称")
                    if not connection.execute("SELECT 1 FROM v22_fields WHERE field_id=?",(target_field,)).fetchone(): raise ValueError("目标技术领域无效")
                    topic_class="A_formal_multi" if decision!="confirm_observation" else "B_observation"
                    result_id="v23-"+uid();connection.execute("INSERT INTO v23_formal_topics VALUES (?,?,?,?,?,?,?,?,?)",(result_id,target_field,name,topic_class,topic["technical_boundary"],"confirmed",actor.strip(),timestamp,1))
                    connection.execute("INSERT INTO v23_formal_topic_sources VALUES (?,?,?)",(result_id,source_topic_id,"confirmed_source"));after=dict(connection.execute("SELECT * FROM v23_formal_topics WHERE formal_topic_id=?",(result_id,)).fetchone())
                connection.execute("INSERT INTO v23_adjudications VALUES (?,?,?,?,?,?,?,?,?)",(uid(),source_topic_id,result_id,decision,actor.strip(),json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,timestamp))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(),actor.strip(),"v23_"+decision,"v23_topic_adjudication",source_topic_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,timestamp))
        finally: connection.close()

    def v151_source_scope(self, batch1_only: bool = False) -> list[dict[str, Any]]:
        extra="AND q.queue_class='A' AND q.batch_number=1" if batch1_only else ""
        return self.repo.rows(f"""SELECT s.*,q.queue_class,q.batch_number,q.suggested_company_name,
          q.review_status FROM v151_source_scope_checks s JOIN v15_funding_review_queue q USING(review_item_id)
          WHERE 1=1 {extra} ORDER BY q.batch_number,s.disclosure_date DESC,q.suggested_company_name""")

    def v151_batch1_recommendations(self) -> list[dict[str, Any]]:
        return self.repo.rows("SELECT * FROM v151_batch1_recommendations ORDER BY source_page_date DESC,company_name")

    def funding_events(self, *, category_id: str = "", round_name: str = "", query: str = "") -> list[dict[str, Any]]:
        clauses = ["p.sample_month='2026-11'", "p.inclusion_status='included'"]
        params: list[Any] = []
        if category_id:
            clauses.append("p.category_id=?"); params.append(category_id)
        if round_name:
            clauses.append("p.normalized_round=?"); params.append(round_name)
        if query:
            clauses.append("(c.official_name LIKE ? OR COALESCE(c.short_name,'') LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        return self.repo.rows(f"""SELECT e.event_id,e.announcement_date,p.transaction_date,c.official_name AS company_name,
            ic.name AS primary_category,p.secondary_track,p.financing_type,p.normalized_round,e.round_original,
            e.amount_original,p.normalized_amount_cny,e.amount_currency,e.use_of_funds_original,e.evidence_grade,
            e.review_status,GROUP_CONCAT(DISTINCT i.official_name) AS investors,
            MIN(CASE WHEN ed.relationship='primary' THEN d.title END) AS source_title,
            MIN(CASE WHEN ed.relationship='primary' THEN d.original_url END) AS source_url
          FROM sample_event_profiles p JOIN funding_events e USING(event_id) JOIN companies c USING(company_id)
          JOIN industry_categories ic ON ic.category_id=p.category_id
          LEFT JOIN event_investors ei USING(event_id) LEFT JOIN investors i USING(investor_id)
          LEFT JOIN event_documents ed USING(event_id) LEFT JOIN raw_documents d USING(document_id)
          WHERE {' AND '.join(clauses)} GROUP BY e.event_id ORDER BY e.announcement_date DESC,c.official_name""", tuple(params))

    def acquisitions(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT a.*,ic.name AS primary_category,
            MIN(CASE WHEN ad.relationship='primary' THEN d.title END) AS source_title,
            MIN(CASE WHEN ad.relationship='primary' THEN d.original_url END) AS source_url
          FROM acquisition_events a JOIN industry_categories ic USING(category_id)
          LEFT JOIN acquisition_documents ad USING(acquisition_id) LEFT JOIN raw_documents d USING(document_id)
          WHERE a.sample_month='2026-11' GROUP BY a.acquisition_id ORDER BY a.disclosure_date DESC""")

    def technology_profiles(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT p.profile_id,p.company_id,c.official_name AS company_name,ic.name AS primary_category,
            p.secondary_track,p.primary_business,p.core_products,p.core_technologies,p.application_scenarios,
            p.value_chain_position,p.technical_problem,p.funding_use,p.cross_domain_tags,p.verification_status,p.review_status
          FROM company_technology_profiles p JOIN companies c USING(company_id)
          JOIN industry_categories ic ON ic.category_id=p.primary_category_id ORDER BY c.official_name""")

    def keywords(self, *, category_id: str = "", query: str = "") -> list[dict[str, Any]]:
        clauses = ["1=1"]; params: list[Any] = []
        if category_id:
            clauses.append("k.category_id=?"); params.append(category_id)
        if query:
            clauses.append("(k.raw_keyword LIKE ? OR k.normalized_keyword LIKE ?)"); params.extend([f"%{query}%", f"%{query}%"])
        return self.repo.rows(f"""SELECT k.keyword_id,k.raw_keyword,k.normalized_keyword,k.description,ic.name AS primary_category,
            GROUP_CONCAT(DISTINCT c.official_name) AS companies,GROUP_CONCAT(DISTINCT l.event_id) AS event_ids,
            GROUP_CONCAT(DISTINCT d.original_url) AS source_urls,k.verification_status
          FROM technology_keywords k JOIN industry_categories ic USING(category_id)
          LEFT JOIN technology_keyword_links l USING(keyword_id) LEFT JOIN companies c USING(company_id)
          LEFT JOIN raw_documents d USING(document_id) WHERE {' AND '.join(clauses)}
          GROUP BY k.keyword_id ORDER BY k.normalized_keyword""", tuple(params))

    def themes(self) -> list[dict[str, Any]]:
        return self.repo.rows("""SELECT t.theme_id,t.provisional_description,t.final_name,t.final_name_locked,
            ic.name AS primary_category,t.value_chain_position,t.formation_basis,t.boundary_definition,
            t.review_questions,t.review_status,COUNT(DISTINCT CASE WHEN m.is_current=1 THEN m.company_id END) AS company_count,
            COUNT(DISTINCT CASE WHEN m.is_current=1 THEN m.event_id END) AS event_count,
            COUNT(DISTINCT CASE WHEN m.is_current=1 THEN ei.investor_id END) AS investor_count,
            SUM(DISTINCT CASE WHEN m.is_current=1 AND e.amount_disclosure_type='exact' AND e.is_cumulative_amount=0 THEN e.amount_exact END) AS disclosed_amount_cny,
            GROUP_CONCAT(DISTINCT CASE WHEN m.is_current=1 THEN c.official_name END) AS companies,
            GROUP_CONCAT(DISTINCT k.normalized_keyword) AS keywords
          FROM candidate_themes t JOIN industry_categories ic USING(category_id)
          LEFT JOIN candidate_theme_members m USING(theme_id) LEFT JOIN companies c USING(company_id)
          LEFT JOIN funding_events e USING(event_id) LEFT JOIN event_investors ei USING(event_id)
          LEFT JOIN candidate_theme_keywords tk USING(theme_id) LEFT JOIN technology_keywords k USING(keyword_id)
          GROUP BY t.theme_id ORDER BY t.created_at,t.theme_id""")

    def theme_actions(self, theme_id: str = "") -> list[dict[str, Any]]:
        if theme_id:
            return self.repo.rows("SELECT * FROM candidate_theme_actions WHERE theme_id=? ORDER BY occurred_at DESC", (theme_id,))
        return self.repo.rows("SELECT * FROM candidate_theme_actions ORDER BY occurred_at DESC")

    def review_theme(self, theme_id: str, *, action: str, actor: str, reason: str, final_name: str = "") -> None:
        if action not in {"rename", "keep", "hold", "exclude", "restore"}:
            raise ValueError("Unsupported theme action")
        connection = connect(self.path)
        try:
            with connection:
                row = connection.execute("SELECT * FROM candidate_themes WHERE theme_id=?", (theme_id,)).fetchone()
                if not row: raise ValueError("Unknown theme")
                before = dict(row)
                if action == "rename":
                    if not final_name.strip(): raise ValueError("Final name is required")
                    connection.execute("UPDATE candidate_themes SET final_name=?,final_name_locked=1,updated_at=? WHERE theme_id=?", (final_name.strip(),now(),theme_id))
                else:
                    status = {"restore":"pending"}.get(action, action)
                    connection.execute("UPDATE candidate_themes SET review_status=?,updated_at=? WHERE theme_id=?", (status,now(),theme_id))
                after = dict(connection.execute("SELECT * FROM candidate_themes WHERE theme_id=?", (theme_id,)).fetchone())
                connection.execute("INSERT INTO candidate_theme_actions VALUES (?,?,?,?,?,?,?,?)", (uid(),theme_id,action,actor,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,now()))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (uid(),actor,f"theme_{action}","candidate_theme",theme_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,now()))
        finally:
            connection.close()

    def merge_theme(self, source_theme_id: str, target_theme_id: str, *, actor: str, reason: str) -> None:
        if source_theme_id == target_theme_id: raise ValueError("Themes must differ")
        connection = connect(self.path)
        try:
            with connection:
                source = connection.execute("SELECT * FROM candidate_themes WHERE theme_id=?", (source_theme_id,)).fetchone()
                target = connection.execute("SELECT * FROM candidate_themes WHERE theme_id=?", (target_theme_id,)).fetchone()
                if not source or not target: raise ValueError("Unknown theme")
                before = {"source":dict(source),"target":dict(target)}
                for row in connection.execute("SELECT company_id,event_id,membership_reason FROM candidate_theme_members WHERE theme_id=? AND is_current=1", (source_theme_id,)).fetchall():
                    connection.execute("INSERT OR IGNORE INTO candidate_theme_members VALUES (?,?,?,?,1,?)", (target_theme_id,row["company_id"],row["event_id"],f"merged: {row['membership_reason']}",now()))
                for row in connection.execute("SELECT keyword_id FROM candidate_theme_keywords WHERE theme_id=?", (source_theme_id,)).fetchall():
                    connection.execute("INSERT OR IGNORE INTO candidate_theme_keywords VALUES (?,?)", (target_theme_id,row["keyword_id"]))
                connection.execute("UPDATE candidate_themes SET review_status='merge',merged_into_theme_id=?,updated_at=? WHERE theme_id=?", (target_theme_id,now(),source_theme_id))
                after = {"source":dict(connection.execute("SELECT * FROM candidate_themes WHERE theme_id=?",(source_theme_id,)).fetchone()),"target_theme_id":target_theme_id}
                connection.execute("INSERT INTO candidate_theme_actions VALUES (?,?,?,?,?,?,?,?)", (uid(),source_theme_id,"merge",actor,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,now()))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (uid(),actor,"theme_merge","candidate_theme",source_theme_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,now()))
        finally:
            connection.close()

    def move_company(self, company_id: str, event_id: str, source_theme_id: str, target_theme_id: str, *, actor: str, reason: str) -> None:
        connection = connect(self.path)
        try:
            with connection:
                row = connection.execute("SELECT * FROM candidate_theme_members WHERE theme_id=? AND company_id=? AND event_id=? AND is_current=1", (source_theme_id,company_id,event_id)).fetchone()
                if not row: raise ValueError("Current membership not found")
                before = dict(row)
                connection.execute("UPDATE candidate_theme_members SET is_current=0 WHERE theme_id=? AND company_id=? AND event_id=?", (source_theme_id,company_id,event_id))
                connection.execute("INSERT OR REPLACE INTO candidate_theme_members VALUES (?,?,?,?,1,?)", (target_theme_id,company_id,event_id,f"manual move: {reason}",now()))
                after = {"source_theme_id":source_theme_id,"target_theme_id":target_theme_id,"company_id":company_id,"event_id":event_id}
                connection.execute("INSERT INTO candidate_theme_actions VALUES (?,?,?,?,?,?,?,?)", (uid(),source_theme_id,"move_company",actor,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,now()))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (uid(),actor,"theme_move_company","candidate_theme",source_theme_id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,now()))
        finally:
            connection.close()

    def split_member(self, company_id: str, event_id: str, source_theme_id: str, *, description: str, actor: str, reason: str) -> str:
        if not description.strip(): raise ValueError("Split theme description is required")
        connection = connect(self.path)
        new_theme_id = uid()
        try:
            with connection:
                source = connection.execute("SELECT * FROM candidate_themes WHERE theme_id=?", (source_theme_id,)).fetchone()
                member = connection.execute("SELECT * FROM candidate_theme_members WHERE theme_id=? AND company_id=? AND event_id=? AND is_current=1", (source_theme_id,company_id,event_id)).fetchone()
                if not source or not member: raise ValueError("Source theme or member not found")
                connection.execute("""INSERT INTO candidate_themes VALUES (?,?,?,?,?,?,?,'pending',NULL,0,NULL,?,?)""",
                    (new_theme_id,description.strip(),source["category_id"],source["value_chain_position"],f"Split from {source_theme_id}: {reason}",source["boundary_definition"],source["review_questions"],now(),now()))
                connection.execute("UPDATE candidate_theme_members SET is_current=0 WHERE theme_id=? AND company_id=? AND event_id=?", (source_theme_id,company_id,event_id))
                connection.execute("INSERT INTO candidate_theme_members VALUES (?,?,?,?,1,?)", (new_theme_id,company_id,event_id,f"manual split: {reason}",now()))
                after = {"new_theme_id":new_theme_id,"company_id":company_id,"event_id":event_id}
                connection.execute("INSERT INTO candidate_theme_actions VALUES (?,?,?,?,?,?,?,?)", (uid(),source_theme_id,"split",actor,json.dumps(dict(member),ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,now()))
                connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (uid(),actor,"theme_split","candidate_theme",source_theme_id,json.dumps(dict(member),ensure_ascii=False),json.dumps(after,ensure_ascii=False),reason,None,now()))
        finally:
            connection.close()
        return new_theme_id
