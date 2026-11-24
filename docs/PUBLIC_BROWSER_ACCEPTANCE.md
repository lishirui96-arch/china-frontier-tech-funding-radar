# 公开网站浏览器验收报告

验收环境：Microsoft Edge（Playwright 驱动），公开端 `127.0.0.1:8511`，内部端 `127.0.0.1:8510`。

## 结果

| 检查项 | 结果 |
|---|---|
| 桌面首页 1440×1000 | 200，无横向溢出、控制台错误或失败资源 |
| 手机首页 390×844 | 200，无横向溢出、控制台错误或失败资源 |
| 六大学科页 | 200，无溢出或资源错误 |
| 数据说明页 | 200，无溢出或资源错误 |
| 90/360 天切换 | 正常，360 天页面显示“近 360 天” |
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

截图为全页真实浏览器渲染，不是设计稿。
