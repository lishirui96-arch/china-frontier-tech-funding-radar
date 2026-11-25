from __future__ import annotations
import csv,sqlite3
from pathlib import Path
from funding_radar.db import database_path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"docs"
def write(name,rows):
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def main():
    db=sqlite3.connect(database_path()); db.row_factory=sqlite3.Row
    recs=[dict(x) for x in db.execute("""SELECT r.*,q.suggested_primary_category,q.suggested_secondary_track,
      q.review_status,s.actual_source_platform,s.primary_url,s.pedaily_source_present,s.spacedaily_source_present,
      s.date_scope_status,s.handling_note FROM v151_batch1_recommendations r
      JOIN v15_funding_review_queue q USING(review_item_id)
      JOIN v151_source_scope_checks s USING(review_item_id)
      ORDER BY r.source_page_date DESC,r.company_name""")]
    scopes=[dict(x) for x in db.execute("""SELECT q.suggested_company_name company_name,q.queue_class,q.batch_number,
      s.actual_source_platform,s.primary_url,s.pedaily_source_present,s.spacedaily_source_present,
      s.source_scope_status,s.disclosure_date,s.date_scope_status,s.handling_note
      FROM v151_source_scope_checks s JOIN v15_funding_review_queue q USING(review_item_id)
      WHERE q.queue_class='A' AND q.batch_number=1 ORDER BY s.disclosure_date DESC,q.suggested_company_name""")]
    write("NOVEMBER_2026_V1_5_1_BATCH1_REVISED_REVIEW_SUMMARY.csv",recs)
    write("NOVEMBER_2026_V1_5_1_BATCH1_SOURCE_SCOPE_CHECK.csv",scopes)
    policy="""# 融资雷达 V1.5.1 研究口径说明

生效日期：2026-11-25。本口径仅影响后续审核和统计资格，不删除或覆盖V1.0至V1.5历史数据。

## 数据来源

当前融资采集来源仅包括投资界（PEdaily）和SpaceDaily融资数据库。其他平台历史链接继续保存并标记实际平台；若没有投资界或SpaceDaily来源，则标记“来源范围外，待处理”，不得计入符合当前来源口径的正式样本。不再考核多平台独立发现或来源交叉覆盖率。

## 时间范围

采集窗口固定为2026-11-01至2026-11-25，以指定来源公开页面日期为准。底层原始报道日期与页面日期不一致时同时保存，并说明统计采用的日期。

## 融资轮次

保留种子、天使、天使+、Pre-A/Pre-A+、A/A+、Pre-B、B/B+以及媒体实际披露的B2、B++等相邻轮次。原始轮次不被强制合并。战略投资或不明确股权阶段单独待判断。历史轮次不计入本轮；同文明确披露两轮时分别记录，但未拆分金额不得推测或平均分配。

## 证据标准

B级可访问媒体正文是基本入库标准。正文须能识别融资企业、融资事实、公开披露日期，并识别轮次或明确标记待核实。不要求企业、投资机构或交易所官方公告，不以官方证据覆盖率评价项目。正文不完整或融资事实无法确认的记录继续待核验。

## 企业名称

只进行简单排查：标题截断、媒体前缀污染、投资方误识别、同一简称重复、明显拼写错误及中英文括号完整性。媒体正文中明确出现的名称可作为标准名称；不强求统一社会信用代码或完整工商核验。

## 投资方角色

分别记录领投、跟投、联合投资、老股东追加、财务顾问和未披露。财务顾问不计入投资机构。

## 并购

保留8条候选。投资界或SpaceDaily正文能够识别交易双方、比例、金额（如有）、首次披露日期和报道所述状态即可进入审核。拟收购、已公告、审议中和已完成必须区分；没有交割证据不得标记已完成。并购不计入融资轮次统计。

## 技术主题

技术归类基于企业主营业务、产品、核心技术、应用场景和产业链位置，不使用来源平台数量衡量主题重要性。本阶段不自动命名最终主题，由用户人工分类和命名。
"""
    (OUT/"NOVEMBER_2026_V1_5_1_RESEARCH_SCOPE.md").write_text(policy,encoding="utf-8")
    print({"revised_summary":len(recs),"source_checks":len(scopes),"out_of_scope_batch1":sum(x['source_scope_status']=='out_of_scope_pending' for x in scopes)})
if __name__=="__main__":main()
