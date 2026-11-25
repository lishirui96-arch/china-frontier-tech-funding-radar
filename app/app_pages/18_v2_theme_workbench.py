import json
import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService(); summary=service.v2_theme_summary(); topics=service.v2_topics(); audits=service.v21_topic_audits()
st.title("科技融资主题质量审核")
st.caption("V2.1只提供审核卡和调整建议。默认不执行主题定稿、合并、拆分或成员移动。")
for col,(label,value) in zip(st.columns(6),[("产业方向",summary["industry_count"]),("技术领域",summary["field_count"]),("候选主题",summary["topic_count"]),("单企业观察",summary["observation_count"]),("待补充画像",21),("其他方向画像",39)]): col.metric(label,value)

detail_tab,overlap_tab,taxonomy_tab,triage_tab,action_tab=st.tabs(["22个主题审核卡","主题重叠","三级分类建议","待处理画像","人工操作"])
with detail_tab:
    labels={f"{r['candidate_name']} · {r['recommendation']}":r for r in audits}
    if labels:
        selected=labels[st.selectbox("选择主题",list(labels))]
        st.subheader(selected["candidate_name"])
        cols=st.columns(5)
        for col,(label,key) in zip(cols,[("企业","company_count"),("事件","event_count"),("正式","formal_count"),("A类","a_count"),("B类","b_count")]): col.metric(label,selected[key])
        st.table({"一级产业":selected["industry_name"],"二级领域":selected["field_name"],"审核建议":selected["recommendation"],"建议名称":selected["suggested_name"] or "保持当前候选名","建议产业":selected["suggested_industry"] or "保持当前归属","建议领域":selected["suggested_field"] or "保持当前归属","修改理由":selected["recommendation_reason"]})
        st.dataframe(pd.DataFrame(json.loads(selected["member_review_json"])),hide_index=True,width="stretch")
        problems=json.loads(selected["problems_json"]);st.warning("；".join(problems) if problems else "未发现需要立即处理的数据质量问题。")
        events=service.repo.rows("SELECT * FROM v2_event_topic_links WHERE topic_id=? ORDER BY disclosure_date DESC",(selected["topic_id"],));st.dataframe(pd.DataFrame(events),hide_index=True,width="stretch")
with overlap_tab:
    overlaps=service.v21_overlap_matrix();shared=[x for x in overlaps if x["shared_company_count"]]
    st.metric("共享企业的主题对",len(shared));st.caption("矩阵基于企业成员交集；无共享企业不代表技术边界一定独立。")
    st.dataframe(pd.DataFrame(shared if shared else overlaps),hide_index=True,width="stretch")
with taxonomy_tab:
    st.info("以下均为待审建议，不会修改V2.0的8个一级产业和26个二级领域。")
    st.dataframe(pd.DataFrame(service.v21_taxonomy()),hide_index=True,width="stretch")
with triage_tab:
    group=st.segmented_control("画像口径",["全部去重","21份待补充","39份其他方向"],default="全部去重")
    key={"全部去重":"","21份待补充":"pending","39份其他方向":"other"}[group];rows=service.v21_profile_triage(key)
    st.caption("两组重叠7份，合并去重后53份。现有证据不足时保留暂时无法判断。")
    st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
with action_tab:
    st.warning("以下操作会改变V2主题工作层，但不会改变原始事件或人工融资审核结果。操作后保留完整历史。")
    topic_labels={r["candidate_name"]:r["topic_id"] for r in topics}
    if topic_labels:
        topic_name=st.selectbox("主题",list(topic_labels),key="v21_action_topic");topic_id=topic_labels[topic_name]
        action=st.selectbox("动作",["confirm","rename","hold","exclude","restore","change_industry","merge","move_company","split_company","add_tag"])
        target_name=st.selectbox("目标主题",["—"]+[x for x in topic_labels if x!=topic_name]);target_id=topic_labels.get(target_name,"")
        members=service.repo.rows("SELECT p.profile_id,p.company_name FROM v2_company_topic_links l JOIN v2_company_profiles p USING(profile_id) WHERE l.topic_id=? AND l.is_current=1 ORDER BY p.company_name",(topic_id,))
        member_labels={x["company_name"]:x["profile_id"] for x in members};member_name=st.selectbox("企业",["—"]+list(member_labels));profile_id=member_labels.get(member_name,"")
        fields=service.repo.rows("SELECT f.field_id,i.name||' / '||f.name label FROM v2_technology_fields f JOIN v2_industry_directions i USING(industry_id) ORDER BY i.sort_order,f.name");field_labels={x["label"]:x["field_id"] for x in fields}
        value=st.text_input("新名称或技术标签")
        if action=="change_industry": value=field_labels[st.selectbox("目标产业/领域",list(field_labels))]
        actor=st.text_input("审核人");reason=st.text_area("审核理由")
        if st.button("执行人工操作",type="primary"):
            try: service.review_v2_topic(topic_id,action=action,actor=actor,reason=reason,value=value,target_topic_id=target_id,profile_id=profile_id);st.success("操作已记录。");st.rerun()
            except ValueError as exc: st.error(str(exc))
        st.dataframe(pd.DataFrame(service.repo.rows("SELECT * FROM v2_topic_actions ORDER BY occurred_at DESC")),hide_index=True,width="stretch")
