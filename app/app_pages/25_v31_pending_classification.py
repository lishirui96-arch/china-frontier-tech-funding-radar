from __future__ import annotations

import pandas as pd
import streamlit as st

from funding_radar.repository import LedgerRepository


st.title("21条待分类记录来源复核")
st.caption("来源正文复核形成的V3.1建议层；不修改V3.0冻结分类和正式Release。")

repo = LedgerRepository()
rows = repo.rows(
    """SELECT company_name AS 企业, business_summary AS 主营业务, product_summary AS 核心产品,
              technology_summary AS 核心技术, proposed_industry_name AS 一级分类,
              proposed_field_name AS 二级分类, proposed_topic_name AS 三级分类,
              taxonomy_fit AS 目录处理, classification_confidence AS 置信度,
              classification_basis AS 分类依据, source_url AS 来源
       FROM v31_pending_classification_reviews ORDER BY company_name"""
)

counts = {row["taxonomy_fit"]: row["n"] for row in repo.rows(
    "SELECT taxonomy_fit, COUNT(*) AS n FROM v31_pending_classification_reviews GROUP BY taxonomy_fit"
)}
c1, c2, c3, c4 = st.columns(4)
c1.metric("可用现有目录", counts.get("existing", 0))
c2.metric("建议新增二级", counts.get("new_field", 0))
c3.metric("建议新增三级", counts.get("new_topic", 0))
c4.metric("证据不足", counts.get("pending", 0))

st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.subheader("二级分类增量建议")
extensions = repo.rows(
    """SELECT parent_industry_name AS 一级分类, proposed_field_name AS 建议新增二级分类,
              supporting_companies_json AS 支持企业, proposal_reason AS 理由,
              review_status AS 状态
       FROM v31_taxonomy_extension_proposals ORDER BY parent_industry_name, proposed_field_name"""
)
st.dataframe(pd.DataFrame(extensions), hide_index=True, use_container_width=True)
