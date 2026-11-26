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
    await page.goto("http://127.0.0.1:8511", { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(out, `8511_home_${config.name}.png`), fullPage: true });
    const text = await page.locator("body").innerText();
    if (!text.includes("10个产业方向") || !text.includes("42个技术领域") || !text.includes("51个候选主题") || !text.includes("22 / 79 / 18") || !text.includes("97 / 0") || !text.includes("共97条")) throw new Error(`V3.2 home assertions failed: ${config.name}`);
    if (!text.includes("本月暂无人工确认的正式融资事件") || !text.includes("资本流向：资金由市场流入各产业领域")) throw new Error(`monthly capital flow empty state failed: ${config.name}`);
    if (await page.locator("#monthly-capital-flow .empty-industry-links a").count() !== 10) throw new Error(`monthly industry links failed: ${config.name}`);
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
