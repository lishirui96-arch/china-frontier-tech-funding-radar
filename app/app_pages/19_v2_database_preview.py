import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); events=service.v2_events(); summary=service.v2_theme_summary()
st.title("科技融资数据库预览")
st.caption("内部预览包含正式、A类待审和B类待核验事件；8511公开站仍只展示正式发布数据。")
for col,(label,key) in zip(st.columns(4),[("主题关联正式事件","formal_events"),("A类待审","a_events"),("B类待核验","b_events"),("候选主题","topic_count")]): col.metric(label,summary[key])
status=st.multiselect("审核状态",["formal","A_candidate","B_candidate"],default=["formal","A_candidate","B_candidate"])
query=st.text_input("搜索企业")
rows=[x for x in events if x["event_source_type"] in status and (not query or query.lower() in x["company_name"].lower())]
st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
if rows:
    chosen=st.selectbox("事件详情",range(len(rows)),format_func=lambda i:f"{rows[i]['disclosure_date']} · {rows[i]['company_name']} · {rows[i]['round_original']}")
    row=rows[chosen]; st.table({"企业":row["company_name"],"日期":row["disclosure_date"],"轮次":row["round_original"],"金额":row["amount_original"],"主题":row["topics"],"状态":row["event_source_type"]})
