import json
import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService();rows=service.v211_profile_reviews()
st.title("企业技术画像复核")
st.caption("V2.1.1建议层。企业业务、产业链、融资和技术分类分开保存；默认不执行任何人工决定。")
counts={k:sum(x["quality_status"]==k for x in rows) for k in ("accurate","needs_revision","missing_core_business")}
for col,(label,key) in zip(st.columns(4),[("画像总数",None),("已有具体依据","accurate"),("需要修订","needs_revision"),("缺少核心业务","missing_core_business")]): col.metric(label,len(rows) if key is None else counts[key])
profiles_tab,dup_tab,shared_tab,split_tab,action_tab=st.tabs(["123份画像","实体重复","共享企业","8主题拆分","人工复核"])
with profiles_tab:
    quality=st.multiselect("质量状态",list(counts),default=list(counts));filtered=[x for x in rows if x["quality_status"] in quality]
    st.dataframe(pd.DataFrame(filtered),hide_index=True,width="stretch")
with dup_tab: st.dataframe(pd.DataFrame(service.v211_duplicate_checks()),hide_index=True,width="stretch")
with shared_tab:
    shared=service.v211_shared_reviews();st.dataframe(pd.DataFrame(shared),hide_index=True,width="stretch")
    if shared:
        item=st.selectbox("共享企业详情",shared,format_func=lambda x:x["company_name"]);st.json(json.loads(item["topic_basis_json"]))
with split_tab: st.dataframe(pd.DataFrame(service.v211_split_proposals()),hide_index=True,width="stretch")
with action_tab:
    if rows:
        labels={f"{x['suggested_name']} · {x['quality_status']}":x for x in rows};item=labels[st.selectbox("企业画像",list(labels))]
        st.warning("确认或修改只写入V2.1.1建议层，不回写V2.0画像或主题结构。")
        with st.form("profile_review"):
            action=st.segmented_control("审核动作",["confirm","modify","hold"],default="hold")
            business=st.text_area("主营业务",value=item["suggested_business"]);products=st.text_area("核心产品",value=item["suggested_products"]);technologies=st.text_area("核心技术",value=item["suggested_technologies"]);scenarios=st.text_area("应用场景",value=item["suggested_scenarios"]);chain=st.text_area("产业链位置",value=item["suggested_chain"])
            actor=st.text_input("审核人");reason=st.text_area("审核理由")
            if st.form_submit_button("保存复核决定"):
                try: service.review_v211_profile(item["review_id"],action=action,actor=actor,reason=reason,business=business,products=products,technologies=technologies,scenarios=scenarios,chain=chain);st.success("已保存到V2.1.1建议层。");st.rerun()
                except ValueError as exc: st.error(str(exc))
        st.dataframe(pd.DataFrame(service.repo.rows("SELECT * FROM v211_profile_actions ORDER BY occurred_at DESC")),hide_index=True,width="stretch")
