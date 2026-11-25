import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService

service = SampleLibraryService()
st.title("技术关键词库")
st.caption("保留原始表达与标准化关键词；关键词必须关联企业、事件和来源。")
categories = service.categories()
category_names = {row["name"]: row["category_id"] for row in categories}
controls = st.container(horizontal=True, vertical_alignment="bottom")
category = controls.selectbox("一级产业", ["全部", *category_names], key="keyword_category")
query = controls.text_input("搜索关键词", key="keyword_query")
rows = service.keywords(category_id=category_names.get(category, ""), query=query)
st.metric("关键词记录", len(rows))
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", alt="标准化技术关键词及其企业、事件和来源")
