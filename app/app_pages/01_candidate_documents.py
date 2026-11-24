import streamlit as st
from funding_radar.document_service import extract_document, screen_document
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
    category = st.selectbox("融资初筛", ["primary_equity","merger_acquisition","ipo","private_placement","bond","bank_credit","government_subsidy","research_grant","non_financing","undetermined"], index=9)
    reason = st.text_input("审核理由")
    if st.button("保存审核", type="primary", disabled=not reason):
        repo.update_document_review(selected["document_id"], relevance, "local-reviewer", reason)
        screen_document(selected["document_id"],"local-reviewer",reason,category)
        st.success("已记录审核和审计日志")
        st.rerun()
    if st.button("生成有原文位置的字段候选", disabled=not selected.get("text_or_summary")):
        count = extract_document(selected["document_id"])
        st.success(f"生成 {count} 个字段候选")
    st.subheader("字段提取候选")
    st.dataframe(repo.rows("SELECT * FROM extraction_candidates WHERE document_id=? ORDER BY span_start", (selected["document_id"],)), width="stretch", hide_index=True, alt="字段提取候选及原文位置")

