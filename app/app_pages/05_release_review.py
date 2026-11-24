from datetime import datetime
import streamlit as st
from funding_radar.repository import LedgerRepository
from funding_radar.services import create_release, quality_issues

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

