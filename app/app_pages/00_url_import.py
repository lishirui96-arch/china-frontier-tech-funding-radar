import streamlit as st
from funding_radar.ingestion import ImportItem, import_items, parse_csv_bytes

st.title("URL 导入")
st.caption("导入只登记公开 URL 和允许保存的元数据/摘要，不绕过访问限制。")
mode = st.segmented_control("导入方式", ["单条", "批量", "CSV"], default="单条")
items = []
if mode == "单条":
    with st.form("single_import"):
        url = st.text_input("原始 URL")
        title = st.text_input("标题")
        source = st.text_input("来源名称")
        published = st.text_input("发布日期（ISO 8601，可空）")
        summary = st.text_area("允许保存的摘要（可空）")
        submitted = st.form_submit_button("导入", type="primary", icon=":material/add_link:")
    if submitted:
        items = [ImportItem(url,title,source,published or None,summary)]
elif mode == "批量":
    st.caption("每行格式：URL<TAB>标题<TAB>来源名称<TAB>发布日期（可空）")
    bulk = st.text_area("批量内容", height=240)
    if st.button("解析并导入", type="primary", icon=":material/upload:"):
        for line in bulk.splitlines():
            if line.strip():
                parts = line.split("\t")
                if len(parts) >= 3:
                    items.append(ImportItem(parts[0],parts[1],parts[2],parts[3] if len(parts)>3 and parts[3] else None))
else:
    upload = st.file_uploader("CSV 文件", type=["csv"])
    if upload and st.button("导入 CSV", type="primary", icon=":material/upload_file:"):
        items = parse_csv_bytes(upload.getvalue())
if items:
    result = import_items(items,"local-reviewer",import_type={"单条":"single_url","批量":"bulk_url","CSV":"csv"}[mode])
    st.success(f"新增 {result['inserted']}，重复 {result['duplicates']}，失败 {result['failed']}")
    if result["errors"]:
        st.json(result["errors"])

