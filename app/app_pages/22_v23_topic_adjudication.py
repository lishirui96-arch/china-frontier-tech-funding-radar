import json
import pandas as pd
import streamlit as st
from funding_radar.sample_library import SampleLibraryService

service=SampleLibraryService();cards=service.v23_review_cards();previews=service.v23_merge_previews();directory=service.v23_formal_directory()
st.title("V2.3 主题人工裁决")
st.caption("正式目录仅接收人工明确提交的主题。本页初始状态不执行任何裁决。")
for col,(label,value) in zip(st.columns(5),[("来源候选",len(cards)),("多企业候选",sum(x["candidate_class"]=="A_multi_company_proposed" for x in cards)),("观察项",sum(x["candidate_class"]=="B_observation" for x in cards)),("待拆分",sum(x["candidate_class"]=="C_needs_further_split" for x in cards)),("正式目录",len(directory))]):col.metric(label,value)
cards_tab,merge_tab,split_tab,directory_tab,action_tab=st.tabs(["完整审核卡","合并预览","观察与拆分","正式主题目录","提交裁决"])
with cards_tab:
    industry=st.selectbox("一级产业",["全部"]+list(dict.fromkeys(x["industry_name"] for x in cards)))
    filtered=[x for x in cards if industry=="全部" or x["industry_name"]==industry]
    labels={f"{x['industry_name']} → {x['field_name']} → {x['candidate_name']}":x for x in filtered}
    if labels:
        item=labels[st.selectbox("主题审核卡",list(labels))]
        st.table({"建议":item["recommendation"],"建议理由":item["recommendation_reason"],"共同技术":item["common_technology"],"独立研究价值":item["independent_value"],"重复情况":item["duplicate_note"],"主题边界":item["technical_boundary"],"企业/事件":f"{item['company_count']}/{item['event_count']}","正式/A/B":f"{item['formal_count']}/{item['a_count']}/{item['b_count']}"})
        st.subheader("关联企业");st.dataframe(pd.DataFrame(json.loads(item["member_details_json"])),hide_index=True,width="stretch")
        st.subheader("融资事件");st.dataframe(pd.DataFrame(json.loads(item["event_details_json"])),hide_index=True,width="stretch")
with merge_tab:
    for preview in previews:
        with st.expander(f"{preview['left_name']} + {preview['right_name']} → {preview['proposed_name']}"):
            st.metric("合并后企业",preview["merged_company_count"]);st.metric("合并后事件",preview["merged_event_count"]);st.json(json.loads(preview["difference_json"]))
            left=json.loads(preview["left_snapshot_json"]);right=json.loads(preview["right_snapshot_json"]);st.write("左侧主题ID：",preview["left_topic_id"]);st.write("右侧主题ID：",preview["right_topic_id"]);st.write("左侧描述：",left["topic"]["technical_boundary"]);st.write("右侧描述：",right["topic"]["technical_boundary"])
with split_tab:
    subset=[x for x in cards if x["candidate_class"]!="A_multi_company_proposed"]
    st.dataframe(pd.DataFrame(subset),hide_index=True,width="stretch")
with directory_tab:
    st.dataframe(pd.DataFrame(directory),hide_index=True,width="stretch");st.info("只有人工确认的A类主题进入正式导航；观察项在独立栏目展示。")
with action_tab:
    if cards:
        choices={f"{x['candidate_name']} · {x['recommendation']}":x for x in cards};item=choices[st.selectbox("来源主题",list(choices))]
        decision=st.selectbox("裁决",["confirm_formal","confirm_observation","hold","exclude","rename_and_confirm","change_field_and_confirm"])
        name=st.text_input("确认后的名称",value=item["candidate_name"])
        fields=service.repo.rows("SELECT f.field_id,i.name||' / '||f.name label FROM v22_fields f JOIN v22_industries i USING(industry_id) ORDER BY i.sort_order,f.sort_order");field_labels={x["label"]:x["field_id"] for x in fields};field_id=field_labels[st.selectbox("确认后的技术领域",list(field_labels),index=next((i for i,x in enumerate(fields) if x["field_id"]==service.repo.rows("SELECT field_id FROM v22_topics WHERE topic_id=?",(item["source_topic_id"],))[0]["field_id"]),0))]
        actor=st.text_input("审核人");reason=st.text_area("审核依据")
        if st.button("明确提交裁决",type="primary"):
            try:service.adjudicate_v23_topic(item["source_topic_id"],decision=decision,actor=actor,reason=reason,formal_name=name,field_id=field_id);st.success("裁决已保存。");st.rerun()
            except ValueError as exc:st.error(str(exc))
        st.dataframe(pd.DataFrame(service.repo.rows("SELECT * FROM v23_adjudications ORDER BY occurred_at DESC")),hide_index=True,width="stretch")
