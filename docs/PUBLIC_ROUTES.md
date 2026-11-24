# 公开网站路由清单

| 路由 | 页面 | 当前空数据行为 |
|---|---|---|
| `/` | 首页 | 展示审核中说明及各模块空状态 |
| `/fields` | 六大学科 | 展示既定六学科入口 |
| `/fields/{field_id}` | 学科详情 | 无发布事件时显示空状态 |
| `/tracks` | 融资赛道 | 不生成虚构排名 |
| `/tracks/{topic_id}` | 赛道详情 | 无有效主题时显示空状态 |
| `/emerging` | 新兴方向 | 等待后续动态主题结果 |
| `/companies` | 企业库 | 只展示 Release 企业 |
| `/companies/{company_id}` | 企业详情 | 未发布主体不可见 |
| `/investors` | 投资机构 | 只展示 Release 投资机构 |
| `/investors/{investor_id}` | 投资机构详情 | 未发布机构不可见 |
| `/events` | 融资事件 | 只展示唯一已发布事件 |
| `/events/{event_id}` | 融资事件详情 | 非有效 Release 事件不可见 |
| `/methodology` | 数据说明 | 展示口径、证据、去重和审核规则 |
| `/search?q=...` | 全站搜索 | 只搜索有效 Release 快照 |

所有导航与返回链接均经过浏览器验证。`/favicon.ico` 返回空的 204 响应，避免无意义的资源错误。
