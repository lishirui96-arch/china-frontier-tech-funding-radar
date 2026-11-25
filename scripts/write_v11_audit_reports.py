from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from funding_radar.db import database_path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    con = sqlite3.connect(database_path()); con.row_factory = sqlite3.Row
    coverage = [dict(r) for r in con.execute("""SELECT r.source_name,r.source_column,COUNT(p.page_id) pages_traversed,
        COALESCE(SUM(p.article_count),0) articles_seen,SUM(CASE WHEN p.http_status<>200 THEN 1 ELSE 0 END) inaccessible_pages,
        MIN(p.oldest_date) oldest_date,MAX(p.newest_date) newest_date FROM source_audit_runs r LEFT JOIN source_audit_pages p USING(run_id)
        GROUP BY r.run_id ORDER BY r.source_column""")]
    candidates = [dict(r) for r in con.execute("""SELECT c.*,d.title,d.original_url,a.source_column,a.original_access_status
        FROM v11_funding_candidates c JOIN raw_documents d ON d.document_id=c.source_document_id
        LEFT JOIN source_document_audit a USING(document_id) ORDER BY c.disclosure_date DESC,c.company_name_original""")]
    sources = [dict(r) for r in con.execute("""SELECT d.document_id,s.name source_name,a.source_column,d.title,d.original_url,d.published_at,
        d.fetched_at,a.page_access_status,a.original_access_status,a.evidence_grade,a.corresponding_event_id,a.duplicate_report,a.notes
        FROM source_document_audit a JOIN raw_documents d USING(document_id) JOIN sources s USING(source_id)
        ORDER BY d.published_at DESC,d.title""")]
    acquisitions = [dict(r) for r in con.execute("SELECT acquisition_id,disclosure_date,buyer_name_original,target_name_original,transaction_type,transaction_status,amount_original,evidence_grade,verification_status,review_status FROM acquisition_events ORDER BY disclosure_date DESC")]
    con.close()
    space = json.loads((ROOT / "work" / "spacedaily_v11_audit.json").read_text(encoding="utf-8"))
    pedaily = json.loads((ROOT / "work" / "pedaily_v11_crawl.json").read_text(encoding="utf-8"))
    originals = json.loads((ROOT / "work" / "spacedaily_originals_v11.json").read_text(encoding="utf-8"))
    domains = Counter(urlparse(x["url"]).netloc for x in originals["records"])
    statuses = Counter(x["candidate_status"] for x in candidates)
    rounds = Counter(x["round_normalized"] for x in candidates if x["candidate_status"] == "verified_new")
    write_csv(DOCS / "NOVEMBER_2026_V1_1_SOURCE_DOCUMENTS.csv", sources)
    write_csv(DOCS / "NOVEMBER_2026_V1_1_FUNDING_CANDIDATES.csv", candidates)
    merged_con = sqlite3.connect(database_path()); merged_con.row_factory = sqlite3.Row
    merged = [dict(r) for r in merged_con.execute("SELECT event_id,announcement_date,round_original,amount_original,evidence_grade,review_status FROM funding_events")]
    merged_con.close()
    merged.extend({"event_id":x["candidate_id"],"announcement_date":x["disclosure_date"],"round_original":x["round_original"],"amount_original":x["amount_original"],"evidence_grade":x["evidence_grade"],"review_status":"V1.1新增候选，待人工审核"} for x in candidates if x["candidate_status"]=="verified_new")
    write_csv(DOCS / "NOVEMBER_2026_V1_1_MERGED_SAMPLE.csv", merged)
    coverage_lines = [f"| {x['source_column']} | {x['pages_traversed']} | {x['articles_seen']} | {x['oldest_date'] or '-'} | {x['newest_date'] or '-'} | {x['inaccessible_pages'] or 0} |" for x in coverage]
    domain_lines = [f"| {d} | {n} |" for d,n in domains.most_common()]
    (DOCS / "NOVEMBER_2026_V1_1_SOURCE_COVERAGE_AUDIT.md").write_text(f"""# V1.1 来源覆盖审计报告

审计窗口：2026-11-01 至 2026-11-25。采集日期：2026-11-25。

## 投资界完整分页

robots.txt 明确 `allow:/`。采用低频公开HTML访问；连续两页均早于窗口或页面无文章后停止。窗口内共保存{pedaily['stats']['unique_window_articles']}篇去重来源文档，正文可访问{pedaily['stats']['accessible_articles']}篇。

| 栏目 | 已遍历页数 | 页面文章数合计 | 最早日期 | 最晚日期 | 失败页数 |
|---|---:|---:|---|---|---:|
{chr(10).join(coverage_lines)}

栏目成员数：融资大事件{pedaily['stats']['column_memberships']['funding_major']}、投资事件{pedaily['stats']['column_memberships']['investment_events']}、天使/早期{pedaily['stats']['column_memberships']['angel_early']}、并购{pedaily['stats']['column_memberships']['ma_events']}。同一文章可属于多个栏目，不能直接相加。天使/早期入口最新文章为2026-10-27，因此窗口内为0，不是解析遗漏。

目标科技轮次候选{len(candidates)}条，其中与V1.0重复{statuses['duplicate_v1']}条，新增候选{statuses['verified_new']}条。新增候选尚未经过人工双审，未写入正式融资事件表，也未进入公开站。

## SpaceDaily技术审计

- robots允许公开页面；首页公开HTML直接包含550条记录。
- 2026-11-01至25日记录95条，标记中国84条，目标或待审轮次73条。
- 未发现公开JSON API、公开API文档或公开导出；完整导出/API指向机构版，因此未访问受限功能。
- 73个原始链接中58个正文可访问，15个不可访问或内容不足。
- 已发现企业名截断、海外项目误标中国、日期含义不一、轮次/金额/币种可能错误等问题。全部仅作线索。

## 其他公开来源域名

SpaceDaily公开记录指向的原始来源分布如下；这反映发现渠道，不等于核验通过。

| 来源域名 | 原始URL数 |
|---|---:|
{chr(10).join(domain_lines)}

## 交叉覆盖

SpaceDaily与投资界按原始URL直接重合数量：{sum(1 for x in space['target_records'] if any(c['original_url']==x.get('su') for c in candidates))}。企业名、日期和轮次的模糊重合仍需人工判断，不能仅凭聚合器字段自动合并。
""", encoding="utf-8")
    (DOCS / "NOVEMBER_2026_V1_1_FUNDING_DEDUP_AUDIT.md").write_text(f"""# V1.1 融资事件去重审计

候选总数：{len(candidates)}。V1.0重复：{statuses['duplicate_v1']}。新增候选：{statuses['verified_new']}。

去重依据包括企业名/简称、披露日期（允许三日差）、轮次及原始URL。无法确认的法定名称、实际交割日期、投资方及多轮/多次交割关系保留在 `unresolved_fields`，不自动合并。

新增候选轮次分布：

{chr(10).join(f'- {k}: {v}' for k,v in sorted(rounds.items()))}

本轮没有覆盖V1.0事件、人工审核结果、主题名称或操作历史。{statuses['verified_new']}条新增候选未进入正式事件表，等待内部双审。
""", encoding="utf-8")
    (DOCS / "NOVEMBER_2026_V1_1_MA_VERIFICATION.md").write_text(f"""# V1.1 并购事件专项核验报告

V1.0已有并购候选{len(acquisitions)}条，均保留原记录。本轮投资界并购栏目窗口内发现4篇：骑形网络创始人入主上市公司、德弘资本拟收购金锣、中国生物制药相关交易、CPE源峰收购A.O.史密斯中国业务。

其中食品和家电交易不属于科技产业重点；骑形网络文章需进一步确认交易标的和控制权结构；中国生物制药文章为回顾性叙述，需回到上市公司公告识别具体交易与披露日。由于尚未取得足够交易所/上市公司原始公告证据，本轮新增正式并购事件为0，4篇均保留在来源库或待核验清单，不把媒体标题直接当成完成交易。

现有6条并购候选状态：{', '.join(f"{x['transaction_status']}" for x in acquisitions)}。证据等级均按原数据库保留，未覆盖交易状态和人工审核结果。
""", encoding="utf-8")
    print(json.dumps({"sources":len(sources),"candidates":len(candidates),"new":statuses['verified_new'],"duplicates":statuses['duplicate_v1'],"ma":len(acquisitions)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
