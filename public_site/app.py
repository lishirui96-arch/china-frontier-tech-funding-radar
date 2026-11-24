from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from funding_radar.public_service import PublicDataService


ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
service = PublicDataService()

FIELDS = (
    ("chemical-engineering", "化学工程", "Chemical Engineering", "过程强化、反应工程与规模化制造"),
    ("chemistry", "化学", "Chemistry", "分子设计、合成方法与功能化学"),
    ("computer-science", "计算机科学", "Computer Science", "人工智能、计算系统与软件基础设施"),
    ("energy", "能源", "Energy", "新型储能、清洁能源与能源系统"),
    ("engineering", "工程", "Engineering", "机器人、先进制造与工程系统"),
    ("materials-science", "材料科学", "Materials Science", "先进材料、器件材料与制造工艺"),
)


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def empty_state(title: str, detail: str) -> str:
    return f'<div class="empty"><i data-lucide="database-zap"></i><h3>{esc(title)}</h3><p>{esc(detail)}</p></div>'


def nav(active: str, query: str = "") -> str:
    links = (("首页","/"),("六大学科","/fields"),("融资赛道","/tracks"),("新兴方向","/emerging"),("企业库","/companies"),("投资机构","/investors"),("数据说明","/methodology"))
    items = "".join(f'<a class="{"active" if href==active else ""}" href="{href}">{label}</a>' for label,href in links)
    return f'''<header class="topbar"><a class="brand" href="/"><span class="brand-mark">融</span><span><b>中国前沿科技融资热点雷达</b><small>China Frontier Tech Funding Radar</small></span></a><nav>{items}</nav><form class="search" action="/search"><i data-lucide="search"></i><input name="q" value="{esc(query)}" placeholder="搜索企业、技术、赛道或机构" aria-label="全站搜索"></form><button class="menu" aria-label="打开导航" onclick="document.body.classList.toggle('nav-open')"><i data-lucide="menu"></i></button></header>'''


def page(title: str, body: str, active: str = "", query: str = "") -> HTMLResponse:
    return HTMLResponse(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="中国前沿科技融资热点研究平台"><link rel="icon" href="/favicon.ico"><title>{esc(title)} · 中国前沿科技融资热点雷达</title><link rel="stylesheet" href="/static/site.css"><script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script></head><body>{nav(active,query)}<main>{body}</main><footer><div><b>中国前沿科技融资热点雷达</b><p>公开端仅展示经过双审并进入有效 Release 的唯一融资事件。</p></div><a href="/methodology">数据口径与证据规则</a></footer><script>if(window.lucide)lucide.createIcons();</script></body></html>''')


def metric(label: str, icon: str, value: str | None) -> str:
    shown = esc(value) if value is not None else '<span class="pending">暂无已发布数据</span>'
    return f'<article class="metric"><i data-lucide="{icon}"></i><div><span>{label}</span><strong>{shown}</strong></div></article>'


async def home(request: Request) -> HTMLResponse:
    period = 360 if request.query_params.get("period") == "360" else 90
    data = service.overview(period)
    release = data["release"]
    metrics = data["metrics"]
    release_label = release.release_name if release else "尚无有效 Release"
    updated = release.created_at[:10] if release else "首批样本审核中"
    cards = "".join((
        metric("融资事件数","landmark",str(metrics["events"]) if metrics else None),
        metric("精确披露融资金额","circle-dollar-sign",f'¥{metrics["exact_amount"]:,}' if metrics else None),
        metric("融资企业数量","building-2",str(metrics["companies"]) if metrics else None),
        metric("活跃投资机构数量","briefcase-business",str(metrics["investors"]) if metrics else None),
    ))
    fields = "".join(f'<a class="field-card" href="/fields/{fid}"><i data-lucide="{icon}"></i><span class="field-en">{en}</span><h3>{zh}</h3><p>{desc}</p><span class="field-count">暂无已发布数据</span></a>' for (fid,zh,en,desc),icon in zip(FIELDS,("flask-conical","atom","cpu","battery-charging","bot","layers-3")))
    body = f'''<section class="hero"><div class="hero-overlay"></div><div class="hero-content"><span class="eyebrow">CAPITAL SIGNALS · VERIFIED EVIDENCE</span><h1>资本正在流向哪些科技方向？</h1><p>追踪中国科技企业融资动态，发现新兴技术赛道，连接科研热点与产业资本。</p><div class="periods"><a class="{'selected' if period==90 else ''}" href="/?period=90">90天趋势</a><a class="{'selected' if period==360 else ''}" href="/?period=360">360天趋势</a></div><dl><div><dt>统计窗口</dt><dd>近 {period} 天</dd></div><div><dt>数据范围</dt><dd>中国科技企业一级市场股权融资</dd></div><div><dt>最近更新</dt><dd>{esc(updated)}</dd></div><div><dt>Release</dt><dd>{esc(release_label)}</dd></div></dl></div></section>
    <div class="page-shell"><section class="metrics">{cards}</section>{'<p class="notice"><i data-lucide="shield-check"></i> 数据审核与首批样本验证进行中。公开端不会展示候选、待审或已撤回数据。</p>' if not release else ''}
    <section class="analysis-grid"><article class="panel chart-panel"><div class="section-head"><div><span class="kicker">CAPITAL FLOW</span><h2>融资趋势</h2></div><div class="segmented"><button class="active">融资事件数量</button><button>披露融资金额</button></div></div>{empty_state('暂无趋势数据','只有精确披露金额进入金额趋势，区间中点和累计融资不会计入。')}</article><article class="panel"><div class="section-head"><div><span class="kicker">TRACKS</span><h2>热门融资赛道 TOP 10</h2></div><a href="/tracks">查看全部</a></div>{empty_state('首批融资样本审核完成后开放','排名仅基于有效 Release 中的唯一事件动态计算。')}</article></section>
    <section><div class="section-head"><div><span class="kicker">SIX RESEARCH FIELDS</span><h2>六大学科导航</h2></div><a href="/fields">浏览学科</a></div><div class="field-grid">{fields}</div></section>
    <section class="split-section"><article><div class="section-head"><div><span class="kicker">EMERGING SIGNALS</span><h2>新兴方向</h2></div><a href="/emerging">进入发现区</a></div>{empty_state('候选方向尚未开放','等待阶段 2 动态术语与主题结果，当前不生成虚构赛道。')}</article><article><div class="section-head"><div><span class="kicker">LATEST EVENTS</span><h2>最新融资动态</h2></div><a href="/events">全部事件</a></div>{empty_state('暂无已发布融资事件','事件完成证据核验、去重和双审后才会在此出现。')}</article></section></div>'''
    return page("首页",body,"/")


def listing(title: str, kicker: str, intro: str, empty_title: str, active: str) -> HTMLResponse:
    return page(title,f'<div class="page-shell subpage"><span class="kicker">{kicker}</span><h1>{title}</h1><p class="lede">{intro}</p><section class="panel">{empty_state(empty_title,"首批融资样本审核完成并形成有效 Release 后展示。")}</section></div>',active)


async def fields(request: Request):
    cards="".join(f'<a class="field-card" href="/fields/{fid}"><span class="field-en">{en}</span><h3>{zh}</h3><p>{desc}</p></a>' for fid,zh,en,desc in FIELDS)
    return page("六大学科",f'<div class="page-shell subpage"><span class="kicker">SIX RESEARCH FIELDS</span><h1>六大学科</h1><p class="lede">分类用于浏览与长期比较，不限制融资事件发现。</p><div class="field-grid">{cards}</div></div>',"/fields")


async def field_detail(request: Request):
    item=next((x for x in FIELDS if x[0]==request.path_params["field_id"]),None)
    title=item[1] if item else "未知学科"
    return page(title,f'<div class="page-shell subpage"><a class="back" href="/fields">← 返回六大学科</a><span class="kicker">FIELD DETAIL</span><h1>{esc(title)}</h1><p class="lede">{esc(item[3] if item else "未找到该学科配置")}</p><section class="panel">{empty_state("暂无已发布融资事件","该学科是浏览入口，不是融资发现边界。")}</section></div>',"/fields")


async def tracks(request: Request): return listing("融资赛道","FUNDING TRACKS","按已发布唯一事件观察资本进入的技术赛道。","暂无融资赛道数据","/tracks")
async def track_detail(request: Request): return listing("赛道详情","TRACK DETAIL","赛道指标将在真实主题数据发布后展示。","该赛道尚无已发布数据","/tracks")
async def emerging(request: Request): return listing("新兴方向","EMERGING SIGNALS","保留无法归入稳定分类的资本信号；本轮仅提供页面框架。","暂无经审核的新兴方向","/emerging")
async def companies(request: Request): return listing("企业库","COMPANY DIRECTORY","仅展示有效 Release 中出现的已确认企业主体。","暂无已发布企业","/companies")
async def company_detail(request: Request):
    company=service.company(request.path_params["company_id"])
    return listing(company["name"] if company else "企业详情","COMPANY DETAIL","企业产品、技术方向和融资时间线。","暂无可公开企业数据","/companies")
async def investors(request: Request): return listing("投资机构","INVESTOR DIRECTORY","仅统计有效 Release 中去重后的投资机构。","暂无已发布投资机构","/investors")
async def investor_detail(request: Request): return listing("投资机构详情","INVESTOR DETAIL","投资事件和技术方向将在证据确认后展示。","暂无可公开机构数据","/investors")
async def events(request: Request): return listing("融资事件","VERIFIED EVENTS","文档数与唯一融资事件数严格分离。","暂无已发布融资事件","/events")
async def event_detail(request: Request):
    event=service.event(request.path_params["event_id"])
    return listing(event.get("company_name") if event else "融资事件详情","EVENT DETAIL","金额原文、轮次、投资方与主要证据来源。","该事件不在当前有效 Release 中","/events")


async def methodology(request: Request):
    data=service.overview()
    release=data["release"].release_name if data["release"] else "尚无有效 Release"
    sections=(("数据范围","中国科技企业一级市场股权融资；并购、IPO、定增、债券、授信、补贴和科研资助不混入统计。"),("融资事件定义","同一笔融资的多篇报道合并为一个唯一事件，原始文档仍全部保留。"),("去重方法","综合企业、日期、轮次、金额、投资机构、文本和引用链；明确不同轮次为强冲突。"),("金额规则","只有精确披露且非累计金额进入精确金额合计；区间金额不取中点。"),("证据等级","S 为法定/监管文件，A 为企业或投资机构官方，B 为政府/高校/可信专业媒体，C 为行业媒体，D 仅作线索。"),("审核流程","文档初筛、主体确认、字段证据、事件去重、两轮独立审核、质量门槛、不可变 Release。"),("统计窗口","首页支持 90 天与 360 天；所有页面在一次请求中使用同一有效 Release。"),("更新频率","当前处于首批样本验证期；仅在审核完成并发布新 Release 后更新。"))
    cards="".join(f'<article class="method-card"><h2>{t}</h2><p>{d}</p></article>' for t,d in sections)
    return page("数据说明",f'<div class="page-shell subpage"><span class="kicker">METHODOLOGY</span><h1>数据说明</h1><p class="lede">当前 Release：{esc(release)}</p><div class="method-grid">{cards}</div></div>',"/methodology")


async def search(request: Request):
    q=request.query_params.get("q","")
    results=service.search(q)
    content="".join(f'<a class="result" href="{esc(r["url"])}"><span>{esc(r["type"])}</span><b>{esc(r["title"])}</b></a>' for r in results) if results else empty_state("没有公开搜索结果","搜索只覆盖当前有效 Release，不检索待审或候选数据。")
    return page("搜索",f'<div class="page-shell subpage"><span class="kicker">SEARCH</span><h1>搜索：{esc(q)}</h1><section class="panel">{content}</section></div>',query=q)


async def favicon(request: Request):
    return Response(status_code=204)


routes=[Route("/",home),Route("/favicon.ico",favicon),Route("/fields",fields),Route("/fields/{field_id}",field_detail),Route("/tracks",tracks),Route("/tracks/{topic_id}",track_detail),Route("/emerging",emerging),Route("/companies",companies),Route("/companies/{company_id}",company_detail),Route("/investors",investors),Route("/investors/{investor_id}",investor_detail),Route("/events",events),Route("/events/{event_id}",event_detail),Route("/methodology",methodology),Route("/search",search)]
app=Starlette(debug=False,routes=routes)
app.mount("/static",StaticFiles(directory=STATIC),name="static")
