import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); st.title("V1.5.1 项目进度与研究口径")
st.caption("融资来源仅采用投资界与SpaceDaily；采集窗口为2026-11-01至2026-11-25。历史范围外来源保留但不计入当前来源口径。")
s=service.v151_progress()
progress=[
 {"评价维度":"投资界主要栏目采集","当前结果":f"{s['pedaily_candidates']}条候选具备投资界来源","状态":"已完成既定窗口采集"},
 {"评价维度":"SpaceDaily公开记录提取","当前结果":f"{s['spacedaily_candidates']}条候选由SpaceDaily渠道支撑","状态":"已完成公开记录提取"},
 {"评价维度":"11月1日至25日采集范围","当前结果":f"{s['date_in_scope']}条A/B候选在日期范围内","状态":"截止11月25日"},
 {"评价维度":"企业名称简单排查","当前结果":f"{s['name_checked']}条名称准确或已修正","状态":"保留明显疑点待审"},
 {"评价维度":"融资轮次准确性","当前结果":"原始轮次保留；冲突和多轮记录进入B类专项审核","状态":"人工审核中"},
 {"评价维度":"并购事件覆盖","当前结果":f"{s['acquisitions']}条独立并购候选","状态":"等待人工确认交易状态"},
 {"评价维度":"A类人工审核进度","当前结果":f"{s['a_reviewed']}/{s['a_total']}","状态":"未由系统自动审核"},
 {"评价维度":"B类待核验进度","当前结果":f"已处理{s['b_resolved']}/{s['b_total']}","状态":"等待人工裁决"},
 {"评价维度":"正式融资事件数量","当前结果":str(s['confirmed_events']),"状态":"仅统计人工确认事件"},
 {"评价维度":"技术主题归类进度","当前结果":f"{s['technology_classified']}条正式事件生成技术分析准备","状态":"不自动命名主题"},
]
st.dataframe(pd.DataFrame(progress),hide_index=True,width="stretch")
st.warning(f"当前有{s['out_of_scope_sources']}条候选只有范围外历史来源，已保留并标记待处理，不计入符合当前来源口径的正式样本。")
tab_scope,tab_batch=st.tabs(["来源范围检查","第一批修订建议"])
with tab_scope: st.dataframe(pd.DataFrame(service.v151_source_scope()),hide_index=True,width="stretch",column_config={"primary_url":st.column_config.LinkColumn("原始链接")})
with tab_batch: st.dataframe(pd.DataFrame(service.v151_batch1_recommendations()),hide_index=True,width="stretch")
