from pathlib import Path
import inspect
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from funding_radar.migrations import migrate
from funding_radar.repository import LedgerRepository

st.set_page_config(page_title="融资事件账本 V1", page_icon=":material/receipt_long:", layout="wide")

# Keep navigation compatible with Streamlit releases that predate Page.help.
if "help" not in inspect.signature(st.Page).parameters:
    _streamlit_page = st.Page

    def _compatible_page(*args, **kwargs):
        kwargs.pop("help", None)
        return _streamlit_page(*args, **kwargs)

    st.Page = _compatible_page

if "alt" not in inspect.signature(st.dataframe).parameters:
    _streamlit_dataframe = st.dataframe

    def _compatible_dataframe(*args, **kwargs):
        kwargs.pop("alt", None)
        return _streamlit_dataframe(*args, **kwargs)

    st.dataframe = _compatible_dataframe

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
        st.dataframe(repo.rows("SELECT evidence_default_grade AS 等级, COUNT(*) AS 来源数 FROM sources GROUP BY evidence_default_grade ORDER BY evidence_default_grade"), width="stretch", hide_index=True)
    with right:
        st.subheader("金额披露类型分布")
        st.dataframe(repo.rows("SELECT amount_disclosure_type AS 类型, COUNT(*) AS 事件数 FROM funding_events GROUP BY amount_disclosure_type ORDER BY amount_disclosure_type"), width="stretch", hide_index=True)
    st.subheader("各来源成功率")
    st.dataframe(repo.rows("""SELECT s.name AS 来源, COUNT(r.discovery_run_id) AS 运行数,
        COALESCE(SUM(r.inserted_count),0) AS 新增文档, COALESCE(SUM(r.failure_count),0) AS 失败数,
        CASE WHEN COALESCE(SUM(r.request_count),0)=0 THEN NULL ELSE ROUND(1.0-(1.0*SUM(r.failure_count)/SUM(r.request_count)),3) END AS 成功率
        FROM sources s LEFT JOIN discovery_runs r USING(source_id) GROUP BY s.source_id ORDER BY s.name"""), width="stretch", hide_index=True)
    st.info("请依次完成文档、实体、去重、事件和发布审核。")

page = st.navigation({
    "": [st.Page(home_page, title="账本概览", icon=":material/receipt_long:", default=True)],
    "11月样本库": [
        st.Page("app_pages/06_november_samples.py", title="融资与并购明细", icon=":material/table_view:", help="查看2026年11月增量样本，按产业、赛道、轮次和企业筛选，并下载完整Excel。"),
        st.Page("app_pages/07_technology_keywords.py", title="技术关键词库", icon=":material/key:", help="查看企业、事件、证据来源与标准化技术关键词的对应关系。"),
        st.Page("app_pages/08_candidate_themes.py", title="候选主题库", icon=":material/hub:", help="查看人工审核前的技术关联分组、边界、企业、事件和关键词。"),
        st.Page("app_pages/09_theme_review.py", title="候选主题人工审核", icon=":material/rule:", help="执行候选主题改名、合并、拆分、成员移动和状态决定，所有操作保留审计记录。"),
        st.Page("app_pages/10_source_coverage.py", title="历史来源审计", icon=":material/travel_explore:", help="查看V1.1历史采集记录；不作为V1.5.1当前进度评价。"),
        st.Page("app_pages/11_multiplatform_audit.py", title="历史多平台审计", icon=":material/compare_arrows:", help="保留V1.2历史多平台记录；当前融资来源口径仅为投资界和SpaceDaily。"),
        st.Page("app_pages/12_quality_audit.py", title="候选质量审计", icon=":material/fact_check:", help="查看V1.3企业实体、字段级核验、重复冲突及并购核验结果。"),
        st.Page("app_pages/13_event_review_queue.py", title="融资事件审核队列", icon=":material/playlist_add_check:", help="裁决轮次冲突、重复关系与样本统计资格，所有人工操作写入审计日志。"),
        st.Page("app_pages/14_formal_funding_review.py", title="11月正式融资审核", icon=":material/how_to_reg:", help="分批人工确认A类候选，专项处理B类问题；默认不执行任何决定。"),
        st.Page("app_pages/15_acquisition_review.py", title="并购人工审核", icon=":material/account_balance:", help="人工确认并购交易阶段，严格区分拟收购、审议、审批和交割。"),
        st.Page("app_pages/16_confirmed_statistics.py", title="正式样本统计与技术分析", icon=":material/analytics:", help="仅统计人工确认纳入的正式月度样本，并准备企业技术画像。"),
        st.Page("app_pages/17_project_progress.py", title="项目进度与研究口径", icon=":material/checklist:", help="查看V1.5.1投资界/SpaceDaily来源口径、11月1日至25日范围及人工审核进度。"),
        st.Page("app_pages/18_v2_theme_workbench.py", title="科技融资主题工作台", icon=":material/account_tree:", help="按核心产品、技术和产业链问题审核V2候选主题。"),
        st.Page("app_pages/19_v2_database_preview.py", title="科技融资数据库预览", icon=":material/database:", help="在内部预览正式、A类与B类融资事件，状态分开显示。"),
        st.Page("app_pages/20_v211_profile_review.py", title="企业技术画像复核", icon=":material/manage_search:", help="复核企业业务、产品、技术、产业链及主题依据；默认不提交决定。"),
        st.Page("app_pages/21_v22_taxonomy.py", title="V2.2三级分类管理", icon=":material/schema:", help="按10个一级产业、二级领域和三级候选主题管理企业与事件关联。"),
        st.Page("app_pages/22_v23_topic_adjudication.py", title="V2.3主题人工裁决", icon=":material/gavel:", help="审核多企业主题、观察项、合并预览和待拆分主题；所有决定需人工提交。"),
        st.Page("app_pages/23_v231_admission_review.py", title="V2.3.1主题准入审查", icon=":material/fact_check:", help="查看14个拟确认主题的第二轮质量审查、成员证据等级、实体重复和主题交叉建议。"),
        st.Page("app_pages/24_v30_taxonomy_migration.py", title="V3.0分类与历史迁移", icon=":material/account_tree:", help="管理冻结的10→38→34分类体系，审核97条历史记录归类及关联变更。"),
        st.Page("app_pages/25_v31_pending_classification.py", title="21条待分类来源复核", icon=":material/manage_search:", help="查看21条原始来源中的主营业务、产品、技术和V3.1分类增量建议。"),
        st.Page("app_pages/26_monthly_capital_preview.py", title="本月资本流向预览", icon=":material/monitoring:", help="只读查看正式统计、历史22条质量和A/B候选分布；公开统计严格隔离。"),
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

