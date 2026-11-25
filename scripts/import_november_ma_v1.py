from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now

NAMESPACE = uuid.UUID("b7e0d343-5051-4b84-9b39-7a8f3745d2c9")
EVENTS = [
    dict(code="MA-202611-001", date="2026-11-16", title="威派格4.34亿元跨界收购新材料公司", source_name="中国水网", url="https://www.h2o-china.com/news/365606.html", buyer="上海威派格智慧水务股份有限公司", target="福建臻璟新材料科技有限公司", transaction_type="control_acquisition", status="announced", amount="4.34亿元", exact=434_000_000, category="energy_materials", track="热管理氮化物新材料", rationale="取得64.29%股权并拓展电子材料新材料布局", business="热管理氮化物新材料", products="热管理氮化物材料", technology="氮化物热管理材料"),
    dict(code="MA-202611-002", date="2026-11-20", title="拓荆科技25亿元收购案获证监会注册批复，将进一步完善半导体设备业务布局", source_name="中国基金报", url="https://www.chnfund.com/article/ARc68c5ef3-f535-b041-4106-3a250bbb10d6", buyer="拓荆科技股份有限公司", target="无锡尚积半导体科技股份有限公司", transaction_type="control_acquisition", status="in_progress", amount="25亿元", exact=2_500_000_000, category="ai_chips_manufacturing", track="半导体PVD与刻蚀设备", rationale="证监会同意注册；拟实现全资控股并补齐PVD和刻蚀设备产品线", business="PVD设备与干法刻蚀设备", products="6/8/12英寸PVD与刻蚀设备", technology="物理气相沉积与干法刻蚀"),
    dict(code="MA-202611-003", date="2026-11-01", title="301269，出手收购EDA公司！", source_name="证券之星（转载中国基金报）", url="https://wap.stockstar.com/detail/IG2026110100010822", buyer="北京华大九天科技股份有限公司", target="奇捷科技（深圳）有限公司", transaction_type="control_acquisition", status="announced", amount="不超过2.2亿元", exact=None, category="ai_chips_manufacturing", track="EDA工业软件", rationale="拟收购不超过51%股权并补齐数字逻辑优化EDA工具", business="逻辑优化EDA工具", products="数字电路逻辑优化解决方案", technology="数字逻辑优化EDA"),
    dict(code="MA-202611-004", date="2026-11-24", title="翰博高新拟现金收购TCL科技子公司51%股权", source_name="电子工程专辑", url="https://www.eet-china.com/mp/a541548.html", buyer="翰博高新材料（合肥）股份有限公司", target="拓合（珠海）科技有限公司", transaction_type="control_acquisition", status="announced", amount="51%股权对价不超过约2.75亿元", exact=None, category="ai_chips_manufacturing", track="湿电子化学品", rationale="已签框架协议；最终价格待审计评估和补充协议", business="功能性湿电子化学品", products="蚀刻液等湿电子化学品", technology="显示面板蚀刻液"),
    dict(code="MA-202611-005", date="2026-11-13", title="5.6亿元！苏州上市公司，收购浦东半导体零部件企业", source_name="搜狐", url="https://m.sohu.com/a/1100960773_546816/", buyer="荣旗工业科技（苏州）股份有限公司", target="上海德祺顺精密机械设备有限公司", transaction_type="control_acquisition", status="announced", amount="5.616亿元", exact=561_600_000, category="ai_chips_manufacturing", track="半导体设备精密零部件", rationale="拟现金收购60%股权并纳入合并报表", business="半导体设备关键精密零部件", products="抛光头组件、多孔盘、腔体内衬等", technology="工程高分子与金属精密加工"),
    dict(code="MA-202611-006", date="2026-11-06", title="梦网科技拟2.73亿元收购数据智能服务商苏州西园51%股权", source_name="凤凰网", url="https://feng.ifeng.com/c/8xpz4g8NXiv", buyer="梦网云科技集团股份有限公司", target="苏州西园掌讯信息科技有限公司", transaction_type="control_acquisition", status="announced", amount="2.73亿元", exact=273_000_000, category="other_emerging", track="数据智能服务", rationale="拟现金收购51%股权并拓展数据智能和AI通信", business="数据智能解决方案", products="技术+数据+运营一站式解决方案", technology="用户画像、自动标签、隐私计算与数据运营"),
]


def stable(kind: str, value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{value}"))


def main() -> None:
    migrate()
    t = now()
    connection = connect()
    try:
        with connection:
            for item in EVENTS:
                url = item["url"]
                domain = urlsplit(url).netloc.lower()
                source_id = stable("source",domain)
                connection.execute("""INSERT OR IGNORE INTO sources(source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at,is_active,allowed_scope,min_interval_seconds,failure_count)
                  VALUES (?,?,?,?,?,?,?, ?,1,'metadata_and_evidence_excerpt',3600,0)""",(source_id,item["source_name"],"professional_media","media","A",f"https://{domain}","reviewed",t))
                document_id = stable("document",url)
                excerpt = item["rationale"]
                connection.execute("""INSERT OR IGNORE INTO raw_documents(document_id,source_id,original_url,canonical_url,title,published_at,fetched_at,text_or_summary,content_hash,source_family,archive_status,parser_version,relevance_status,review_status,created_at,source_domain,fetch_status,financing_category,event_link_status,imported_at)
                  VALUES (?,?,?,?,?,?,?,?,?,'media','summary_saved','november-ma-v1','relevant','field_review',?,?,'success','merger_acquisition','linked',?)""",
                  (document_id,source_id,url,url,item["title"],item["date"],t,excerpt,stable("hash",excerpt),t,domain,t))
                company_ids = {}
                for role in ("buyer","target"):
                    name = item[role]; company_id = stable("company",name); company_ids[role]=company_id
                    connection.execute("INSERT OR IGNORE INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(company_id,name,name,None,None,None,"legal_entity","needs_review","pending",document_id,t,t))
                acquisition_id = stable("acquisition",item["code"])
                connection.execute("""INSERT OR IGNORE INTO acquisition_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (acquisition_id,item["date"],None,"2026-11",company_ids["buyer"],company_ids["target"],item["buyer"],item["target"],item["transaction_type"],item["status"],item["amount"],"CNY",item["exact"],item["exact"],item["category"],item["track"],item["rationale"],"A","partially_verified","pending",t,t))
                connection.execute("INSERT OR IGNORE INTO acquisition_documents VALUES (?,?,'primary',?)",(acquisition_id,document_id,t))
                profile_id = stable("profile",company_ids["target"])
                connection.execute("""INSERT OR IGNORE INTO company_technology_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (profile_id,company_ids["target"],item["business"],item["products"],item["technology"],"未单独披露",item["track"],"未单独披露",None,item["category"],item["track"],"[]","partially_verified","pending",t,t))
                connection.execute("INSERT OR IGNORE INTO technology_profile_sources VALUES (?,?,?,?,?)",(profile_id,document_id,json.dumps(["primary_business","core_products","core_technologies"],ensure_ascii=False),"partially_verified",t))
    finally:
        connection.close()
    print(json.dumps({"acquisitions":len(EVENTS),"cutoff":"2026-11-25"},ensure_ascii=False))


if __name__ == "__main__": main()
