import streamlit as st
from funding_radar.repository import LedgerRepository
from funding_radar.review_service import add_evidence, record_review, update_event_fields

st.title("事件审核")
repo = LedgerRepository()
events = repo.list_events()
if not events:
    st.info("暂无真实候选事件。固定测试 fixtures 不会写入开发账本。")
    st.stop()
labels = {f"{e['company_name']} · {e['announcement_date'] or '日期待定'} · {e['event_id'][:8]}": e for e in events}
event = labels[st.selectbox("事件", labels)]
st.json(event)
st.subheader("字段级证据")
st.dataframe(repo.evidence_for_event(event["event_id"]), width="stretch", hide_index=True)
st.caption("未被证据支持的字段必须为空。所有修改通过 Service 写入 audit_logs。")
with st.form("event_edit"):
    round_original = st.text_input("轮次原文", value=event.get("round_original") or "")
    round_normalized = st.text_input("标准轮次", value=event.get("round_normalized") or "")
    amount_original = st.text_input("金额原文", value=event.get("amount_original") or "")
    disclosure = st.selectbox("披露类型", ["exact","bounded_range","lower_bound","upper_bound","order_of_magnitude","undisclosed","cumulative_only"], index=["exact","bounded_range","lower_bound","upper_bound","order_of_magnitude","undisclosed","cumulative_only"].index(event["amount_disclosure_type"]))
    status = st.selectbox("审核状态", ["field_review","approved","needs_correction","held","rejected"], index=0)
    reason = st.text_input("修改理由")
    save = st.form_submit_button("保存事件修改", type="primary")
if save and reason:
    update_event_fields(event["event_id"],{"round_original":round_original or None,"round_normalized":round_normalized or None,"amount_original":amount_original,"amount_disclosure_type":disclosure,"amount_exact":event["amount_exact"] if disclosure=="exact" else None,"review_status":status},"local-reviewer",reason)
    st.success("事件已更新")
    st.rerun()
documents = repo.rows("SELECT d.* FROM raw_documents d JOIN event_documents ed USING(document_id) WHERE ed.event_id=?", (event["event_id"],))
if documents:
    st.subheader("增加字段证据")
    doc = st.selectbox("证据文档", documents, format_func=lambda x:x["title"])
    field = st.text_input("字段名")
    excerpt = st.text_area("原文摘录")
    span = st.number_input("字符起始位置", min_value=0, value=0)
    ev_reason = st.text_input("证据理由")
    if st.button("增加证据", disabled=not(field and excerpt and ev_reason)):
        source_grade = repo.rows("SELECT s.evidence_default_grade grade FROM sources s JOIN raw_documents d USING(source_id) WHERE d.document_id=?",(doc["document_id"],))[0]["grade"]
        add_evidence(doc["document_id"],"funding_event",event["event_id"],field,excerpt,int(span),source_grade,"local-reviewer",ev_reason)
        st.success("证据已追加；历史证据未删除")
st.subheader("双审")
review_round = st.segmented_control("审核轮次", [1,2], default=1)
review_result = st.selectbox("审核结果", ["confirmed","needs_correction","held","rejected"])
review_reason = st.text_input("双审理由")
if st.button("记录本轮审核", disabled=not review_reason):
    record_review("funding_event",event["event_id"],review_round,"reviewer-1" if review_round==1 else "reviewer-2",review_result,{},review_reason)
    st.success("审核轮次已记录")

