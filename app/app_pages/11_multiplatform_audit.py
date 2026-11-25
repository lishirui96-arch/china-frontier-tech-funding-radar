import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService


service=SampleLibraryService()
st.title("V1.2 历史多平台交叉核验")
st.caption("本页仅保留历史采集结果。V1.5.1不再考核多平台独立发现或交叉覆盖率。")
summary=service.v12_summary()
cols=st.columns(4)
cols[0].metric("候选观察",summary["candidate_observations"])
cols[1].metric("去重后新增",summary["new_candidates"])
cols[2].metric("V1.0/V1.1重复",summary["duplicates"])
cols[3].metric("待核验",summary["pending"])

st.subheader("平台访问与采集")
st.dataframe(pd.DataFrame(service.v12_platform_audits()),hide_index=True,width="stretch")

all_rows=service.v12_candidates()
platforms=sorted({row["source_platform"] for row in all_rows})
controls=st.container(horizontal=True,vertical_alignment="bottom")
platform=controls.selectbox("来源平台",["全部",*platforms])
status=controls.selectbox("候选状态",["全部","new","duplicate_v1_v11","pending_scope","excluded_market"])
rows=service.v12_candidates("" if platform=="全部" else platform,"" if status=="全部" else status)
display=pd.DataFrame([{"日期":r["disclosure_date"],"企业":r["company_name_original"],"轮次":r["round_original"],"金额":r["amount_original"],"投资方":r["investors_original"],"平台":r["source_platform"],"核验":r["verification_status"],"状态":r["candidate_status"],"待解决问题":r["unresolved_fields"],"原文":r["original_url"]} for r in rows])
st.dataframe(display,hide_index=True,width="stretch",column_config={"原文":st.column_config.LinkColumn("原文")})
