# 公开网站浏览器验收报告

验收环境：Microsoft Edge（Playwright 驱动），公开端 `127.0.0.1:8511`，内部端 `127.0.0.1:8510`。

## 结果

| 检查项 | 结果 |
|---|---|
| 桌面首页 1440×1000 | 200，无横向溢出、控制台错误或失败资源 |
| 手机首页 390×844 | 200，无横向溢出、控制台错误或失败资源 |
| 六大学科页 | 200，无溢出或资源错误 |
| 数据说明页 | 200，无溢出或资源错误 |
| 自然月分析区 | 左侧月度事件、右侧活跃投资方、下方事件明细均存在且联动空状态正常 |
| 旧滚动窗口 | 页面不再出现 90/360 天按钮、文案或查询逻辑 |
| 搜索 | 正常，只返回真实 Release 结果；当前显示空状态 |
| 赛道/新兴方向/企业/机构/事件详情 | 均返回 200 和真实空状态 |
| 虚构数据检查 | 未发现随机趋势、虚构 TOP 10、企业、机构或事件 |
| 内部审核站健康检查 | `/_stcore/health` 返回 200 和 `ok` |

机器可读结果见 `docs/screenshots/browser-audit.json`。

## 截图

- `docs/screenshots/home-desktop.png`
- `docs/screenshots/home-mobile.png`
- `docs/screenshots/fields-desktop.png`
- `docs/screenshots/methodology-desktop.png`
- `docs/screenshots/filters-empty.png`
- `docs/screenshots/monthly-chart-empty.png`
- `docs/screenshots/active-investors-empty.png`
- `docs/screenshots/event-table-empty.png`

截图为全页真实浏览器渲染，不是设计稿。

真实数据库当前没有有效 Release，因此没有可点击的真实月份柱或赛道。月份点击、赛道筛选、投资方排名与事件表联动由临时测试数据库验证；未用模拟数据制作对外截图。
