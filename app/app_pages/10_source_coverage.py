import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService


service = SampleLibraryService()
st.title("V1.1 来源覆盖审计")
st.caption("检索窗口：2026-11-01 至 2026-11-25。新增候选需经人工审核后才能进入正式事件和公开站。")

summary = service.v11_summary()
cols = st.columns(4)
cols[0].metric("投资界来源文档", summary.get("pedaily_documents", 0))
cols[1].metric("目标轮次候选", summary.get("verified_new", 0) + summary.get("duplicate_v1", 0))
cols[2].metric("与V1.0重复", summary.get("duplicate_v1", 0))
cols[3].metric("SpaceDaily待核验", summary.get("spacedaily_records", 0))

st.subheader("投资界分页覆盖")
st.dataframe(pd.DataFrame(service.source_coverage()), hide_index=True, width="stretch")

status = st.segmented_control("候选状态", ["全部", "新增候选", "V1.0重复"], default="全部")
status_code = {"新增候选": "verified_new", "V1.0重复": "duplicate_v1"}.get(status, "")
rows = service.v11_candidates(status_code)
display = pd.DataFrame([{
    "披露日期": row["disclosure_date"], "企业": row["company_name_original"], "轮次": row["round_original"],
    "金额": row["amount_original"], "状态": row["candidate_status"], "未确认字段": row["unresolved_fields"], "原文": row["original_url"],
} for row in rows])
st.dataframe(display, hide_index=True, width="stretch", column_config={"原文": st.column_config.LinkColumn("原文")})
