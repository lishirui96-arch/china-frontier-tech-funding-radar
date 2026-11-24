from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from funding_radar.migrations import migrate
from funding_radar.repository import LedgerRepository

st.set_page_config(page_title="融资事件账本 V1", page_icon=":material/receipt_long:", layout="wide")
migrate()

def home_page():
    repo = LedgerRepository()
    st.title("融资事件账本 V1")
    st.caption("内部审核工具 · 试验样本不代表全市场 · 不用于公开排名")
    counts = {
        "候选文档": repo.rows("SELECT COUNT(*) n FROM raw_documents")[0]["n"],
        "待审核文档": repo.rows("SELECT COUNT(*) n FROM raw_documents WHERE review_status NOT IN ('approved','published','rejected')")[0]["n"],
        "有效候选事件": repo.rows("SELECT COUNT(*) n FROM funding_events WHERE event_status='candidate'")[0]["n"],
        "唯一融资事件": repo.rows("SELECT COUNT(*) n FROM funding_events WHERE event_status<>'superseded'")[0]["n"],
        "重复候选": repo.rows("SELECT COUNT(*) n FROM dedup_candidates WHERE status='pending'")[0]["n"],
        "已审核事件": repo.rows("SELECT COUNT(*) n FROM funding_events WHERE review_status IN ('field_review','approved','published')")[0]["n"],
        "已批准事件": repo.rows("SELECT COUNT(*) n FROM funding_events WHERE review_status IN ('approved','published')")[0]["n"],
    }
    for col, (label, value) in zip(st.columns(7), counts.items()):
        col.metric(label, value)
    left, right = st.columns(2)
    with left:
        st.subheader("来源等级分布")
        st.dataframe(repo.rows("SELECT evidence_default_grade AS 等级, COUNT(*) AS 来源数 FROM sources GROUP BY evidence_default_grade ORDER BY evidence_default_grade"), width="stretch", hide_index=True, alt="来源等级分布")
    with right:
        st.subheader("金额披露类型分布")
        st.dataframe(repo.rows("SELECT amount_disclosure_type AS 类型, COUNT(*) AS 事件数 FROM funding_events GROUP BY amount_disclosure_type ORDER BY amount_disclosure_type"), width="stretch", hide_index=True, alt="金额披露类型分布")
    st.subheader("各来源成功率")
    st.dataframe(repo.rows("""SELECT s.name AS 来源, COUNT(r.discovery_run_id) AS 运行数,
        COALESCE(SUM(r.inserted_count),0) AS 新增文档, COALESCE(SUM(r.failure_count),0) AS 失败数,
        CASE WHEN COALESCE(SUM(r.request_count),0)=0 THEN NULL ELSE ROUND(1.0-(1.0*SUM(r.failure_count)/SUM(r.request_count)),3) END AS 成功率
        FROM sources s LEFT JOIN discovery_runs r USING(source_id) GROUP BY s.source_id ORDER BY s.name"""), width="stretch", hide_index=True, alt="各来源发现成功率")
    st.info("请依次完成文档、实体、去重、事件和发布审核。")

page = st.navigation(
    [
        st.Page(home_page, title="账本概览", icon=":material/receipt_long:", default=True),
        st.Page("app_pages/00_url_import.py", title="URL 导入", icon=":material/upload_file:"),
        st.Page("app_pages/00_source_management.py", title="来源管理", icon=":material/source:"),
        st.Page("app_pages/01_candidate_documents.py", title="候选文档", icon=":material/article:"),
        st.Page("app_pages/02_entity_review.py", title="实体审核", icon=":material/domain:"),
        st.Page("app_pages/03_dedup_review.py", title="去重审核", icon=":material/compare_arrows:"),
        st.Page("app_pages/04_event_review.py", title="事件审核", icon=":material/fact_check:"),
        st.Page("app_pages/05_release_review.py", title="发布审核", icon=":material/publish:"),
    ],
    position="top",
)
page.run()

