import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); st.title("正式样本统计与技术分析准备")
st.caption("本页只读取人工确认纳入的V1.5正式月度样本。未披露金额保持为空，不按0处理。")
summary=service.v15_review_summary(); st.metric("人工确认正式事件",summary.get("confirmed_events",0))
tab_stats,tab_tech=st.tabs(["正式融资统计","技术主题分析准备"])
with tab_stats:
    data=service.v15_confirmed_statistics()
    if data: st.dataframe(pd.DataFrame(data),hide_index=True,width="stretch")
    else: st.info("尚无人工确认纳入的正式事件。完成审核后统计将自动出现。")
with tab_tech:
    data=service.v15_technology_analysis()
    if data: st.dataframe(pd.DataFrame(data),hide_index=True,width="stretch")
    else: st.info("技术画像只为人工确认的正式事件生成。目前没有可分析记录。")
