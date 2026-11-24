# 公开网站 MVP 修改文件

## 新增

- `funding_radar/public_service.py`：只读 Release 快照服务。
- `public_site/__init__.py`：公开站包入口。
- `public_site/app.py`：公开路由和页面结构。
- `public_site/static/site.css`：响应式视觉样式。
- `scripts/run_public_site.py`：8511 独立启动脚本。
- `tests/test_public_site.py`：公开端隔离、快照、撤回、路由和空状态测试。
- `tests/test_monthly_public_analysis.py`：自然月统计、去重、时区、筛选联动和 Release 隔离测试。
- `docs/screenshots/*`：浏览器验收截图及 JSON 结果。
- `docs/PUBLIC_*.md`：本轮实施、路由、架构、验收及修改清单。
- `docs/MONTHLY_ANALYSIS_IMPLEMENTATION.md`：首页月度分析改版说明。

## 修改

- `funding_radar/services.py`：未来 Release 事件快照冻结投资机构信息。
- `tests/test_ledger_v1.py`：适配并验证扩展后的快照内容。
- `requirements.txt`：加入公开站测试客户端依赖。

## 未修改

- `migrations/001_initial.sql`
- `migrations/002_stage_1_1.sql`
- 现有内部审核页面
- 原科研项目及其数据库
