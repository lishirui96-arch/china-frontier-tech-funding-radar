import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(import.meta.dirname, "..");
const out = path.join(root, "work", "v30_qa");
await fs.mkdir(out, { recursive: true });
const browserCandidates = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];
const executablePath = browserCandidates.find(candidate => fsSync.existsSync(candidate));
const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
const results = [];
try {
  for (const config of [
    { name: "desktop", viewport: { width: 1440, height: 1000 } },
    { name: "mobile", viewport: { width: 390, height: 844 } },
  ]) {
    const page = await browser.newPage({ viewport: config.viewport });
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    page.on("console", message => { if (message.type() === "error" && !message.text().includes("lucide")) errors.push(message.text()); });
    await page.goto("http://127.0.0.1:8511", { waitUntil: "domcontentloaded" });
    await page.locator("#monthly-capital-flow").waitFor();
    await page.screenshot({ path: path.join(out, `8511_home_${config.name}.png`), fullPage: true });
    const text = await page.locator("body").innerText();
    if (!text.includes("10个产业方向") || !text.includes("42个技术领域") || !text.includes("51个候选主题") || !text.includes("95 / 0") || !text.includes("共95条")) throw new Error(`V3.2 home assertions failed: ${config.name}`);
    if (text.includes("正式/A/B")) throw new Error(`legacy formal candidate metric still visible: ${config.name}`);
    if (!text.includes("本周期暂无人工确认的正式融资事件") || !text.includes("各领域融资事件次数与占比") || !text.includes("已披露融资金额")) throw new Error(`rolling capital flow layout failed: ${config.name}`);
    if (!text.includes("近30天") || !text.includes("近90天") || !text.includes("近360天") || !text.includes("历史数据仅覆盖 2026-11-02 至 2026-11-25")) throw new Error(`capital period controls failed: ${config.name}`);
    if (!text.includes("95条候选观察样本") || !text.includes("VC（Pre-A–B++）") || !text.includes("69.5%") || !text.includes("早期（种子/天使）") || !text.includes("30.5%")) throw new Error(`candidate round donut failed: ${config.name}`);
    if (!text.includes("候选融资事件数") || !text.includes("95 起") || !text.includes("涉及企业数（候选）") || !text.includes("95 家") || !text.includes("覆盖产业领域数（候选）") || !text.includes("10 个")) throw new Error(`candidate metric cards failed: ${config.name}`);
    if (text.includes("近6个月融资趋势") || !text.includes("VC（Pre-A–B++） 产业领域分布") || !text.includes("66 起") || !text.includes("66 家") || !text.includes("9 个")) throw new Error(`round industry default view failed: ${config.name}`);
    await page.locator('[data-period="90"]').click();
    const activeWindow = page.locator('[data-capital-window="90"]');
    if (!(await activeWindow.isVisible()) || !(await activeWindow.innerText()).includes("滚动90天")) throw new Error(`90 day capital period failed: ${config.name}`);
    await activeWindow.locator('[data-round-key="early"]').click();
    const earlyView = activeWindow.locator('[data-round-view="early"]');
    if (!(await earlyView.isVisible()) || !(await earlyView.innerText()).includes("29 起")) throw new Error(`round industry interaction failed: ${config.name}`);
    await activeWindow.locator('[data-round-key="vc"]').click();
    const vcIndustryHref = await activeWindow.locator('[data-round-view="vc"] .round-industry-row').first().getAttribute('href');
    if (!vcIndustryHref?.includes("round_group=vc") || !vcIndustryHref?.includes("window=90")) throw new Error(`round industry event link failed: ${config.name}`);
    await page.goto(`http://127.0.0.1:8511${vcIndustryHref}`, { waitUntil: "networkidle" });
    const filteredText = await page.locator("body").innerText();
    if (!filteredText.includes("融资事件 · 生物制造与生命科学 · VC（Pre-A–B++） · 近90天") || !filteredText.includes("共15条")) throw new Error(`round industry event filtering failed: ${config.name}`);
    if (!(await page.locator(".company-cell small").first().isVisible())) throw new Error(`filtered event company profile missing: ${config.name}`);
    await page.screenshot({ path: path.join(out, `8511_round_industry_events_${config.name}.png`), fullPage: true });
    await page.goto("http://127.0.0.1:8511", { waitUntil: "domcontentloaded" });
    await page.locator("#monthly-capital-flow").waitFor();
    const repeatedHref = await page.locator('.capital-metrics a[href="/companies/repeated"]').first().getAttribute('href');
    if (repeatedHref !== "/companies/repeated") throw new Error(`repeated company metric link failed: ${config.name}`);
    await page.goto(`http://127.0.0.1:8511${repeatedHref}`, { waitUntil: "networkidle" });
    const repeatedText = await page.locator("body").innerText();
    if (!repeatedText.includes("谱星航天") || !repeatedText.includes("蓝固新能源") || !repeatedText.includes("已合并重复来源") || !repeatedText.includes("保留1个事件")) throw new Error(`repeated company page failed: ${config.name}`);
    const repeatedOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (repeatedOverflow) throw new Error(`repeated company horizontal overflow: ${config.name}`);
    await page.screenshot({ path: path.join(out, `8511_repeated_companies_${config.name}.png`), fullPage: true });
    await page.goto("http://127.0.0.1:8511", { waitUntil: "domcontentloaded" });
    await page.locator("#monthly-capital-flow").waitFor();
    if (text.includes("资本流向：资金由市场流入各产业领域")) throw new Error(`obsolete capital flow panel still visible: ${config.name}`);
    const homeOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (homeOverflow) throw new Error(`home horizontal overflow: ${config.name}`);
    const homeHeaders = await page.locator(".classified-table thead th").allTextContents();
    await page.goto("http://127.0.0.1:8511/events", { waitUntil: "networkidle" });
    const eventHeaders = await page.locator(".classified-table thead th").allTextContents();
    if (JSON.stringify(eventHeaders) !== JSON.stringify(homeHeaders)) throw new Error(`event headers differ from home: ${config.name}`);
    if (!(await page.locator(".company-cell small").first().isVisible())) throw new Error(`event company profile missing: ${config.name}`);
    if (!(await page.locator(".track-cell small").first().isVisible())) throw new Error(`event secondary field missing: ${config.name}`);
    await page.screenshot({ path: path.join(out, `8511_events_${config.name}.png`), fullPage: true });
    await page.goto("http://127.0.0.1:8511/taxonomy", { waitUntil: "networkidle" });
    if (await page.locator(".field-card").count() !== 10) throw new Error(`taxonomy card count failed: ${config.name}`);
    const firstIndustry = await page.locator(".field-card").first().getAttribute("href");
    await page.goto(`http://127.0.0.1:8511${firstIndustry}`, { waitUntil: "networkidle" });
    const firstTheme = await page.locator('.topic-links a').first().getAttribute('href');
    await page.goto(`http://127.0.0.1:8511${firstTheme}`, { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(out, `8511_theme_${config.name}.png`), fullPage: true });
    const themeText = await page.locator("body").innerText();
    if (!themeText.includes("唯一候选事件") || !themeText.includes("融资事件时间线")) throw new Error(`theme assertions failed: ${config.name}`);
    const themeHeaders = await page.locator(".classified-table thead th").allTextContents();
    if (JSON.stringify(themeHeaders) !== JSON.stringify(homeHeaders)) throw new Error(`theme headers differ from home: ${config.name}`);
    if (!(await page.locator(".event-detail .company-cell small").first().isVisible())) throw new Error(`theme company profile missing: ${config.name}`);
    if (!(await page.locator(".event-detail .track-cell small").first().isVisible())) throw new Error(`theme secondary field missing: ${config.name}`);
    const themeOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (themeOverflow) throw new Error(`theme horizontal overflow: ${config.name}`);
    results.push({ site: 8511, viewport: config.name, errors, homeOverflow, themeOverflow });
    await page.close();
  }
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto("http://127.0.0.1:8510", { waitUntil: "networkidle" });
  const body = await page.locator("body").innerText();
  if (!body.includes("V3.0分类与历史迁移")) throw new Error("8510 navigation does not expose V3.0 page");
  if (!body.includes("本月资本流向预览")) throw new Error("8510 navigation does not expose monthly capital preview");
  await page.screenshot({ path: path.join(out, "8510_home_desktop.png"), fullPage: true });
  results.push({ site: 8510, viewport: "desktop", navigationVisible: true });
  await page.close();
} finally {
  await browser.close();
}
await fs.writeFile(path.join(out, "results.json"), JSON.stringify(results, null, 2), "utf8");
console.log(JSON.stringify(results));
