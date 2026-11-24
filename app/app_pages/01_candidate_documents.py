import streamlit as st
from funding_radar.repository import LedgerRepository

st.title("候选文档")
repo = LedgerRepository()
documents = repo.list_documents()
st.dataframe(documents, width="stretch", hide_index=True)
if documents:
    labels = {f"{d['title']} · {d['document_id'][:8]}": d for d in documents}
    selected = labels[st.selectbox("选择文档", labels)]
    st.write(selected.get("text_or_summary") or "未保存正文或摘要")
    st.link_button("打开原始来源", selected["original_url"])
    relevance = st.segmented_control("相关性", ["relevant", "irrelevant", "uncertain"], default="uncertain")
    reason = st.text_input("审核理由")
    if st.button("保存审核", type="primary", disabled=not reason):
        repo.update_document_review(selected["document_id"], relevance, "local-reviewer", reason)
        st.success("已记录审核和审计日志")
        st.rerun()

