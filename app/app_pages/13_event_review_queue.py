import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService()
st.title("V1.4 融资事件审核队列")
st.caption("A/B/C为样本资格，不是证据等级。自动预裁决不会覆盖人工决定，也不会写入正式融资事件表。")
summary=service.v14_summary()
for col,(label,key) in zip(st.columns(5),[("可统计准备","A_statistical"),("待核验","B_pending"),("不重复计数/排除","C_excluded"),("建议拆分","split_recommended"),("建议合并来源","merge_sources")]): col.metric(label,summary.get(key,0))

eligibility=st.selectbox("样本资格",["全部","A_statistical","B_pending","C_excluded"])
rows=service.v14_review_queue("" if eligibility=="全部" else eligibility)
display=pd.DataFrame([{"event_unit_id":r["event_unit_id"],"披露日期":r["disclosure_date"],"企业":r["adjudicated_company_name"],"原始企业名":r["original_company_name"],"轮次":r["adjudicated_round"],"原始轮次":r["original_round"],"金额":r["amount_original"],"投资方":r["investors_original"],"样本资格":r["sample_eligibility_status"],"事件结构":r["event_structure_status"],"轮次裁决":r["adjudication_type"],"重复关系":r["duplicate_relations"],"证据等级":r["evidence_grade"],"理由":r["eligibility_reason"],"原文":r["source_url"]} for r in rows])
st.dataframe(display,hide_index=True,width="stretch",column_config={"原文":st.column_config.LinkColumn("原文")})

if rows:
    labels={f"{r['adjudicated_company_name']} | {r['disclosure_date']} | {r['adjudicated_round']} | {r['event_unit_id'][:8]}":r for r in rows}
    selected=labels[st.selectbox("选择待审事件",list(labels))]
    with st.form("v14_review"):
        actor=st.text_input("审核人")
        action=st.selectbox("审核操作",["confirm_company","rename_company","confirm_round","split_event","merge_duplicate","mark_statistical","hold","exclude"])
        value=st.text_input("修订值",help="修改标准化名称或确认轮次时填写")
        reason=st.text_area("裁决依据")
        if st.form_submit_button("提交审核决定",type="primary"):
            try:
                service.review_v14_event(selected["event_unit_id"],action=action,actor=actor,reason=reason,value=value)
                st.success("审核决定已保存，并写入审计日志。")
                st.rerun()
            except ValueError as exc: st.error(str(exc))
