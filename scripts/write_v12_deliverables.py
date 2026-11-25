from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from funding_radar.db import database_path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SPACE_JSON = ROOT / "work" / "spacedaily_v11_audit.json"
ORIGINALS_JSON = ROOT / "work" / "spacedaily_originals_v11.json"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else ["status"]
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def norm(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]","",value or "").lower()


def company_key(title: str) -> str:
    value = re.sub(r"^首发\s*[|｜:]\s*","",title or "")
    value = value.split("完成",1)[0].split("获",1)[0]
    value = re.split(r"[！!：:]",value)[-1]
    return norm(value)


def main() -> None:
    con=sqlite3.connect(database_path());con.row_factory=sqlite3.Row
    source_records=[dict(r) for r in con.execute("SELECT * FROM v12_source_records ORDER BY disclosure_date DESC,source_record_id")]
    candidates=[dict(r) for r in con.execute("SELECT * FROM v12_funding_candidates ORDER BY disclosure_date DESC,source_platform,company_name_original")]
    audits=[dict(r) for r in con.execute("SELECT * FROM v12_platform_audits ORDER BY platform")]
    ma=[dict(r) for r in con.execute("SELECT * FROM v12_acquisition_candidates ORDER BY disclosure_date DESC")]
    links=[dict(r) for r in con.execute("SELECT * FROM v12_candidate_source_links ORDER BY source_platform,source_title")]
    v11=[dict(r) for r in con.execute("""SELECT c.*,d.title,d.original_url FROM v11_funding_candidates c JOIN raw_documents d ON d.document_id=c.source_document_id WHERE c.candidate_status='verified_new' ORDER BY c.disclosure_date DESC,c.company_name_original""")]
    formal=[dict(r) for r in con.execute("""SELECT e.event_id,c.official_name company_name,e.announcement_date,e.round_original,e.amount_original,e.evidence_grade,e.review_status FROM funding_events e JOIN companies c USING(company_id) ORDER BY e.announcement_date DESC""")]
    space=json.loads(SPACE_JSON.read_text(encoding="utf-8")); originals=json.loads(ORIGINALS_JSON.read_text(encoding="utf-8"))
    inaccessible={x["url"]:x for x in originals["records"] if not x["accessible"]}

    supplemental=[]
    for record in space["target_records"]:
        if record.get("su") not in inaccessible:
            continue
        title=record.get("st") or ""; key=company_key(title)
        best=None;best_score=0.0
        for link in links:
            if link["source_url"]==record.get("su") or link["access_status"]!="accessible":continue
            score=SequenceMatcher(None,norm(title),norm(link["source_title"])).ratio()
            if key and len(key)>=3 and key in norm(link["source_title"]):score=max(score,0.9)
            if score>best_score:best,best_score=link,score
        reliable=best is not None and best_score>=0.55
        supplemental.append({"spacedaily_id":record["id"],"企业名称":record.get("c"),"轮次":record.get("r"),"原始失败URL":record.get("su"),"访问状态":"正文不足或不可访问","补充来源平台":best["source_platform"] if reliable else "","补充来源标题":best["source_title"] if reliable else "","补充来源URL":best["source_url"] if reliable else "","匹配分数":round(best_score,3),"补充核验状态":"找到可靠替代来源" if reliable else "仍待核验"})

    verification=[]
    for row in v11:
        related=[c for c in candidates if c.get("duplicate_candidate_id")==row["candidate_id"]]
        platforms=sorted({c["source_platform"] for c in related})
        grades=sorted({c["evidence_grade"] for c in related})
        verification.append({"v11_candidate_id":row["candidate_id"],"企业名称":row["company_name_original"],"披露日期":row["disclosure_date"],"轮次":row["round_original"],"金额":row["amount_original"],"投资界URL":row["original_url"],"交叉来源":"、".join(platforms),"交叉来源数量":len(platforms),"最高新增证据等级":min(grades) if grades else "B","核验状态":"多平台交叉核验" if platforms else "仅投资界B级证据","核验边界":row["unresolved_fields"]})

    new_candidates=[x for x in candidates if x["candidate_status"]=="new"]
    merged=[{"record_type":"正式事件",**x} for x in formal]
    merged.extend({"record_type":"V1.1待审候选","event_id":x["candidate_id"],"company_name":x["company_name_original"],"announcement_date":x["disclosure_date"],"round_original":x["round_original"],"amount_original":x["amount_original"],"evidence_grade":x["evidence_grade"],"review_status":"pending"} for x in v11)
    merged.extend({"record_type":"V1.2新增候选","event_id":x["candidate_id"],"company_name":x["company_name_original"],"announcement_date":x["disclosure_date"],"round_original":x["round_original"],"amount_original":x["amount_original"],"evidence_grade":x["evidence_grade"],"review_status":x["verification_status"]} for x in new_candidates)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_SPACEDAILY_95_RECORDS.csv",source_records)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_SPACEDAILY_15_INACCESSIBLE_VERIFICATION.csv",supplemental)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_V11_72_VERIFICATION.csv",verification)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_NEW_FUNDING_CANDIDATES.csv",new_candidates)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_ACQUISITION_CANDIDATES.csv",ma)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_MERGED_FUNDING_SAMPLE.csv",merged)

    platform_stats=[]
    for audit in audits:
        rows=[x for x in candidates if x["source_platform"]==audit["platform"]]
        platform_stats.append({"来源":audit["platform"],"发现线索":audit["clues_found"],"目标轮次候选":len(rows),"去重后新增":sum(x["candidate_status"]=="new" for x in rows),"已核实":sum(x["verification_status"] in {"verified","partially_verified"} for x in rows),"待核验":sum(x["verification_status"]=="pending" for x in rows)})
    space_rows=[x for x in candidates if x["source_platform"]=="SpaceDaily"]
    platform_stats.insert(0,{"来源":"SpaceDaily","发现线索":95,"目标轮次候选":73,"去重后新增":sum(x["candidate_status"]=="new" for x in space_rows),"已核实":sum(x["verification_status"] in {"verified","partially_verified"} for x in space_rows),"待核验":sum(x["verification_status"]=="pending" for x in space_rows)})
    platform_stats.insert(0,{"来源":"投资界（V1.1）","发现线索":155,"目标轮次候选":89,"去重后新增":72,"已核实":sum(x["核验状态"]=="多平台交叉核验" for x in verification),"待核验":sum(x["核验状态"]!="多平台交叉核验" for x in verification)})

    platforms_all=["投资界","SpaceDaily","36氪","IT桔子","清科","投中","财联社","证券时报"]
    platform_totals={"投资界":89,"SpaceDaily":73}
    platform_totals.update({name:sum(c["source_platform"]==name for c in candidates) for name in platforms_all if name not in platform_totals})
    event_platforms=defaultdict(set)
    for c in candidates:
        cluster=c.get("duplicate_candidate_id") or c.get("duplicate_event_id") or c["candidate_id"]
        event_platforms[cluster].add(c["source_platform"])
        if c.get("duplicate_candidate_id"):event_platforms[cluster].add("投资界")
    overlap=[]
    for left in platforms_all:
        row={"来源":left}
        for right in platforms_all:
            row[right]=sum(left in values and right in values for values in event_platforms.values()) if left!=right else platform_totals[left]
        overlap.append(row)
    write_csv(DOCS/"NOVEMBER_2026_V1_2_SOURCE_OVERLAP_MATRIX.csv",overlap)

    audit_lines="\n".join(f"| {x['来源']} | {x['发现线索']} | {x['目标轮次候选']} | {x['去重后新增']} | {x['已核实']} | {x['待核验']} |" for x in platform_stats)
    (DOCS/"NOVEMBER_2026_V1_2_MULTIPLATFORM_COVERAGE_AUDIT.md").write_text(f"""# V1.2 多平台来源覆盖审计

检索窗口：2026-11-01至2026-11-25。所有新增数据仅进入候选库，不进入正式事件或公开Release。

| 来源 | 发现线索 | 目标轮次候选 | 去重后新增 | 已核实 | 待核验 |
|---|---:|---:|---:|---:|---:|
{audit_lines}

## 平台访问边界

36氪、投中、财联社可访问部分公开新闻正文。IT桔子首页返回HTTP 412，未绕过；清科与证券时报首页可访问，但限定日期的公开新闻检索未发现目标事件；清科事件数据库和IT桔子结构化数据若需登录，不作为本轮全量来源。各平台发现数来自限定域名公开检索，未声称为平台全量。

SpaceDaily 95条全部结构化；84条中国标签全部重新给出 `confirmed_china/probable_china/not_china/pending` 市场判断；73条全部进入候选层，其中明确目标轮次57条，其他/战略待审16条。58条可访问原始链接逐条读取；15条正文不足或不可访问中，{sum(x['补充核验状态']=='找到可靠替代来源' for x in supplemental)}条找到可访问替代来源。
""",encoding="utf-8")
    (DOCS/"NOVEMBER_2026_V1_2_SOURCE_OVERLAP_REPORT.md").write_text("# V1.2 来源交叉重合报告\n\n重合按候选关联、企业名称、披露日期、轮次和标题相似度综合建立，不只比较URL。矩阵对角线为各平台目标候选总数，非对角线为平台间匹配的独立事件数。明细矩阵见 `NOVEMBER_2026_V1_2_SOURCE_OVERLAP_MATRIX.csv`。\n\n"+"\n".join(f"- {r['来源']}: "+", ".join(f"{k}={v}" for k,v in r.items() if k!='来源' and v) for r in overlap),encoding="utf-8")
    workbook={"title":"2026年11月中国科技产业融资与并购样本库 V1.2","cutoff":"2026-11-25","sheets":{
        "SpaceDaily 95条":[list(source_records[0]),*[list(x.values()) for x in source_records]],
        "统一融资候选":[list(candidates[0]),*[list(x.values()) for x in candidates]],
        "V1.2新增候选":[list(new_candidates[0]),*[list(x.values()) for x in new_candidates]],
        "V1.1候选核验":[list(verification[0]),*[list(x.values()) for x in verification]],
        "平台覆盖审计":[list(platform_stats[0]),*[list(x.values()) for x in platform_stats]],
        "来源重合矩阵":[list(overlap[0]),*[list(x.values()) for x in overlap]],
        "并购新增候选":[list(ma[0]),*[list(x.values()) for x in ma]],
    }}
    (ROOT/"work"/"v12_workbook_data.json").write_text(json.dumps(workbook,ensure_ascii=False),encoding="utf-8")
    con.close()
    print(json.dumps({"space95":len(source_records),"supplemented":sum(x['补充核验状态']=='找到可靠替代来源' for x in supplemental),"v11_verified":sum(x['核验状态']=='多平台交叉核验' for x in verification),"new_candidates":len(new_candidates),"ma":len(ma)},ensure_ascii=False))


if __name__=="__main__":main()
