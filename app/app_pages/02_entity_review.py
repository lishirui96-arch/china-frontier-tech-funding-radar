import streamlit as st
from funding_radar.repository import LedgerRepository
from funding_radar.review_service import confirm_entity

st.title("实体审核")
repo = LedgerRepository()
tab1, tab2 = st.tabs(["企业", "投资机构"])
with tab1:
    st.dataframe(repo.list_entities("companies"), width="stretch", hide_index=True)
    st.subheader("企业别名与证据")
    st.dataframe(repo.list_aliases("companies"), width="stretch", hide_index=True)
with tab2:
    st.dataframe(repo.list_entities("investors"), width="stretch", hide_index=True)
    st.subheader("机构别名与证据")
    st.dataframe(repo.list_aliases("investors"), width="stretch", hide_index=True)
st.warning("V1 不会仅凭名称自动合并。同名、集团/子公司、品牌/法人和基金载体差异必须人工确认。")
kind = st.segmented_control("确认主体类型", ["company","investor"], default="company")
entities = repo.list_entities("companies" if kind=="company" else "investors")
if entities:
    key = "company_id" if kind=="company" else "investor_id"
    selected = st.selectbox("选择主体", entities, format_func=lambda x: x["official_name"])
    reason = st.text_input("确认理由")
    if st.button("确认主体", type="primary", disabled=not reason):
        confirm_entity(kind,selected[key],"local-reviewer",reason)
        st.success("主体已确认并记录审计日志")
        st.rerun()

