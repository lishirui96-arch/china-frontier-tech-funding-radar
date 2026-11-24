import streamlit as st
from funding_radar.repository import LedgerRepository
from funding_radar.source_service import create_source, update_source

st.title("来源管理")
repo = LedgerRepository()
sources = repo.rows("SELECT * FROM sources ORDER BY evidence_default_grade,name")
st.dataframe(sources, width="stretch", hide_index=True, alt="来源配置和抓取状态")
with st.form("new_source"):
    st.subheader("新增来源")
    name = st.text_input("来源名称")
    domain = st.text_input("来源域名")
    source_type = st.selectbox("来源类别", ["company_official","investor_official","regulatory","government","university_transfer","professional_media","technology_media","aggregator"])
    family = st.text_input("来源族", value="official")
    grade = st.segmented_control("证据等级", ["S","A","B","C","D"], default="C")
    scope = st.selectbox("允许访问范围", ["metadata_only","rss_only","listed_news_pages","public_pages"])
    interval = st.number_input("最小抓取间隔（秒）", min_value=60, value=3600, step=60)
    reason = st.text_input("新增理由")
    submitted = st.form_submit_button("新增来源", type="primary")
if submitted and name and reason:
    create_source({"name":name,"source_type":source_type,"source_family":family,"grade":grade,"base_url":domain,"allowed_scope":scope,"min_interval_seconds":interval},"local-reviewer",reason)
    st.success("来源已新增并记录审计日志")
    st.rerun()
if sources:
    selected = st.selectbox("编辑来源", sources, format_func=lambda x: f"{x['name']} · {x['evidence_default_grade']}")
    active = st.toggle("启用", value=bool(selected["is_active"]))
    new_grade = st.segmented_control("调整等级", ["S","A","B","C","D"], default=selected["evidence_default_grade"], key="edit_grade")
    edit_reason = st.text_input("修改理由")
    if st.button("保存来源修改", disabled=not edit_reason):
        update_source(selected["source_id"],{"is_active":int(active),"evidence_default_grade":new_grade},"local-reviewer",edit_reason)
        st.success("已保存")
        st.rerun()
