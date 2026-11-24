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
        "唯一事件": repo.rows("SELECT COUNT(*) n FROM funding_events")[0]["n"],
        "待审重复": repo.rows("SELECT COUNT(*) n FROM dedup_candidates WHERE status='pending'")[0]["n"],
        "发布快照": repo.rows("SELECT COUNT(*) n FROM releases")[0]["n"],
    }
    for col, (label, value) in zip(st.columns(4), counts.items()):
        col.metric(label, value)
    st.info("请依次完成文档、实体、去重、事件和发布审核。")

page = st.navigation(
    [
        st.Page(home_page, title="账本概览", icon=":material/receipt_long:", default=True),
        st.Page("app_pages/01_candidate_documents.py", title="候选文档", icon=":material/article:"),
        st.Page("app_pages/02_entity_review.py", title="实体审核", icon=":material/domain:"),
        st.Page("app_pages/03_dedup_review.py", title="去重审核", icon=":material/compare_arrows:"),
        st.Page("app_pages/04_event_review.py", title="事件审核", icon=":material/fact_check:"),
        st.Page("app_pages/05_release_review.py", title="发布审核", icon=":material/publish:"),
    ],
    position="top",
)
page.run()

