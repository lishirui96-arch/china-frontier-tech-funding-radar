import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService

service = SampleLibraryService()
st.title("候选主题人工审核")
st.caption("改名、合并、拆分和企业移动均保留原始分类、动作历史和审计记录。")
themes = service.themes()
if not themes:
    st.info("当前没有候选主题。")
    st.stop()
labels = {f"{row['theme_id']} · {row['final_name'] or row['provisional_description']}": row["theme_id"] for row in themes}
selected_label = st.selectbox("候选主题", labels, key="review_theme")
theme_id = labels[selected_label]
theme = next(row for row in themes if row["theme_id"] == theme_id)
st.table({"暂定描述":theme["provisional_description"],"最终名称":theme["final_name"] or "未命名","锁定":"是" if theme["final_name_locked"] else "否","企业":theme["companies"] or "—","状态":theme["review_status"]}, border="horizontal", width="stretch")

with st.form("theme_decision"):
    action = st.segmented_control("审核动作", ["rename","keep","hold","exclude","restore"], default="keep", key="theme_action")
    final_name = st.text_input("最终主题名称（仅改名时填写）", key="theme_final_name")
    actor = st.text_input("审核人", key="theme_actor")
    reason = st.text_area("审核理由", key="theme_reason")
    if st.form_submit_button("保存审核决定", icon=":material/save:"):
        if not actor.strip() or not reason.strip(): st.error("审核人和审核理由不能为空。")
        else:
            service.review_theme(theme_id, action=action, actor=actor, reason=reason, final_name=final_name)
            st.success("审核决定已保存。"); st.rerun()

with st.form("theme_merge"):
    target_label = st.selectbox("合并到", [label for label, value in labels.items() if value != theme_id], key="merge_target") if len(labels) > 1 else None
    actor_merge = st.text_input("合并审核人", key="merge_actor")
    reason_merge = st.text_area("合并理由", key="merge_reason")
    if st.form_submit_button("合并主题", icon=":material/merge:", disabled=target_label is None):
        if not actor_merge.strip() or not reason_merge.strip(): st.error("审核人和理由不能为空。")
        else:
            service.merge_theme(theme_id, labels[target_label], actor=actor_merge, reason=reason_merge)
            st.success("主题已合并并记录历史。")

members = service.repo.rows("""SELECT m.company_id,m.event_id,c.official_name FROM candidate_theme_members m JOIN companies c USING(company_id) WHERE m.theme_id=? AND m.is_current=1 ORDER BY c.official_name""", (theme_id,))
if members:
    member_labels = {f"{r['official_name']} · {r['event_id']}": r for r in members}
    with st.form("theme_member_action"):
        member_label = st.selectbox("主题成员", member_labels, key="member_choice")
        mode = st.segmented_control("成员操作", ["move","split"], default="move", key="member_mode")
        target_member_label = st.selectbox("移动到", [label for label, value in labels.items() if value != theme_id], key="member_target") if len(labels) > 1 else None
        split_description = st.text_input("拆分后候选描述", key="split_description")
        member_actor = st.text_input("操作人", key="member_actor")
        member_reason = st.text_area("操作理由", key="member_reason")
        if st.form_submit_button("执行成员调整", icon=":material/account_tree:"):
            member = member_labels[member_label]
            if not member_actor.strip() or not member_reason.strip(): st.error("操作人和理由不能为空。")
            elif mode == "move" and target_member_label:
                service.move_company(member["company_id"],member["event_id"],theme_id,labels[target_member_label],actor=member_actor,reason=member_reason); st.success("企业已移动。")
            elif mode == "split":
                service.split_member(member["company_id"],member["event_id"],theme_id,description=split_description,actor=member_actor,reason=member_reason); st.success("已拆分为新候选主题。")
            else: st.error("请选择目标主题。")

st.subheader("修改记录")
st.dataframe(pd.DataFrame(service.theme_actions(theme_id)), hide_index=True, width="stretch", alt="当前候选主题的人工审核动作历史")
