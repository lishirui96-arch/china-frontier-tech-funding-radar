import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService

service = SampleLibraryService()
st.title("候选技术主题库")
st.caption("这里只展示证据支持的技术关联分组，不自动确定最终主题名称或热点排名。")
rows = service.themes()
st.metric("候选主题", len(rows))
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", alt="候选技术主题、企业、融资事件和技术关键词")
for row in rows:
    with st.expander(row["final_name"] or row["provisional_description"]):
        st.table({"一级产业":row["primary_category"],"产业链位置":row["value_chain_position"],"企业":row["companies"] or "—","关键词":row["keywords"] or "—","形成依据":row["formation_basis"],"主题边界":row["boundary_definition"],"待审核问题":row["review_questions"],"人工状态":row["review_status"]}, border="horizontal", width="stretch")
