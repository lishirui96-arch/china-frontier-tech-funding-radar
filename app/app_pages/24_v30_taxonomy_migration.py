import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService


service = SampleLibraryService()
taxonomy = service.v30_taxonomy()
records = service.v30_migration_records()
pending = [row for row in records if row["needs_manual_review"]]

st.title("V3.0 分类冻结与历史记录迁移")
st.caption("V3.0分类已冻结。修改分类名称只生成版本变更申请；事件分类调整需要审核人和理由。")
if not taxonomy["industries"]:
    st.warning("V3.0冻结数据尚未生成。请先运行增量迁移构建。")
    st.stop()
metrics = [
    ("一级产业", len(taxonomy["industries"])), ("二级领域", len(taxonomy["fields"])),
    ("三级主题", len(taxonomy["topics"])), ("历史记录", len(records)),
    ("已归类", sum(row["primary_topic_id"] is not None for row in records)), ("待复核", len(pending)),
]
for col, (label, value) in zip(st.columns(6), metrics): col.metric(label, value)

tree_tab, migration_tab, review_tab, links_tab, history_tab = st.tabs([
    "冻结分类体系", "97条迁移对照", "待分类审核", "企业与主题关联", "变更历史"
])
with tree_tab:
    industry_names = {row["industry_id"]: row["name"] for row in taxonomy["industries"]}
    selected_industry = st.selectbox("一级产业", taxonomy["industries"], format_func=lambda row: f"{row['code']} {row['name']}")
    field_rows = [row for row in taxonomy["fields"] if row["industry_id"] == selected_industry["industry_id"]]
    st.dataframe(pd.DataFrame(field_rows), hide_index=True, alt="冻结分类中的二级技术领域")
    selected_fields = {row["field_id"] for row in field_rows}
    st.dataframe(pd.DataFrame([row for row in taxonomy["topics"] if row["field_id"] in selected_fields]), hide_index=True,
                 alt="所选一级产业下的三级候选主题")
    st.subheader("分类名称版本变更申请")
    with st.form("v30_change_request"):
        target_type = st.selectbox("层级", ["industry", "field", "topic"])
        sources = {"industry": taxonomy["industries"], "field": taxonomy["fields"], "topic": taxonomy["topics"]}[target_type]
        target = st.selectbox("对象", sources, format_func=lambda row: row["name"])
        proposed = st.text_input("建议名称")
        actor = st.text_input("审核人")
        reason = st.text_area("变更依据")
        if st.form_submit_button("提交版本变更申请"):
            try:
                service.request_v30_taxonomy_change(target_type, target[f"{target_type}_id"], proposed, actor, reason)
                st.success("申请已记录，冻结分类未被修改。")
            except ValueError as exc: st.error(str(exc))
with migration_tab:
    status_filter = st.segmented_control("分类状态", ["全部", "已归类", "待复核"], default="全部")
    shown = records
    if status_filter == "已归类": shown = [row for row in records if row["primary_topic_id"]]
    if status_filter == "待复核": shown = pending
    st.dataframe(pd.DataFrame(shown), hide_index=True, alt="97条历史融资记录迁移对照")
with review_tab:
    candidates = pending or records
    selected = st.selectbox("历史记录", candidates, format_func=lambda row: f"{row['disclosure_date']} · {row['company_name_standard']} · {row['round_original']}")
    st.table({"来源": selected["source_platform"], "原始链接": selected["source_url"], "金额": selected["amount_original"],
              "当前理由": selected["classification_reason"], "状态": selected["classification_status"]}, border="horizontal")
    with st.form("v30_classification_review"):
        primary = st.selectbox("主主题", taxonomy["topics"], format_func=lambda row: f"{row['industry_name']} → {row['field_name']} → {row['name']}")
        secondary = st.multiselect("次级主题", taxonomy["topics"], format_func=lambda row: row["name"])
        decision = st.segmented_control("审核决定", ["classify", "hold", "exclude"], default="classify")
        actor = st.text_input("审核人")
        reason = st.text_area("分类依据")
        if st.form_submit_button("明确提交分类决定"):
            try:
                service.review_v30_classification(selected["record_id"], primary_topic_id=primary["topic_id"],
                    secondary_topic_ids=[row["topic_id"] for row in secondary], decision=decision, actor=actor, reason=reason)
                st.success("分类决定已记录。")
            except ValueError as exc: st.error(str(exc))
with links_tab:
    st.subheader("企业—主题关系")
    st.dataframe(pd.DataFrame(service.repo.rows("""SELECT c.display_name,t.name topic_name,l.link_role,l.product_basis,l.technology_basis,l.review_status
      FROM v22_company_topic_links l JOIN v22_companies c USING(company_id) JOIN v30_topics t ON t.topic_id=l.topic_id AND t.taxonomy_version='V3.0'
      ORDER BY c.display_name,t.name""")), hide_index=True, alt="企业与冻结主题的产品技术关系")
    st.subheader("融资事件—主题关系")
    st.dataframe(pd.DataFrame(service.repo.rows("""SELECT h.company_name_standard,h.unique_event_id,t.name topic_name,rt.link_role,rt.basis,rt.review_status
      FROM v30_record_topics rt JOIN v30_historical_records h USING(record_id) JOIN v30_topics t
      ON t.taxonomy_version=rt.taxonomy_version AND t.topic_id=rt.topic_id ORDER BY h.disclosure_date DESC""")), hide_index=True,
      alt="历史融资事件与冻结主题的关系")
with history_tab:
    st.dataframe(pd.DataFrame(service.v30_actions()), hide_index=True, alt="V3.0分类人工操作历史")
    st.subheader("分类版本变更申请")
    st.dataframe(pd.DataFrame(service.repo.rows("SELECT * FROM v30_taxonomy_change_requests ORDER BY created_at DESC")), hide_index=True,
                 alt="冻结分类的版本变更申请")
