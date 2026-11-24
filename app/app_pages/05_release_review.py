from datetime import datetime
import streamlit as st
from funding_radar.repository import LedgerRepository
from funding_radar.services import create_release, quality_issues
from funding_radar.review_service import change_release_status

st.title("发布审核")
repo = LedgerRepository()
issues = quality_issues()
approved = repo.rows("SELECT COUNT(*) n FROM funding_events WHERE review_status='approved'")[0]["n"]
st.metric("待发布已批准事件", approved)
if issues:
    st.error("质量门槛未通过")
    for issue in issues:
        st.write(f"- {issue}")
else:
    st.success("全部质量门槛通过")
name = st.text_input("Release 名称", value=datetime.now().strftime("ledger-v1-%Y%m%d"))
if st.button("生成不可变 Release", type="primary", disabled=bool(issues) or not name):
    rid = create_release(name, "local-reviewer")
    st.success(f"已生成 {rid}")
st.subheader("只读 Release")
st.dataframe(repo.releases(), width="stretch", hide_index=True)
releases = repo.releases()
if releases:
    selected_release = st.selectbox("Release 状态管理", releases, format_func=lambda x:x["release_name"])
    new_status = st.segmented_control("新状态", ["withdrawn","superseded"], default="withdrawn")
    status_reason = st.text_input("状态变更理由")
    if st.button("追加状态记录", disabled=not status_reason):
        change_release_status(selected_release["release_id"],new_status,"local-reviewer",status_reason)
        st.success("已追加状态历史；原始 Release 和事件快照未修改")
        st.rerun()
    st.dataframe(repo.rows("SELECT * FROM release_status_history WHERE release_id=? ORDER BY changed_at",(selected_release["release_id"],)), width="stretch", hide_index=True, alt="Release 状态历史")

