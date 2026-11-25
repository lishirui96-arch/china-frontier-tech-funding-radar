from pathlib import Path

import pandas as pd
import streamlit as st

from funding_radar.sample_library import SampleLibraryService

service = SampleLibraryService()
st.title("2026年11月融资与并购明细")
st.caption("月内增量样本，数据截止2026-11-25；未覆盖完整月份，不代表全市场。")

kind = st.segmented_control("交易类别", ["早期融资", "并购"], default="早期融资", key="nov_kind")
if kind == "并购":
    rows = service.acquisitions()
    st.metric("并购候选", len(rows))
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", alt="2026年11月并购候选明细",
        column_config={"source_url": st.column_config.LinkColumn("来源")})
else:
    categories = service.categories()
    category_names = {row["name"]: row["category_id"] for row in categories}
    all_rows = service.funding_events()
    rounds = sorted({row["normalized_round"] for row in all_rows})
    controls = st.container(horizontal=True, vertical_alignment="bottom")
    category = controls.selectbox("一级产业", ["全部", *category_names], key="nov_category")
    round_name = controls.selectbox("融资轮次", ["全部", *rounds], key="nov_round")
    query = controls.text_input("企业名称", key="nov_company")
    rows = service.funding_events(category_id=category_names.get(category, ""), round_name="" if round_name == "全部" else round_name, query=query)
    disclosed = sum(row["normalized_amount_cny"] is not None for row in rows)
    cols = st.columns(3)
    cols[0].metric("融资事件", len(rows)); cols[1].metric("去重企业", len({row["company_name"] for row in rows})); cols[2].metric("标准化金额披露率", f"{disclosed/len(rows):.0%}" if rows else "—")
    display = pd.DataFrame([{ "日期":r["announcement_date"],"企业":r["company_name"],"赛道":r["secondary_track"],"轮次":r["round_original"],"金额":r["amount_original"],"投资方":r["investors"] or "未披露","来源":r["source_url"]} for r in rows])
    st.dataframe(display, hide_index=True, width="stretch", alt="2026年11月早期融资事件明细", column_config={"来源": st.column_config.LinkColumn("来源")})

workbook = Path(__file__).resolve().parents[2] / "docs" / "NOVEMBER_2026_TECH_FINANCING_MA_SAMPLE_LIBRARY_V1.xlsx"
if workbook.exists():
    st.download_button("下载完整Excel", workbook.read_bytes(), file_name=workbook.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:")
