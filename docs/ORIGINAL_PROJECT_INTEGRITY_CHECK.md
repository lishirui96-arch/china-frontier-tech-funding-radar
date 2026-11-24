# 原科研项目完整性校验

校验对象：`C:\Users\LSR\Documents\Codex\2026-11-18\ji\work\university-research-radar`。

开发前后结果一致：Git 工作区为空；commit 均为 `c5381f3c0c4b7d7373d2335bb3d07fc8f6b3e619`。

| 文件 | 开发前/后 SHA-256 |
|---|---|
| `streamlit_app.py` | `F5268F1083545EBD8C16B5DD14DFA749E5895426857B6D5FEC1ACE9647FB7730` |
| `storage.py` | `4349453CC68B16A3096DD59138489386DC4683B4ACC386F14B279684974C7F44` |
| `migrations.py` | `A013ABFA4D979DFD5AB81B5B280B22D6D9EB7276CB3F8D549AC38AD32F9F61F2` |
| `dashboard_repository.py` | `0B4CBFD6D3B1905A56D06DD06E4C7DE1E3897C15A89FC9CD689C426E314CB017` |

| 数据库 | 大小（字节） | 开发前/后 UTC 修改时间 |
|---|---:|---|
| `persistent/data/radar.db` | 479232 | `2026-11-23T03:06:25.2583955Z` |
| `work/v15-regional/radar-v15.db` | 548581376 | `2026-11-20T08:04:41.0443531Z` |
| `work/citation-ui-test-v2.db` | 552472576 | `2026-11-24T03:18:57.1470460Z` |
| `work/citation-ui-test.db` | 548618240 | `2026-11-23T08:02:21.4447311Z` |

新项目的数据库保护还会拒绝路径中包含 `university-research-radar` 或文件名为 `radar.db` 的连接，包括只读/写入入口，防止误配置。
