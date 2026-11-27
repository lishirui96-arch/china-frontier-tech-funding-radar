from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from funding_radar.public_service import PublicDataService, PublicFilters, candidate_round_bucket, rolling_window


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
    links = (("首页","/"),("产业技术分类","/taxonomy"),("融资事件","/events"),("企业库","/companies"),("数据说明","/methodology"))
    items = "".join(f'<a class="{"active" if href==active else ""}" href="{href}">{label}</a>' for label,href in links)
    return f'''<header class="topbar"><a class="brand" href="/"><span class="brand-mark">融</span><span><b>中国前沿科技融资热点雷达</b><small>China Frontier Tech Funding Radar</small></span></a><nav>{items}</nav><form class="search" action="/search"><i data-lucide="search"></i><input name="q" value="{esc(query)}" placeholder="搜索企业、技术、赛道或机构" aria-label="全站搜索"></form><button class="menu" aria-label="打开导航" onclick="document.body.classList.toggle('nav-open')"><i data-lucide="menu"></i></button></header>'''


def page(title: str, body: str, active: str = "", query: str = "") -> HTMLResponse:
    return HTMLResponse(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="中国前沿科技融资热点研究平台"><link rel="icon" href="/favicon.ico"><title>{esc(title)} · 中国前沿科技融资热点雷达</title><link rel="stylesheet" href="/static/site.css"><script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script></head><body>{nav(active,query)}<main>{body}</main><footer><div><b>中国前沿科技融资热点雷达</b><p>当前分类Release分别展示正式事件、A类候选与B类候选，候选状态不代表人工确认。</p></div><a href="/methodology">数据口径与证据规则</a></footer><script>if(window.lucide)lucide.createIcons();</script></body></html>''')


def metric(label: str, icon: str, value: str | None, href: str = "") -> str:
    shown = esc(value) if value is not None else '<span class="pending">暂无已发布数据</span>'
    content = f'<i data-lucide="{icon}"></i><div><span>{label}</span><strong>{shown}</strong></div>'
    return f'<a class="metric metric-link" href="{esc(href)}">{content}<i class="metric-arrow" data-lucide="arrow-up-right"></i></a>' if href else f'<article class="metric">{content}</article>'


def filter_url(filters: PublicFilters, **changes: object) -> str:
    values = {
        "month": filters.month,
        "track": filters.track_id,
        "year": filters.year,
        "round": filters.round_name,
        "company": filters.company,
        "investor": filters.investor,
        "page": filters.page,
    }
    values.update(changes)
    query = urlencode({key: value for key, value in values.items() if value not in ("", None, 1)})
    return "/" + (f"?{query}" if query else "")


def filter_bar(data: dict, filters: PublicFilters) -> str:
    all_tracks_url = filter_url(filters, track="", page=1)
    track_buttons = [f'<a class="chip active" href="{all_tracks_url}">全部赛道</a>'] if not filters.track_id else [f'<a class="chip" href="{all_tracks_url}">全部赛道</a>']
    for item in data["tracks"]:
        selected = " active" if filters.track_id == item["track_id"] else ""
        track_buttons.append(f'<a class="chip{selected}" href="{filter_url(filters, track=item["track_id"], page=1)}">{esc(item["track_name"])}</a>')
    years = '<option value="">全部年份</option>' + "".join(f'<option value="{esc(year)}" {"selected" if filters.year == year else ""}>{esc(year)}年</option>' for year in data["years"])
    rounds = '<option value="">全部轮次</option>' + "".join(f'<option value="{esc(name)}" {"selected" if filters.round_name == name else ""}>{esc(name)}</option>' for name in data["rounds"])
    hidden_month = f'<input type="hidden" name="month" value="{esc(filters.month)}">' if filters.month else ""
    return f'''<section class="filter-panel"><div class="filter-title"><div><i data-lucide="list-filter"></i><b>联动筛选</b><span>同步更新图表、投资方排名与事件明细</span></div><a href="/">重置筛选</a></div><div class="track-chips">{"".join(track_buttons)}</div><form class="filter-form" method="get">{hidden_month}<input type="hidden" name="track" value="{esc(filters.track_id)}"><label>年份<select name="year">{years}</select></label><label>融资轮次<select name="round">{rounds}</select></label><label>企业搜索<input name="company" value="{esc(filters.company)}" placeholder="输入企业名称"></label><label>投资机构<input name="investor" value="{esc(filters.investor)}" placeholder="输入机构名称"></label><button type="submit"><i data-lucide="search"></i>应用筛选</button></form></section>'''


def monthly_chart(data: dict, filters: PublicFilters) -> str:
    if not data["months"]:
        return empty_state("暂无已发布融资数据", "首批融资事件完成核验与发布后，将按自然月展示融资趋势。")
    palette = ("#1677ff", "#7357d9", "#16a085", "#e39b2f", "#d75a72", "#4d95a8", "#6a7b91", "#25a66a")
    color_map = {item["track_id"]: palette[index % len(palette)] for index, item in enumerate(data["tracks"])}
    legend = "".join(f'<a class="legend-item {"muted" if filters.track_id and filters.track_id != item["track_id"] else ""}" href="{filter_url(filters, track="" if filters.track_id == item["track_id"] else item["track_id"], month="", page=1)}"><i style="--legend:{color_map[item["track_id"]]}"></i>{esc(item["track_name"])}</a>' for item in data["tracks"])
    maximum = max(item["total_event_count"] for item in data["months"])
    columns = []
    for item in data["months"]:
        selected = " selected" if filters.month == item["month"] else ""
        tooltip = f'{item["month"][:4]}年{int(item["month"][5:])}月｜' + "｜".join(f'{segment["track_name"]}：{segment["event_count"]}笔' for segment in item["tracks"]) + f'｜合计：{item["total_event_count"]}笔'
        segments = "".join(f'<span style="height:{max(8, segment["event_count"] / maximum * 190):.1f}px;background:{color_map.get(segment["track_id"], "#6a7b91")}"></span>' for segment in item["tracks"])
        target_month = "" if filters.month == item["month"] else item["month"]
        columns.append(f'<a class="month-column{selected}" href="{filter_url(filters, month=target_month, page=1)}" title="{esc(tooltip)}"><b>{item["total_event_count"]}</b><span class="stack">{segments}</span><small>{esc(item["month"])}</small></a>')
    return f'<div class="chart-legend">{legend}</div><div class="chart-scroll"><div class="monthly-chart">{"".join(columns)}</div></div><p class="coverage-note"><i data-lucide="info"></i>仅展示有已发布事件的月份；未验证覆盖的月份不会显示为 0。点击月份可筛选，再次点击可取消。</p>'


def investor_ranking(data: dict) -> str:
    if not data["investors"]:
        return empty_state("暂无已发布投资机构数据", "投资机构完成标准化并随融资事件发布后，将按参与的唯一事件数排名。")
    maximum = data["investors"][0]["investor_event_count"]
    rows = "".join(f'<a class="investor-rank" href="/investors/{esc(item["investor_id"])}"><span class="rank">{index}</span><span class="investor-name"><b>{esc(item["investor_name"])}</b><i><em style="width:{item["investor_event_count"] / maximum * 100:.1f}%"></em></i></span><strong>{item["investor_event_count"]}笔</strong></a>' for index, item in enumerate(data["investors"], 1))
    return f'<div class="investor-list">{rows}</div>'


def amount_display(event: dict) -> str:
    if event.get("is_cumulative_amount"):
        return "未披露（仅披露累计）"
    return str(event.get("amount_original") or "未披露")


def event_table(data: dict, filters: PublicFilters) -> str:
    if not data["events"]:
        return empty_state("暂无符合条件的融资事件", "只有核验、去重、双审并进入当前有效 Release 的事件才会出现。")
    rows = []
    for event in data["events"]:
        investors = "、".join(esc(item.get("official_name")) for item in event.get("investors", [])) or "未披露"
        sources = event.get("public_sources") or []
        source = f'<a href="{esc(sources[0]["url"])}" target="_blank" rel="noopener noreferrer">{esc(sources[0].get("title") or "查看原文")}<i data-lucide="external-link"></i></a>' if sources else "未公开"
        rows.append(f'<tr><td>{esc(event.get("announcement_date") or "日期待确认")}</td><td><a href="/companies/{esc(event.get("company_id"))}">{esc(event.get("company_name") or "未命名企业")}</a></td><td><span class="track-tag">{esc(event["track_name"])}</span></td><td>{esc(event.get("round_original") or event.get("round_normalized") or "未披露")}</td><td>{esc(amount_display(event))}</td><td>{investors}</td><td>{source}</td></tr>')
    pager = ""
    if data["pages"] > 1:
        links = "".join(f'<a class="{"active" if number == data["page"] else ""}" href="{filter_url(filters, page=number)}">{number}</a>' for number in range(1, data["pages"] + 1))
        pager = f'<nav class="pagination" aria-label="事件分页">{links}</nav>'
    return f'<div class="table-scroll"><table><thead><tr><th>日期</th><th>企业</th><th>赛道</th><th>融资轮次</th><th>融资金额</th><th>投资方</th><th>原始来源</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>{pager}'


def v30_classified_rows(events: list[dict], taxonomy: dict[str, list[dict]]) -> str:
    field_names = {item["field_id"]: item["name"] for item in taxonomy["fields"]}
    industry_names = {item["industry_id"]: item["name"] for item in taxonomy["industries"]}
    if not events:
        return empty_state("暂无已分类融资记录", "完成企业技术画像与主主题关联后，记录将在这里展示。")
    rows = []
    for event in sorted(events, key=lambda item: (item.get("disclosure_date", ""), item.get("company_name_standard", "")), reverse=True):
        classification = event["classification"]
        industry_name = industry_names.get(classification.get("primary_industry_id")) or "待分类"
        field_name = field_names.get(classification.get("primary_field_id")) or "产品技术证据待补充"
        business = event.get("primary_business") or "主营业务待补充"
        company_name = esc(event.get("company_name_standard") or event.get("company_name_original") or "未命名企业")
        company_id = event.get("company_id")
        company = f'<a href="/companies/{esc(company_id)}">{company_name}</a>' if company_id else company_name
        investors = str(event.get("investors_original") or "").strip()
        if investors.startswith("["):
            try:
                parsed_investors = json.loads(investors)
                if isinstance(parsed_investors, list):
                    investors = "、".join(str(item).strip() for item in parsed_investors if str(item).strip())
            except json.JSONDecodeError:
                pass
        if not investors or investors in {"未结构化提取", "待结构化", "未披露"}:
            investors = "未披露或待结构化"
        source_label = event.get("source_platform") or "查看原文"
        source = f'<a href="{esc(event["source_url"])}" target="_blank" rel="noopener noreferrer">{esc(source_label)}<i data-lucide="external-link"></i></a>'
        rows.append(
            f'<tr><td>{esc(event["disclosure_date"])}</td>'
            f'<td class="company-cell">{company}<small>{esc(business)}</small></td>'
            f'<td class="track-cell"><strong>{esc(industry_name)}</strong><small>{esc(field_name)}</small></td>'
            f'<td>{esc(event.get("round_original") or "未披露")}</td>'
            f'<td>{esc(event.get("amount_original") or "未披露")}</td>'
            f'<td>{esc(investors)}</td><td>{source}</td></tr>'
        )
    return f'<div class="table-scroll classified-table"><table class="taxonomy-table"><thead><tr><th>日期</th><th>企业</th><th>赛道</th><th>轮次</th><th>金额</th><th>投资方</th><th>来源</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def v30_event_rows(events: list[dict]) -> str:
    if not events: return empty_state("暂无关联融资事件", "当前主题尚无已归类记录。")
    rows = []
    for event in sorted(events, key=lambda item: item.get("disclosure_date", ""), reverse=True):
        status = "A类候选" if event["queue_class"] == "A" else "B类待核验"
        source = f'<a href="{esc(event["source_url"])}" target="_blank" rel="noopener noreferrer">查看原文<i data-lucide="external-link"></i></a>'
        rows.append(f'<tr><td>{esc(event["disclosure_date"])}</td><td>{esc(event["company_name_standard"])}</td><td>{esc(event["round_original"])}</td><td>{esc(event["amount_original"])}</td><td><span class="status-badge {event["queue_class"].lower()}">{status}</span></td><td>{source}</td></tr>')
    return f'<div class="table-scroll"><table class="taxonomy-table"><thead><tr><th>披露日期</th><th>企业</th><th>轮次</th><th>金额原文</th><th>审核状态</th><th>来源</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def formal_event_rows(events: list[dict]) -> str:
    if not events:
        return empty_state("暂无人工确认的正式融资事件", "事件必须同时完成人工确认并进入正式Release后才会显示。")
    rows = "".join(f'<tr><td>{esc(x["announcement_date"])}</td><td>{esc(x["company_name"])}</td><td>{esc(x["round_original"])}</td><td>{esc(x["amount_original"])}</td><td>正式发布</td></tr>' for x in sorted(events, key=lambda item: item["announcement_date"], reverse=True))
    return f'<div class="table-scroll"><table class="taxonomy-table"><thead><tr><th>公告日期</th><th>企业</th><th>轮次</th><th>金额</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div>'


def capital_amount(value: int | float, currency: str) -> str:
    if currency == "CNY":
        return f"¥{value / 100_000_000:.2f}亿元" if value >= 100_000_000 else f"¥{value / 10_000:.0f}万元"
    if currency == "USD":
        return f"${value / 1_000_000:.2f}M"
    return f"{value:,.0f} {currency}"


def capital_flow_window(data: dict, candidate_rounds: dict, candidate_industries: dict, days: int) -> str:
    totals = data["totals"]
    amounts = totals["amounts"]
    amount_summary = " / ".join(capital_amount(value, code) for code, value in amounts.items()) or "暂无可统计金额"
    cards = "".join((
        metric("已披露融资金额", "coins", amount_summary),
        metric("候选融资事件数", "layers-3", f'{candidate_industries["total"]} 起'),
        metric("涉及企业数（候选）", "building-2", f'{candidate_industries["company_count"]} 家', "/companies/repeated"),
        metric("覆盖产业领域数（候选）", "network", f'{candidate_industries["industry_count"]} 个'),
    ))
    ranking_rows = []
    ranking_max = max((row["event_count"] for row in candidate_industries["industries"]), default=0)
    for index, row in enumerate(candidate_industries["industries"]):
        width = row["event_count"] / ranking_max * 100 if ranking_max else 0
        ranking_rows.append(f'<a href="/events?industry_id={esc(row["industry_id"])}&amp;window={days}"><span>{esc(row["industry_name"])}</span><i class="candidate-industry-bar"><u style="width:{width:.1f}%"></u></i><b>{row["event_count"]} 起</b><em>{row["share"]:.1%}</em></a>')
    disclosed_value = amount_summary if amounts else "—"
    disclosure = f'''<div class="disclosed-total"><strong>{esc(disclosed_value)}</strong></div><p class="disclosure-note"><i data-lucide="info"></i><span>仅统计可核验的披露金额<br><small>未披露金额、金额区间、累计金额不计入</small></span></p><div class="disclosure-summary"><h4>本周期融资数据概览</h4><dl><div><dt>精确披露金额事件</dt><dd>{totals["amount_disclosed_event_count"]} 起</dd></div><div><dt>区间披露金额事件</dt><dd>{totals["range_amount_event_count"]} 起（不计入金额）</dd></div><div><dt>未披露金额事件</dt><dd>{totals["undisclosed_amount_event_count"]} 起</dd></div><div><dt>美元融资事件</dt><dd>{totals["usd_event_count"]} 起（单独统计）</dd></div></dl></div>'''
    palette = ("#1267dc", "#5caef2", "#8a79e8", "#cbd5e3")
    offset = 0.0; stops = []; round_rows = []; distribution_views = []
    for index, row in enumerate(candidate_rounds["groups"]):
        color = palette[index]
        if row["share"]:
            stops.append(f'{color} {offset:.1%} {(offset + row["share"]):.1%}')
            offset += row["share"]
        selected = " selected" if index == 0 else ""
        round_rows.append(f'<li><button type="button" class="round-selector{selected}" data-round-key="{esc(row["key"])}" aria-selected="{str(index == 0).lower()}" onclick="selectRoundIndustry(\'{esc(row["key"])}\',this)"><i style="background:{color}"></i><span>{esc(row["label"])}</span><b>{row["count"]}</b><em>{row["share"]:.1%}</em></button></li>')
        industry_max = max((item["event_count"] for item in row["industries"]), default=0)
        industry_bars = "".join(f'<a class="round-industry-row" href="/events?industry_id={esc(item["industry_id"])}&amp;round_group={esc(row["key"])}&amp;window={days}" title="查看{esc(row["label"])} · {esc(item["industry_name"])}融资事件"><span>{esc(item["industry_name"])}</span><i><u style="width:{(item["event_count"] / industry_max * 100) if industry_max else 0:.1f}%"></u></i><b>{item["event_count"]} 起</b><em>{item["share"]:.1%}</em></a>' for item in row["industries"])
        empty = empty_state("暂无该轮次候选事件", f"近{days}天窗口内没有这一轮次分组。") if not industry_bars else ""
        distribution_views.append(f'''<div class="round-industry-view" data-round-view="{esc(row["key"])}" {"" if index == 0 else "hidden"}><h3>{esc(row["label"])} 产业领域分布</h3><div class="round-summary"><div><i data-lucide="layers-3"></i><span>融资事件数<b>{row["count"]} 起</b></span></div><div><i data-lucide="building-2"></i><span>涉及企业<b>{row["company_count"]} 家</b></span></div><div><i data-lucide="network"></i><span>覆盖领域<b>{row["industry_count"]} 个</b></span></div><div><i data-lucide="pie-chart"></i><span>占全部候选样本<b>{row["share"]:.1%}</b></span></div></div><div class="round-industry-head"><span>产业领域（一级）</span><b>融资事件数</b><em>占比</em></div><div class="round-industry-bars">{industry_bars or empty}</div></div>''')
    donut_background = f'conic-gradient({",".join(stops)})' if stops else '#e4ebf4'
    ring = f'<div class="candidate-donut" style="--donut:{donut_background}"><span><b>{candidate_rounds["total"]}起</b><small>候选融资数量</small></span></div><div class="candidate-round-table"><div class="candidate-round-head"><span>轮次</span><b>数量</b><em>占比</em></div><ul class="round-list">{"".join(round_rows)}</ul></div><p class="candidate-scope-note">A类{candidate_rounds["queue_counts"].get("A",0)}条 · B类{candidate_rounds["queue_counts"].get("B",0)}条候选观察样本<br>{esc(candidate_rounds["note"])}</p>'
    distribution = "".join(distribution_views)
    coverage = (f'数据完整覆盖所选窗口' if data["coverage_complete"] else f'历史数据仅覆盖 {data["effective_start_date"]} 至 {data["source_end_date"]}，不代表完整近{days}天市场')
    return f'''<div class="capital-window" data-capital-window="{days}" {"" if days == 30 else "hidden"}><p class="capital-range">按公告日期统计 · 滚动{days}天 · 统计区间：{data["start_date"]} 至 {data["end_date"]} · {esc(coverage)}</p><div class="capital-metrics">{cards}</div><p class="capital-empty-banner">{("本周期暂无人工确认的正式融资事件；下方为A/B类候选观察样本" if totals["event_count"] == 0 else "正式事件与候选观察样本分开展示")}</p><div class="capital-grid"><article class="capital-panel capital-ranking"><h3>各领域融资事件次数与占比 <small>{candidate_industries["total"]}条候选观察样本（近{days}天）</small></h3><div class="ranking-list candidate-industry-ranking">{"".join(ranking_rows)}</div></article><article class="capital-panel capital-disclosure"><h3>已披露融资金额 <small>（正式Release辅助指标）</small></h3>{disclosure}</article><article class="capital-panel capital-structure"><h3>资金结构（按轮次） <small>{candidate_rounds["total"]}条候选观察样本</small></h3>{ring}</article><article class="capital-panel round-industry-panel">{distribution}</article></div><p class="capital-method"><i data-lucide="shield-check"></i>未披露、累计融资及金额区间不计入金额合计；多主题关联按唯一事件ID去重。</p></div>'''


def capital_flow_module(windows: dict[int, dict]) -> str:
    panes = "".join(capital_flow_window(item["formal"], item["rounds"], item["industries"], days) for days, item in windows.items())
    buttons = "".join(f'<button type="button" class="capital-period{(" active" if days == 30 else "")}" data-period="{days}" aria-pressed="{str(days == 30).lower()}" onclick="selectCapitalPeriod({days},this)">近{days}天</button>' for days in windows)
    return f'''<section class="capital-overview" id="monthly-capital-flow"><div class="capital-title"><div><span class="capital-icon"><i data-lucide="chart-no-axes-combined"></i></span><div><span class="kicker">CAPITAL FLOW OVERVIEW</span><h2>资本流向概览</h2></div></div><div class="capital-periods" aria-label="统计周期">{buttons}</div></div>{panes}<script>function selectCapitalPeriod(days,button){{const root=document.getElementById('monthly-capital-flow');root.querySelectorAll('[data-capital-window]').forEach(view=>view.hidden=String(days)!==view.dataset.capitalWindow);root.querySelectorAll('[data-period]').forEach(item=>{{const active=item===button;item.classList.toggle('active',active);item.setAttribute('aria-pressed',active)}});if(window.lucide)lucide.createIcons();}}function selectRoundIndustry(key,button){{const root=button.closest('[data-capital-window]');root.querySelectorAll('[data-round-view]').forEach(view=>view.hidden=view.dataset.roundView!==key);root.querySelectorAll('[data-round-key]').forEach(item=>{{const active=item===button;item.classList.toggle('selected',active);item.setAttribute('aria-selected',active)}});}}</script></section>'''


def v30_home(overview: dict) -> HTMLResponse:
    manifest = overview["manifest"]; taxonomy = service.v30_taxonomy(); events = overview["events"]
    windows = {}
    for days in (30, 90, 360):
        candidate = service.v30_candidate_window(days)
        windows[days] = {
            "formal": service.formal_capital_window(days, cutoff=candidate["end_date"]),
            "rounds": candidate["rounds"], "industries": candidate["industries"],
        }
        windows[days]["formal"].update({key: candidate[key] for key in (
            "start_date", "end_date", "source_start_date", "source_end_date", "effective_start_date", "coverage_complete"
        )})
    classified_events = [event for event in events if event["classification"].get("primary_industry_id")]
    counts: dict[str, int] = {}
    for event in classified_events:
        key = event["classification"]["primary_industry_id"]
        counts[key] = counts.get(key, 0) + 1
    industry_cards = "".join(f'<a class="field-card" href="/industries/{item["industry_id"]}"><span class="field-en">INDUSTRY {esc(item["code"])}</span><h3>{esc(item["name"])}</h3><p>{sum(field["industry_id"]==item["industry_id"] for field in taxonomy["fields"])}个二级领域 · {sum(topic["field_id"] in {field["field_id"] for field in taxonomy["fields"] if field["industry_id"]==item["industry_id"]} for topic in taxonomy["topics"])}个三级主题</p><span class="field-count">{counts.get(item["industry_id"],0)}个已归类候选事件</span></a>' for item in taxonomy["industries"])
    version = taxonomy.get("version") or manifest.get("taxonomy_version", "V3.0")
    body = f'''<section class="hero taxonomy-hero"><div class="hero-content"><span class="eyebrow">FROZEN TAXONOMY · {esc(version)}</span><h1>中国前沿科技融资热点雷达</h1><p>以{len(taxonomy["industries"])}个产业方向、{len(taxonomy["fields"])}个技术领域和{len(taxonomy["topics"])}个技术主题组织融资样本。</p><dl><div><dt>分类版本</dt><dd>{esc(version)} · frozen</dd></div><div><dt>已归类/待分类</dt><dd>{manifest["classified"]} / {manifest["pending_classification"]}</dd></div><div><dt>更新时间</dt><dd>{esc(overview["release"]["created_at"][:10])}</dd></div></dl></div></section><div class="page-shell">{capital_flow_module(windows)}<section><div class="section-head"><div><span class="kicker">10 INDUSTRY DIRECTIONS</span><h2>产业技术分类导航</h2><p>逐级进入二级技术领域和三级技术主题</p></div><a href="/taxonomy">查看完整分类</a></div><div class="field-grid taxonomy-grid">{industry_cards}</div></section><section class="panel event-detail"><div class="section-head"><div><span class="kicker">FUNDING RECORDS</span><h2>融资记录</h2><p>共{len(events)}条，其中{len(classified_events)}条已归入一级分类；企业下方展示主营业务画像</p></div></div>{v30_classified_rows(events, taxonomy)}</section></div>'''
    return page("首页", body, "/")


async def home(request: Request) -> HTMLResponse:
    v30 = service.v30_overview()
    if v30: return v30_home(v30)
    def page_number(value: str | None) -> int:
        try:
            return max(int(value or "1"), 1)
        except ValueError:
            return 1

    filters = PublicFilters(month=request.query_params.get("month", ""), track_id=request.query_params.get("track", ""), year=request.query_params.get("year", ""), round_name=request.query_params.get("round", ""), company=request.query_params.get("company", ""), investor=request.query_params.get("investor", ""), page=page_number(request.query_params.get("page")))
    overview = service.overview()
    data = service.monthly_analysis(filters)
    release = overview["release"]
    metrics = overview["metrics"]
    release_label = release.release_name if release else "尚无有效 Release"
    updated = release.created_at[:10] if release else "首批样本审核中"
    coverage = data["coverage"]
    coverage_label = f'{coverage["first_month"]} 至 {coverage["last_month"]}（已发布事件月份）' if coverage else "暂无已发布数据"
    cards = "".join((
        metric("融资事件数","landmark",str(metrics["events"]) if metrics else None),
        metric("精确披露融资金额","circle-dollar-sign",f'¥{metrics["exact_amount"]:,}' if metrics else None),
        metric("融资企业数量","building-2",str(metrics["companies"]) if metrics else None),
        metric("活跃投资机构数量","briefcase-business",str(metrics["investors"]) if metrics else None),
    ))
    fields = "".join(f'<a class="field-card" href="/fields/{fid}"><i data-lucide="{icon}"></i><span class="field-en">{en}</span><h3>{zh}</h3><p>{desc}</p><span class="field-count">暂无已发布数据</span></a>' for (fid,zh,en,desc),icon in zip(FIELDS,("flask-conical","atom","cpu","battery-charging","bot","layers-3")))
    selected_label = f'<span class="selection-note"><i data-lucide="calendar-check"></i>当前月份：{esc(filters.month)}<a href="{filter_url(filters, month="", page=1)}">取消</a></span>' if filters.month else ""
    body = f'''<section class="hero"><div class="hero-overlay"></div><div class="hero-content"><span class="eyebrow">CAPITAL SIGNALS · VERIFIED EVIDENCE</span><h1>资本正在流向哪些科技方向？</h1><p>追踪中国科技企业融资动态，发现新兴技术赛道，连接科研热点与产业资本。</p><dl><div><dt>数据覆盖时间</dt><dd>{esc(coverage_label)}</dd></div><div><dt>数据范围</dt><dd>中国科技企业一级市场股权融资</dd></div><div><dt>数据更新日期</dt><dd>{esc(updated)}</dd></div><div><dt>Release</dt><dd>{esc(release_label)}</dd></div></dl></div></section>
    <div class="page-shell"><section class="metrics">{cards}</section>{'<p class="notice"><i data-lucide="shield-check"></i> 数据审核与首批样本验证进行中。公开端不会展示候选、待审或已撤回数据。</p>' if not release else ''}
    {filter_bar(data, filters)}{selected_label}<section class="monthly-analysis"><article class="panel chart-panel"><div class="section-head"><div><span class="kicker">MONTHLY CAPITAL FLOW</span><h2>每月融资事件数</h2><p>按赛道堆叠 · 悬停查看明细</p></div></div>{monthly_chart(data, filters)}</article><article class="panel investor-panel"><div class="section-head"><div><span class="kicker">ACTIVE INVESTORS</span><h2>最活跃投资方</h2><p>按参与事件数（当前筛选）</p></div><span class="top-label">TOP 10</span></div>{investor_ranking(data)}</article></section>
    <section class="panel event-detail"><div class="section-head"><div><span class="kicker">VERIFIED EVENTS</span><h2>融资事件明细</h2><p>按公布日期倒序 · 共 {data["total_events"]} 笔</p></div></div>{event_table(data, filters)}</section>
    <section><div class="section-head"><div><span class="kicker">SIX RESEARCH FIELDS</span><h2>六大学科导航</h2></div><a href="/fields">浏览学科</a></div><div class="field-grid">{fields}</div></section>
    <section class="split-section"><article><div class="section-head"><div><span class="kicker">EMERGING SIGNALS</span><h2>新兴方向</h2></div><a href="/emerging">进入发现区</a></div>{empty_state('候选方向尚未开放','等待阶段 2 动态术语与主题结果，当前不生成虚构赛道。')}</article><article><div class="section-head"><div><span class="kicker">LATEST EVENTS</span><h2>最新融资动态</h2></div><a href="/events">全部事件</a></div>{empty_state('暂无已发布融资事件','事件完成证据核验、去重和双审后才会在此出现。')}</article></section>
    <section class="split-section secondary-split"><article><div class="section-head"><div><span class="kicker">FOCUS COMPANIES</span><h2>重点企业</h2></div><a href="/companies">企业库</a></div>{empty_state('暂无已发布重点企业','企业标签和融资时间线仅从当前有效 Release 生成。')}</article><article><div class="section-head"><div><span class="kicker">INVESTOR ACTIVITY</span><h2>投资机构动态</h2></div><a href="/investors">机构库</a></div>{empty_state('暂无已发布机构动态','不会将新闻提及次数作为投资事件数量。')}</article></section></div>'''
    return page("首页",body,"/")


def listing(title: str, kicker: str, intro: str, empty_title: str, active: str) -> HTMLResponse:
    return page(title,f'<div class="page-shell subpage"><span class="kicker">{kicker}</span><h1>{title}</h1><p class="lede">{intro}</p><section class="panel">{empty_state(empty_title,"首批融资样本审核完成并形成有效 Release 后展示。")}</section></div>',active)


async def fields(request: Request):
    cards="".join(f'<a class="field-card" href="/fields/{fid}"><span class="field-en">{en}</span><h3>{zh}</h3><p>{desc}</p></a>' for fid,zh,en,desc in FIELDS)
    return page("六大学科",f'<div class="page-shell subpage"><span class="kicker">SIX RESEARCH FIELDS</span><h1>六大学科</h1><p class="lede">分类用于浏览与长期比较，不限制融资事件发现。</p><div class="field-grid">{cards}</div></div>',"/fields")


async def field_detail(request: Request):
    data=service.v30_field(request.path_params["field_id"])
    if data:
        cards="".join(f'<a class="topic-card" href="/themes/{topic["topic_id"]}"><span>{esc(topic["management_status"])}</span><h3>{esc(topic["name"])}</h3><p>{esc(topic["technical_boundary"])}</p></a>' for topic in data["topics"])
        return page(data["field"]["name"],f'<div class="page-shell subpage"><a class="back" href="/industries/{data["industry"]["industry_id"]}">← 返回{esc(data["industry"]["name"])}</a><span class="kicker">TECHNOLOGY FIELD</span><h1>{esc(data["field"]["name"])}</h1><p class="lede">三级候选主题保留原始状态，未人工确认的主题不会被描述为正式主题。</p><div class="topic-grid">{cards}</div></div>',"/taxonomy")
    item=next((x for x in FIELDS if x[0]==request.path_params["field_id"]),None); title=item[1] if item else "未知领域"
    return page(title,f'<div class="page-shell subpage"><h1>{esc(title)}</h1>{empty_state("未找到该技术领域","请返回分类导航。")}</div>',"/taxonomy")


async def taxonomy(request: Request):
    data=service.v30_taxonomy()
    cards="".join(f'<a class="field-card" href="/industries/{item["industry_id"]}"><span class="field-en">{esc(item["code"])}</span><h3>{esc(item["name"])}</h3><p>{sum(x["industry_id"]==item["industry_id"] for x in data["fields"])}个二级领域</p></a>' for item in data["industries"])
    return page("产业技术分类",f'<div class="page-shell subpage"><span class="kicker">{esc(data.get("version") or "V3")} FROZEN TAXONOMY</span><h1>产业技术分类</h1><p class="lede">{len(data["industries"])}个一级产业方向、{len(data["fields"])}个二级技术领域、{len(data["topics"])}个三级技术主题。来源主题身份和历史ID完整保留。</p><div class="field-grid taxonomy-grid">{cards}</div></div>',"/taxonomy")


async def industry_detail(request: Request):
    data=service.v30_industry(request.path_params["industry_id"])
    if not data: return page("产业方向",f'<div class="page-shell subpage">{empty_state("未找到产业方向","请返回分类导航。")}</div>',"/taxonomy")
    blocks=[]
    for field in data["fields"]:
        topics=[x for x in data["topics"] if x["field_id"]==field["field_id"]]
        links="".join(f'<a href="/themes/{x["topic_id"]}">{esc(x["name"])}</a>' for x in topics) or '<span class="pending">当前无三级主题</span>'
        blocks.append(f'<article class="field-block"><a href="/fields/{field["field_id"]}"><h2>{esc(field["name"])}</h2></a><div class="topic-links">{links}</div></article>')
    return page(data["industry"]["name"],f'<div class="page-shell subpage"><a class="back" href="/taxonomy">← 返回产业技术分类</a><span class="kicker">INDUSTRY DIRECTION</span><h1>{esc(data["industry"]["name"])}</h1><p class="lede">包含{len(data["fields"])}个二级技术领域和{len(data["topics"])}个三级候选主题。</p><div class="field-block-grid">{"".join(blocks)}</div></div>',"/taxonomy")


async def theme_detail(request: Request):
    data=service.v30_topic(request.path_params["topic_id"])
    if not data: return page("主题详情",f'<div class="page-shell subpage">{empty_state("未找到主题","请返回分类导航。")}</div>',"/taxonomy")
    taxonomy=service.v30_taxonomy()
    topic=data["topic"]; companies="".join(f'<article class="company-card"><h3>{esc(x["name"])}</h3><p>{esc(x["business"])}</p><small>产品：{esc(x["products"])}<br>技术：{esc(x["technologies"])}</small></article>' for x in data["companies"])
    rounds="、".join(f'{esc(k)} {v}笔' for k,v in data["rounds"].items()) or "暂无"
    body=f'<div class="page-shell subpage"><a class="back" href="/fields/{data["field"]["field_id"]}">← 返回{esc(data["field"]["name"])}</a><span class="kicker">CANDIDATE TECHNOLOGY THEME</span><h1>{esc(topic["name"])}</h1><p class="lede">{esc(topic["technical_boundary"])}</p><section class="theme-metrics"><div><span>一级产业</span><b>{esc(data["industry"]["name"])}</b></div><div><span>二级领域</span><b>{esc(data["field"]["name"])}</b></div><div><span>关联企业</span><b>{len(data["companies"])}家</b></div><div><span>唯一候选事件</span><b>{len({x["unique_event_id"] for x in data["events"]})}笔</b></div></section><section><div class="section-head"><div><h2>企业技术画像</h2><p>产品和技术字段来自冻结前的清洗建议层</p></div></div><div class="company-grid">{companies or empty_state("暂无企业画像","等待事件完成分类。")}</div></section><section class="panel event-detail"><div class="section-head"><div><h2>融资事件时间线</h2><p>轮次分布：{rounds}</p></div></div>{v30_classified_rows(data["events"],taxonomy)}</section><p class="coverage-note">数据更新：{esc(service.v30_release()["created_at"][:10])} · 主题状态：{esc(topic["management_status"])}</p></div>'
    return page(topic["name"],body,"/taxonomy")


async def tracks(request: Request): return listing("融资赛道","FUNDING TRACKS","按已发布唯一事件观察资本进入的技术赛道。","暂无融资赛道数据","/tracks")
async def track_detail(request: Request): return listing("赛道详情","TRACK DETAIL","赛道指标将在真实主题数据发布后展示。","该赛道尚无已发布数据","/tracks")
async def emerging(request: Request): return listing("新兴方向","EMERGING SIGNALS","保留无法归入稳定分类的资本信号；本轮仅提供页面框架。","暂无经审核的新兴方向","/emerging")
async def companies(request: Request):
    overview=service.v30_overview()
    if overview:
        companies={event["company_id"]:event for event in overview["events"] if event.get("company_id")}
        cards="".join(f'<a class="company-card" href="/companies/{cid}"><h3>{esc(event["company_name_standard"])}</h3><p>{esc(event.get("primary_business") or "业务信息待补充")}</p><small>{"A类候选" if event["queue_class"]=="A" else "B类待核验"}</small></a>' for cid,event in sorted(companies.items(),key=lambda x:x[1]["company_name_standard"]))
        release=service.v30_release(); manifest=json.loads(release["manifest_json"]) if release else {}
        return page("企业库",f'<div class="page-shell subpage"><span class="kicker">COMPANY DIRECTORY</span><h1>企业库</h1><p class="lede">覆盖{esc(manifest.get("taxonomy_version","当前"))} Release中的候选企业；审核状态不会被隐藏。</p><div class="company-grid">{cards}</div></div>',"/companies")
    return listing("企业库","COMPANY DIRECTORY","仅展示有效 Release 中的企业。","暂无已发布企业","/companies")


async def repeated_companies(request: Request):
    groups = service.v34_merged_candidate_sources()
    taxonomy = service.v30_taxonomy()
    sections = []
    for group in groups:
        sections.append(f'''<section class="panel repeated-company"><div class="section-head"><div><span class="repeat-badge confirmed">已合并重复来源</span><h2><a href="/companies/{esc(group["company_id"])}">{esc(group["company_name"])}</a></h2><p>{esc(group["reason"])}</p></div><strong>保留1个事件</strong></div>{v30_classified_rows(group["records"],taxonomy)}</section>''')
    body = f'''<div class="page-shell subpage"><a class="back" href="/">← 返回首页</a><span class="kicker">SOURCE MERGE AUDIT</span><h1>重复来源合并记录</h1><p class="lede">原始97条来源记录完整保留；两组重复来源经用户确认后合并为95个候选融资事件。以下展示主记录与被合并来源，网站统计仅计一次。</p>{"".join(sections) or empty_state("暂无重复来源合并记录","当前没有已确认的重复来源合并决定。")}</div>'''
    return page("重复来源合并记录", body, "/companies")
async def company_detail(request: Request):
    company=service.v30_company(request.path_params["company_id"])
    if not company:
        company=service.historical_company(request.path_params["company_id"])
    if company:
        body=f'<div class="page-shell subpage"><a class="back" href="/companies">← 返回企业库</a><span class="kicker">COMPANY DETAIL</span><h1>{esc(company["name"])}</h1><p class="lede">{esc(company["business"])}</p><section class="theme-metrics"><div><span>核心产品</span><b>{esc(company["products"])}</b></div><div><span>核心技术</span><b>{esc(company["technologies"])}</b></div><div><span>融资记录</span><b>{len(company["events"])}笔</b></div></section><section class="panel event-detail">{v30_classified_rows(company["events"],service.v30_taxonomy())}</section></div>'
        return page(company["name"],body,"/companies")
    company=service.company(request.path_params["company_id"]); return listing(company["name"] if company else "企业详情","COMPANY DETAIL","企业产品、技术方向和融资时间线。","暂无可公开企业数据","/companies")
async def investors(request: Request): return listing("投资机构","INVESTOR DIRECTORY","仅统计有效 Release 中去重后的投资机构。","暂无已发布投资机构","/investors")
async def investor_detail(request: Request): return listing("投资机构详情","INVESTOR DETAIL","投资事件和技术方向将在证据确认后展示。","暂无可公开机构数据","/investors")
async def events(request: Request):
    if request.query_params.get("scope") == "formal":
        industry_id=request.query_params.get("industry_id","")
        rows=[x for x in service.formal_released_events() if not industry_id or x.get("primary_industry_id")==industry_id]
        industry=next((x for x in service.v30_taxonomy()["industries"] if x["industry_id"]==industry_id),None)
        label=f' · {industry["name"]}' if industry else ""
        return page("正式融资事件",f'<div class="page-shell subpage"><span class="kicker">FORMAL FUNDING EVENTS</span><h1>正式融资事件{esc(label)}</h1><p class="lede">仅展示人工确认有效且进入正式Release的事件；A/B候选和历史待确认记录不在此列表。</p><section class="panel event-detail">{formal_event_rows(rows)}</section></div>',"/events")
    overview=service.v30_overview()
    if overview:
        taxonomy=service.v30_taxonomy()
        industry_id=request.query_params.get("industry_id","")
        round_group=request.query_params.get("round_group","")
        valid_round_groups={"vc":"VC（Pre-A–B++）","early":"早期（种子/天使）","strategic":"战略投资 / 并购","other":"其他"}
        if round_group not in valid_round_groups: round_group=""
        try: window_days=int(request.query_params.get("window", "0"))
        except ValueError: window_days=0
        if window_days not in {30,90,360}: window_days=0
        all_events=service.historical_candidate_events()
        window_events=rolling_window(all_events, window_days, cutoff="2026-11-25")["events"] if window_days else all_events
        rows=[event for event in window_events if (not industry_id or event["classification"].get("primary_industry_id")==industry_id) and (not round_group or candidate_round_bucket(event.get("round_original"))==round_group)]
        classified=sum(event["classification"].get("primary_industry_id") is not None for event in rows)
        industry=next((x for x in taxonomy["industries"] if x["industry_id"]==industry_id),None)
        label=f' · {industry["name"]}' if industry else ""
        round_label=f' · {valid_round_groups[round_group]}' if round_group else ""
        window_label=f' · 近{window_days}天' if window_days else ""
        return page("融资事件",f'<div class="page-shell subpage"><a class="back" href="/">← 返回首页资本流向</a><span class="kicker">FUNDING RECORDS</span><h1>融资事件{esc(label)}{esc(round_label)}{esc(window_label)}</h1><p class="lede">共{len(rows)}条，其中{classified}条已归入一级分类；企业下方展示主营业务画像。</p><section class="panel event-detail">{v30_classified_rows(rows,taxonomy)}</section></div>',"/events")
    return listing("融资事件","VERIFIED EVENTS","文档数与唯一融资事件数严格分离。","暂无已发布融资事件","/events")
async def event_detail(request: Request):
    event=service.event(request.path_params["event_id"])
    return listing(event.get("company_name") if event else "融资事件详情","EVENT DETAIL","金额原文、轮次、投资方与主要证据来源。","该事件不在当前有效 Release 中","/events")


async def methodology(request: Request):
    data=service.overview()
    release=data["release"].release_name if data["release"] else "尚无有效 Release"
    sections=(("数据范围","中国科技企业一级市场股权融资；并购、IPO、定增、债券、授信、补贴和科研资助不混入统计。"),("融资事件定义","同一笔融资的多篇报道合并为一个唯一事件，原始文档仍全部保留。"),("去重方法","综合企业、日期、轮次、金额、投资机构、文本和引用链；明确不同轮次为强冲突。"),("金额规则","只有精确披露且非累计金额进入精确金额合计；区间金额不取中点。"),("证据等级","S 为法定/监管文件，A 为企业或投资机构官方，B 为政府/高校/可信专业媒体，C 为行业媒体，D 仅作线索。"),("审核流程","文档初筛、主体确认、字段证据、事件去重、两轮独立审核、质量门槛、不可变 Release。"),("月度统计","按中国标准时间将融资公布日期归入自然月；日期不明确的事件不进入月度图，未验证覆盖的月份不显示为零。"),("更新频率","当前处于首批样本验证期；仅在审核完成并发布新 Release 后更新。"))
    cards="".join(f'<article class="method-card"><h2>{t}</h2><p>{d}</p></article>' for t,d in sections)
    return page("数据说明",f'<div class="page-shell subpage"><span class="kicker">METHODOLOGY</span><h1>数据说明</h1><p class="lede">当前 Release：{esc(release)}</p><div class="method-grid">{cards}</div></div>',"/methodology")


async def search(request: Request):
    q=request.query_params.get("q","")
    results=service.search(q)
    content="".join(f'<a class="result" href="{esc(r["url"])}"><span>{esc(r["type"])}</span><b>{esc(r["title"])}</b></a>' for r in results) if results else empty_state("没有公开搜索结果","搜索只覆盖当前有效 Release，不检索待审或候选数据。")
    return page("搜索",f'<div class="page-shell subpage"><span class="kicker">SEARCH</span><h1>搜索：{esc(q)}</h1><section class="panel">{content}</section></div>',query=q)


async def favicon(request: Request):
    return Response(status_code=204)


async def monthly_capital_flow_api(request: Request):
    try:
        data=service.formal_monthly_capital_flow(
            request.query_params.get("month") or None,
            currency=request.query_params.get("currency", "").upper(),
            industry_id=request.query_params.get("industry_id", ""),
            round_name=request.query_params.get("round", ""),
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    return JSONResponse(data, headers={"Cache-Control":"public, max-age=300"})


async def capital_window_api(request: Request):
    try:
        days=int(request.query_params.get("window", "30"))
        candidate=service.v30_candidate_window(days)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    formal=service.formal_capital_window(days, cutoff=candidate["end_date"])
    return JSONResponse({
        "window_days": days,
        "date_range": {key: candidate[key] for key in ("start_date", "end_date", "effective_start_date", "source_start_date", "source_end_date", "coverage_complete")},
        "formal_release": formal["totals"],
        "candidate_observation": {"industries": candidate["industries"], "rounds": candidate["rounds"]},
        "methodology": "按公告日期和稳定事件ID去重；正式Release与A/B候选观察样本分开统计",
    }, headers={"Cache-Control":"public, max-age=300"})


routes=[Route("/",home),Route("/api/monthly-capital-flow",monthly_capital_flow_api),Route("/api/capital-flow",capital_window_api),Route("/favicon.ico",favicon),Route("/taxonomy",taxonomy),Route("/industries/{industry_id}",industry_detail),Route("/fields",fields),Route("/fields/{field_id}",field_detail),Route("/themes/{topic_id}",theme_detail),Route("/tracks",tracks),Route("/tracks/{topic_id}",track_detail),Route("/emerging",emerging),Route("/companies",companies),Route("/companies/repeated",repeated_companies),Route("/companies/{company_id}",company_detail),Route("/investors",investors),Route("/investors/{investor_id}",investor_detail),Route("/events",events),Route("/events/{event_id}",event_detail),Route("/methodology",methodology),Route("/search",search)]
app=Starlette(debug=False,routes=routes)
app.mount("/static",StaticFiles(directory=STATIC),name="static")
