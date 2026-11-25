import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); summary=service.v2_theme_summary(); topics=service.v2_topics()
st.title("科技融资主题工作台")
st.caption("候选主题来自企业产品、核心技术和产业链问题；名称与边界均等待人工确认。正式、A类和B类事件分别统计。")
labels=[("产业方向",summary["industry_count"]),("技术领域",summary["field_count"]),("候选主题",summary["topic_count"]),("单企业观察",summary["observation_count"]),("涉及企业",summary["company_count"]),("待补充画像",summary["unclassified_count"])]
for col,(label,value) in zip(st.columns(6),labels): col.metric(label,value)
industry=st.selectbox("产业方向",["全部"]+sorted({x["industry_name"] for x in topics}))
kind=st.segmented_control("主题类型",["全部","多企业主题","单企业观察"],default="全部")
rows=[x for x in topics if (industry=="全部" or x["industry_name"]==industry) and (kind=="全部" or (kind=="单企业观察")==(x["topic_kind"]=="single_company_observation"))]
columns=["candidate_name","industry_name","field_name","company_count","event_count","formal_count","a_count","b_count","review_status"]
st.dataframe(pd.DataFrame(rows,columns=columns)[columns],hide_index=True,width="stretch")
for row in rows:
    with st.expander(row["candidate_name"]):
        st.write(row["topic_description"]); st.caption(row["technical_boundary"])
        st.write("关联企业：",row["companies"] or "—"); st.write("轮次：",row["rounds"] or "—")
        st.info("待人工判断："+row["human_questions"])
st.subheader("企业技术画像")
st.dataframe(pd.DataFrame(service.v2_profiles()),hide_index=True,width="stretch")
