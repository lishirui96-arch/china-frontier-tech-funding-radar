import json

import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService


service = SampleLibraryService()
reviews = service.v231_admission_reviews()
members = service.v231_member_quality()
entities = service.v231_entity_reviews()
cross_links = service.v231_cross_topic_reviews()

st.title("V2.3.1 主题准入质量审查")
st.caption("第二轮审查结果仅为独立建议，不确认、合并或修改任何主题、企业及融资事件。")

conclusion_counts = pd.Series([row["admission_conclusion"] for row in reviews]).value_counts().to_dict()
grade_counts = pd.Series([row["quality_grade"] for row in members]).value_counts().to_dict()
metrics = [
    ("审查主题", len(reviews)),
    ("调整成员后提交", sum(value for key, value in conclusion_counts.items() if key.startswith("C."))),
    ("建议拆分", sum(value for key, value in conclusion_counts.items() if key.startswith("D."))),
    ("暂缓", sum(value for key, value in conclusion_counts.items() if key.startswith("E."))),
    ("成员关系", len(members)),
]
for column, (label, value) in zip(st.columns(5), metrics):
    column.metric(label, value)

topic_tab, member_tab, entity_tab, cross_tab = st.tabs(["14个主题", "企业画像依据", "重复实体", "主题交叉"])

with topic_tab:
    options = {f"{row['industry_name']} → {row['field_name']} → {row['candidate_name']}": row for row in reviews}
    if options:
        selected = options[st.selectbox("选择主题", list(options))]
        st.table({
            "准入建议": selected["admission_conclusion"],
            "具体理由": selected["conclusion_reason"],
            "共同技术主张": selected["common_technology_claim"],
            "主题边界": selected["boundary_assessment"],
            "企业差异": selected["difference_assessment"],
            "交叉关系": selected["cross_topic_notes"],
            "唯一企业 / 唯一事件": f"{selected['unique_company_count']} / {selected['unique_event_count']}",
            "正式 / A / B": f"{selected['formal_count']} / {selected['a_count']} / {selected['b_count']}",
            "重复风险": selected["duplicate_risk"],
        }, border="horizontal")
        detail = pd.DataFrame(service.v231_member_quality(selected["source_topic_id"]))
        st.subheader("成员证据明细")
        st.dataframe(detail, hide_index=True, alt="所选主题成员的产品、技术和证据质量明细")

with member_tab:
    st.caption("A=产品、技术和URL依据充分；B=产品明确但技术不足；C=技术明确但产品不足；D=有效依据不足。")
    st.dataframe(pd.DataFrame(members), hide_index=True, alt="14个主题全部企业成员的画像质量等级")
    st.table({f"{grade}级": count for grade, count in sorted(grade_counts.items())}, border="horizontal")

with entity_tab:
    st.warning("优理奇两条记录仅建立主从ID映射建议。现有资料没有可靠统一社会信用代码，因此不会自动合并。")
    st.dataframe(pd.DataFrame(entities), hide_index=True, alt="疑似重复企业实体的核查与ID映射建议")

with cross_tab:
    st.caption("跨主题关系只有在存在具体产品或技术依据时才建议保留；融资事件全局仍按唯一事件ID计数。")
    st.dataframe(pd.DataFrame(cross_links), hide_index=True, alt="企业跨主题关系及其产品技术依据")

st.info("需要提交裁决时，请返回 V2.3 主题人工裁决页面。此页不会写入任何人工决定。")
