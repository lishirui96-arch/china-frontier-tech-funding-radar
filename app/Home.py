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

page = st.navigation({
    "": [st.Page(home_page, title="账本概览", icon=":material/receipt_long:", default=True)],
    "11月样本库": [
        st.Page("app_pages/06_november_samples.py", title="融资与并购明细", icon=":material/table_view:", help="查看2026年11月增量样本，按产业、赛道、轮次和企业筛选，并下载完整Excel。"),
        st.Page("app_pages/07_technology_keywords.py", title="技术关键词库", icon=":material/key:", help="查看企业、事件、证据来源与标准化技术关键词的对应关系。"),
        st.Page("app_pages/08_candidate_themes.py", title="候选主题库", icon=":material/hub:", help="查看人工审核前的技术关联分组、边界、企业、事件和关键词。"),
        st.Page("app_pages/09_theme_review.py", title="候选主题人工审核", icon=":material/rule:", help="执行候选主题改名、合并、拆分、成员移动和状态决定，所有操作保留审计记录。"),
        st.Page("app_pages/10_source_coverage.py", title="来源覆盖审计", icon=":material/travel_explore:", help="查看V1.1来源遍历、交叉重复和新增候选。"),
        st.Page("app_pages/11_multiplatform_audit.py", title="多平台交叉核验", icon=":material/compare_arrows:", help="查看SpaceDaily、36氪、投中、财联社等平台候选及交叉去重结果。"),
        st.Page("app_pages/12_quality_audit.py", title="候选质量审计", icon=":material/fact_check:", help="查看V1.3企业实体、字段级核验、重复冲突及并购核验结果。"),
    ],
    "采集与审核": [
        st.Page("app_pages/00_url_import.py", title="URL 导入", icon=":material/upload_file:"),
        st.Page("app_pages/00_source_management.py", title="来源管理", icon=":material/source:"),
        st.Page("app_pages/01_candidate_documents.py", title="候选文档", icon=":material/article:"),
        st.Page("app_pages/02_entity_review.py", title="实体审核", icon=":material/domain:"),
        st.Page("app_pages/03_dedup_review.py", title="去重审核", icon=":material/compare_arrows:"),
        st.Page("app_pages/04_event_review.py", title="事件审核", icon=":material/fact_check:"),
        st.Page("app_pages/05_release_review.py", title="发布审核", icon=":material/publish:"),
    ],
}, position="sidebar")
page.run()

