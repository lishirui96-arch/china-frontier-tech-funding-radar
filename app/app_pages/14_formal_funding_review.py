import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); st.title("11月正式融资审核")
st.caption("默认不执行任何操作。只有审核人明确提交“确认纳入”后，事件才进入正式月度样本。")
summary=service.v15_review_summary()
for col,(label,key) in zip(st.columns(4),[("待审核","pending"),("正式纳入","confirmed_events"),("暂缓","held"),("排除","excluded")]): col.metric(label,summary.get(key,0))

tab_a,tab_b,tab_history=st.tabs(["A类分批审核","B类专项审核","操作记录"])
def review_panel(rows,key):
    if not rows: st.info("当前分组没有记录。"); return
    labels={f"{r['suggested_company_name']} | {r['disclosure_date']} | {r['suggested_round']} | {r['review_status']}":r for r in rows}; selected=labels[st.selectbox("选择事件",list(labels),key=key+"_select")]
    st.markdown(f"**原始新闻：** [{selected['source_title']}]({selected['source_url']})")
    st.write({"主营业务":selected["primary_business"],"核心产品":selected["core_products"],"其他来源":selected["cross_sources"] or "无","字段核验":selected["field_verifications"],"问题":selected["quality_issues_json"]})
    with st.form(key+"_form"):
        company=st.text_input("企业名称",selected["suggested_company_name"]); round_name=st.text_input("融资轮次",selected["suggested_round"])
        primary=st.text_input("一级产业",selected["suggested_primary_category"]); secondary=st.text_input("二级赛道",selected["suggested_secondary_track"])
        investors=st.text_area("投资方",selected["suggested_investors"]); notes=st.text_area("人工备注",selected["suggested_notes"])
        actor=st.text_input("审核人"); reason=st.text_area("审核依据")
        decision=st.radio("审核决定",["不操作","确认纳入","暂缓","排除","仅保存字段修改"],index=0,horizontal=True)
        if st.form_submit_button("提交人工审核",type="primary"):
            if decision=="不操作": st.warning("尚未选择审核操作。")
            else:
                mapping={"确认纳入":"confirm","暂缓":"hold","排除":"exclude","仅保存字段修改":"edit"}
                try:
                    service.review_v15_funding(selected["review_item_id"],decision=mapping[decision],actor=actor,reason=reason,company_name=company,round_name=round_name,primary_category=primary,secondary_track=secondary,investors=investors,notes=notes)
                    st.success("人工决定已保存。条目、前后快照和操作历史均已记录。"); st.rerun()
                except ValueError as exc: st.error(str(exc))

with tab_a:
    batch=st.segmented_control("批次",[1,2,3,4],default=1); rows=service.v15_funding_queue("A",batch=batch)
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch",column_config={"source_url":st.column_config.LinkColumn("原文")}); review_panel(rows,"a")
with tab_b:
    all_b=service.v15_funding_queue("B"); groups=sorted({r["issue_group"] for r in all_b}); group=st.selectbox("问题类型",["全部",*groups]); rows=service.v15_funding_queue("B",issue_group="" if group=="全部" else group)
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch",column_config={"source_url":st.column_config.LinkColumn("原文")}); review_panel(rows,"b")
with tab_history: st.dataframe(pd.DataFrame(service.v15_actions()),hide_index=True,width="stretch")
