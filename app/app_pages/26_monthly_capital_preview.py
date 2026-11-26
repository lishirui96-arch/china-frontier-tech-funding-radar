import pandas as pd
import streamlit as st

from funding_radar.public_service import PublicDataService


st.title("本月资本流向 · 内部统计预览")
st.caption("只读质量检查。正式统计、历史待确认记录与A/B候选严格分区，候选数据不会进入公开资金流向。")

data = PublicDataService().internal_monthly_quality_preview()

st.subheader("A. 正式统计")
formal = data["formal"]
cols = st.columns(4)
cols[0].metric("人工确认有效事件", formal["confirmed_events"])
cols[1].metric("正式Release交集事件", formal["released_events"])
cols[2].metric("金额可统计事件", formal["amount_disclosed_events"])
cols[3].metric("已归入一级领域", formal["classified_events"])
st.info("公开站只读取人工确认有效事件与正式Release的显式交集。当前不存在该交集，因此公开月度统计为0。")

st.subheader("B. 历史22条事件质量分析")
historical = data["historical"]
cols = st.columns(5)
cols[0].metric("历史待确认记录", historical["total"])
cols[1].metric("明确公告日期", historical["dated"])
cols[2].metric("本轮金额有效", historical["valid_amount"])
cols[3].metric("精确金额", historical["exact_amount"])
cols[4].metric("冻结分类已关联", historical["classified_events"])
st.warning("这些记录仍为candidate / field_review，仅用于数据质量分析，不是正式融资统计。")
left, right = st.columns(2)
with left:
    st.markdown("**币种情况**")
    st.dataframe(pd.DataFrame(historical["currencies"]), hide_index=True, width="stretch")
with right:
    st.markdown("**轮次情况**")
    st.dataframe(pd.DataFrame(historical["rounds"]), hide_index=True, width="stretch")

st.subheader("C. A/B候选观察区")
counts = {row["queue_class"]: row["event_count"] for row in data["candidates"]["counts"]}
left, right = st.columns(2)
left.metric("A类候选", counts.get("A", 0))
right.metric("B类候选", counts.get("B", 0))
st.caption(f"有效候选事件{data['candidates']['effective_events']}条；原始来源记录{data['candidates']['raw_source_records']}条，其中已合并重复来源{data['candidates']['merged_duplicate_sources']}条。以下分类分布不进入公开正式资本流向。")
st.dataframe(pd.DataFrame(data["candidates"]["industries"]), hide_index=True, width="stretch")
