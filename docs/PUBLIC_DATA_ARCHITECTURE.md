# 公开端数据读取架构

## 边界

`public_site/app.py` 只负责公开路由和 HTML 渲染；`funding_radar/public_service.py` 是公开端唯一数据入口；内部审核页面及服务保持独立。

## 读取链路

1. 使用 SQLite URI `mode=ro` 建立只读连接。
2. 从 `releases` 读取发布记录。
3. 结合 `release_status_history` 的最新状态筛除已撤回或已取代 Release。
4. 仅从选中 Release 的不可变 `release_events` 快照生成指标、列表、详情与搜索结果。
5. 没有有效 Release 时返回结构化空结果，由页面统一展示空状态。

公开服务不查询 `raw_documents`、提取候选、审核人、审计日志或未发布证据，也没有写入方法。

## 快照不可变性

新建 Release 时，事件快照同时冻结投资机构信息。Release 生成后，即使内部业务表继续修改，公开结果仍来自原快照。状态变化通过 `release_status_history` 追加记录；撤回不会修改快照内容，但会使该 Release 退出公开选择。

## 金额与计数

- 事件数：Release 中唯一事件数。
- 企业数：快照企业去重数。
- 投资机构数：快照投资机构去重数。
- 精确金额：仅汇总 `exact` 且非累计的金额；不使用区间中点。
- 页面一次请求只使用一个有效 Release，避免跨版本混算。

## 月度分析

`PublicDataService.monthly_analysis()` 统一生成自然月堆叠数据、投资机构排名、筛选后的事件明细及分页信息。公布时间先转换为中国标准时间；图表、排名和表格使用同一组筛选条件与同一 Release。未验证覆盖的月份不会自动补零。
