import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService


service = SampleLibraryService()
st.title("V1.3 候选事件质量审计")
st.caption("候选层只读审计；字段核实不等同于正式事件入库，披露日期不代表实际交割日期。")

summary = service.v13_summary()
for col, (label, key) in zip(st.columns(6), [
    ("独立候选", "candidates"), ("企业实体", "companies"), ("名称准确", "accurate_names"),
    ("名称修正", "corrected_names"), ("确认重复", "confirmed_duplicates"), ("完整核实", "complete"),
]):
    col.metric(label, summary[key])

tab_candidates, tab_fields, tab_relations, tab_acquisitions = st.tabs([
    "候选质量", "字段级核验", "重复与冲突", "并购核验",
])
with tab_candidates:
    status = st.selectbox("整体核验状态", ["全部", "complete", "partial", "pending", "conflict"])
    rows = service.v13_candidate_audits("" if status == "全部" else status)
    display = pd.DataFrame([{
        "披露日期": r["normalized_disclosure_date"], "企业": r["normalized_company_name"],
        "原始企业名": r["original_company_name"], "轮次": r["normalized_round"],
        "金额": r["normalized_amount"], "投资方": r["normalized_investors"],
        "名称质量": r["name_quality_status"], "核验状态": r["overall_verification_status"],
        "证据等级": r["evidence_grade"], "问题": r["quality_issues_json"], "原文": r["source_url"],
    } for r in rows])
    st.dataframe(display, hide_index=True, width="stretch", column_config={"原文": st.column_config.LinkColumn("原文")})

with tab_fields:
    controls = st.container(horizontal=True, vertical_alignment="bottom")
    field_name = controls.selectbox("核验字段", ["全部", "event_verified", "company_verified", "round_verified", "amount_verified", "investor_verified", "date_verified", "source_verified"])
    field_status = controls.selectbox("字段状态", ["全部", "verified", "partially_verified", "pending", "conflict", "not_applicable"])
    rows = service.v13_field_verifications("" if field_name == "全部" else field_name, "" if field_status == "全部" else field_status)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

with tab_relations:
    st.dataframe(pd.DataFrame(service.v13_relations()), hide_index=True, width="stretch")

with tab_acquisitions:
    st.dataframe(pd.DataFrame(service.v13_acquisition_verifications()), hide_index=True, width="stretch")
