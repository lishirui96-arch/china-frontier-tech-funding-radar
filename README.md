# 中国前沿科技融资热点雷达 - 融资事件账本 V1

阶段 0/1 的本地内部审核系统。它不是公开市场榜单，不进行动态主题聚类，也不连接原科研热点数据库。

## 运行

```powershell
.\.venv\Scripts\python -m scripts.migrate
.\.venv\Scripts\python -m scripts.seed_experimental_samples
.\.venv\Scripts\python -m streamlit run app\Home.py --server.port 8510
```

数据库路径只读取 `FUNDING_RADAR_DB_PATH`；缺省为 `data/funding_radar.db`。

