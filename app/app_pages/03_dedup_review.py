import json
import streamlit as st
from funding_radar.repository import LedgerRepository
from funding_radar.services import decide_dedup

st.title("去重审核")
repo = LedgerRepository()
items = repo.list_dedup_candidates()
if not items:
    st.info("暂无重复候选")
    st.stop()
labels = {f"{x['left_company']} ↔ {x['right_company']} · {x['risk_level']} · {x['total_score']:.2f}": x for x in items}
item = labels[st.selectbox("候选对", labels)]
left, right = st.columns(2)
left.json({"企业": item["left_company"], "日期": item["left_date"], "轮次": item["left_round"], "金额": item["left_amount"]})
right.json({"企业": item["right_company"], "日期": item["right_date"], "轮次": item["right_round"], "金额": item["right_amount"]})
st.json({k: item[k] for k in ["company_score","date_score","round_score","amount_score","investor_score","text_score","citation_score","total_score","strong_conflicts_json"]})
decision = st.selectbox("决定", ["pending", "merge", "do_not_merge", "supplemental_disclosure"])
reason = st.text_input("决定理由")
if st.button("保存决定", type="primary", disabled=not reason):
    decide_dedup(item["candidate_id"], decision, reason, "local-reviewer", item["rule_version_id"])
    st.success("决定已保存；再次决定会保留反向链，可撤销恢复。")
    st.rerun()

