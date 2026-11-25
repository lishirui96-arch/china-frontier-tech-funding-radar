import json
import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); st.title("并购人工审核")
st.caption("并购与融资分开审核。公告、董事会审议、股东大会、监管审批和完成交割是不同状态。")
rows=service.v15_acquisition_queue(); st.metric("并购候选",len(rows)); st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
if rows:
    labels={f"{r['buyer_name']} → {r['target_name']} | {r['first_announcement_date']}":r for r in rows}; selected=labels[st.selectbox("选择交易",list(labels))]
    st.json(json.loads(selected["original_snapshot_json"]))
    with st.form("ma_review"):
        status=st.selectbox("确认交易状态",["proposed","announced","board_approved","shareholder_approved","regulatory_review","regulatory_approved","closing_in_progress","completed","unclear"])
        notes=st.text_area("人工备注"); actor=st.text_input("审核人"); reason=st.text_area("审核依据")
        decision=st.radio("审核决定",["不操作","确认状态","暂缓","排除","仅保存修改"],index=0,horizontal=True)
        if st.form_submit_button("提交并购审核",type="primary"):
            if decision=="不操作": st.warning("尚未选择审核操作。")
            else:
                mapping={"确认状态":"confirm_status","暂缓":"hold","排除":"exclude","仅保存修改":"edit"}
                try: service.review_v15_acquisition(selected["review_item_id"],decision=mapping[decision],transaction_status=status,actor=actor,reason=reason,notes=notes); st.success("并购审核决定已保存。"); st.rerun()
                except ValueError as exc: st.error(str(exc))
