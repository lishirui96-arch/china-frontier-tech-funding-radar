import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService();topics=service.v22_taxonomy_tree();companies=service.v22_company_classifications()
st.title("V2.2 三级产业技术分类管理")
st.caption("10个一级导航已按用户确认方案固定。三级主题仍为候选，人工确认前不进入8511正式导航。")
for col,(label,value) in zip(st.columns(5),[("一级产业",10),("二级领域",38),("来源候选主题",len(topics)),("已提出主分类",sum(x["classification_status"]=="classified_proposed" for x in companies)),("未分类",sum(x["classification_status"]=="unclassified" for x in companies))]):col.metric(label,value)
tree_tab,company_tab,relation_tab,action_tab=st.tabs(["产业→领域→主题","企业归属","重复与冲突","人工操作"])
with tree_tab:
    industry=st.selectbox("一级产业",["全部"]+list(dict.fromkeys(x["industry_name"] for x in topics)))
    rows=[x for x in topics if industry=="全部" or x["industry_name"]==industry]
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
    for row in rows:
        with st.expander(f"{row['industry_name']} → {row['field_name']} → {row['candidate_name']}"):
            st.write(row["technical_boundary"]);st.write("企业：",row["companies"] or "—");st.write("关键词：",row["tags"] or "—")
            st.table({"状态":row["management_status"],"企业数":row["company_count"],"事件数":row["event_count"],"正式/A/B":f"{row['formal_count']}/{row['a_count']}/{row['b_count']}"})
with company_tab: st.dataframe(pd.DataFrame(companies),hide_index=True,width="stretch")
with relation_tab: st.dataframe(pd.DataFrame(service.v22_topic_relations()),hide_index=True,width="stretch")
with action_tab:
    if topics:
        topic_labels={f"{x['candidate_name']} · {x['management_status']}":x for x in topics};item=topic_labels[st.selectbox("主题",list(topic_labels))]
        action=st.selectbox("动作",["confirm_multi","confirm_observation","hold_split","exclude","rename","change_field","merge_suggestion","split_suggestion","move_company","add_tag"])
        value=st.text_input("新名称、辅助标签或目标主题ID")
        fields=service.repo.rows("SELECT f.field_id,i.name||' / '||f.name label FROM v22_fields f JOIN v22_industries i USING(industry_id) ORDER BY i.sort_order,f.sort_order")
        if action=="change_field": value={x["label"]:x["field_id"] for x in fields}[st.selectbox("目标领域",[x["label"] for x in fields])]
        members=service.repo.rows("SELECT c.company_id,c.display_name FROM v22_company_topic_links l JOIN v22_companies c USING(company_id) WHERE l.topic_id=? ORDER BY c.display_name",(item["topic_id"],));member_labels={x["display_name"]:x["company_id"] for x in members};member=st.selectbox("企业",["—"]+list(member_labels));company_id=member_labels.get(member,"")
        if action=="move_company":
            targets={x["candidate_name"]:x["topic_id"] for x in topics if x["topic_id"]!=item["topic_id"]};value=targets[st.selectbox("目标主题",list(targets))]
        actor=st.text_input("审核人");reason=st.text_area("审核依据")
        if st.button("执行人工操作",type="primary"):
            try:service.review_v22_topic(item["topic_id"],action=action,actor=actor,reason=reason,value=value,company_id=company_id);st.success("操作已记录。");st.rerun()
            except ValueError as exc:st.error(str(exc))
        st.dataframe(pd.DataFrame(service.repo.rows("SELECT * FROM v22_topic_history ORDER BY occurred_at DESC")),hide_index=True,width="stretch")
