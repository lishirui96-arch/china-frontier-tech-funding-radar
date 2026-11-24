import streamlit as st
from funding_radar.repository import LedgerRepository

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
st.caption("未被证据支持的字段必须为空。状态变更需通过 Service 并写入 audit_logs。")

