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
