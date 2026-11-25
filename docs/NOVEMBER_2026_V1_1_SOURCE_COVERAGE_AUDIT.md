# V1.1 来源覆盖审计报告

审计窗口：2026-11-01 至 2026-11-25。采集日期：2026-11-25。

## 投资界完整分页

robots.txt 明确 `allow:/`。采用低频公开HTML访问；连续两页均早于窗口或页面无文章后停止。窗口内共保存155篇去重来源文档，正文可访问155篇。

| 栏目 | 已遍历页数 | 页面文章数合计 | 最早日期 | 最晚日期 | 失败页数 |
|---|---:|---:|---|---|---:|
| angel_early | 2 | 40 | 2024-10-18 | 2026-10-27 | 0 |
| funding_major | 9 | 180 | 2026-10-22 | 2026-11-25 | 0 |
| investment_events | 9 | 180 | 2026-10-26 | 2026-11-25 | 0 |
| ma_events | 3 | 60 | 2025-12-11 | 2026-11-16 | 0 |

栏目成员数：融资大事件132、投资事件125、天使/早期0、并购4。同一文章可属于多个栏目，不能直接相加。天使/早期入口最新文章为2026-10-27，因此窗口内为0，不是解析遗漏。

目标科技轮次候选89条，其中与V1.0重复17条，新增候选72条。新增候选尚未经过人工双审，未写入正式融资事件表，也未进入公开站。

## SpaceDaily技术审计

- robots允许公开页面；首页公开HTML直接包含550条记录。
- 2026-11-01至25日记录95条，标记中国84条，目标或待审轮次73条。
- 未发现公开JSON API、公开API文档或公开导出；完整导出/API指向机构版，因此未访问受限功能。
- 73个原始链接中58个正文可访问，15个不可访问或内容不足。
- 已发现企业名截断、海外项目误标中国、日期含义不一、轮次/金额/币种可能错误等问题。全部仅作线索。

## 其他公开来源域名

SpaceDaily公开记录指向的原始来源分布如下；这反映发现渠道，不等于核验通过。

| 来源域名 | 原始URL数 |
|---|---:|
| news.qq.com | 20 |
| www.msn.cn | 12 |
| www.sohu.com | 10 |
| www.unite.ai | 4 |
| finance.sina.com.cn | 4 |
| www.36kr.com | 3 |
| www.163.com | 2 |
| news.pedaily.cn | 2 |
| www.taibo.cn | 1 |
| www.chinastarmarket.cn | 1 |
| www.techflowpost.com | 1 |
| www.yicai.com | 1 |
| www.guandian.cn | 1 |
| www.ithome.com | 1 |
| www.zqrb.cn | 1 |
| feng.ifeng.com | 1 |
| view.inews.qq.com | 1 |
| www.thepaper.cn | 1 |
| www.ednchina.com | 1 |
| bydrug.pharmcube.com | 1 |
| www.c114.com.cn | 1 |
| finance.eastmoney.com | 1 |
| www.szhzxw.cn | 1 |
| www.stnn.cc | 1 |

## 交叉覆盖

SpaceDaily与投资界按原始URL直接重合数量：2。企业名、日期和轮次的模糊重合仍需人工判断，不能仅凭聚合器字段自动合并。
