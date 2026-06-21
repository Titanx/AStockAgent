"""快速验证 sector 历史数据完整性"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from dataflows.market_cache import MarketDataCache
from dataflows.akshare_adapter import get_latest_trade_date

today = get_latest_trade_date()
cache = MarketDataCache.get_instance()
cache.set_trade_date(today)
cache.preload()

# 检查历史
h = cache.get_history("get_sector_boards", days=10)
print(f"内存中 {len(h)} 天 sector 数据\n")

for item in h:
    d = item["data"]
    dates = item["date"]
    up = sum(1 for r in d if r.get("涨跌幅", 0) > 0)
    down = sum(1 for r in d if r.get("涨跌幅", 0) < 0)
    s = sorted(d, key=lambda r: r.get("涨跌幅", 0), reverse=True)
    top = s[:3]
    bot = s[-3:]
    print(f"{dates} | {len(d)}板块 | ↑{up} ↓{down}")
    for r in top:
        print(f"  🟢 {r['板块']:10s} {r['涨跌幅']:+.2f}")
    for r in bot:
        print(f"  🔴 {r['板块']:10s} {r['涨跌幅']:+.2f}")
    print()

# 磁盘文件统计
md = sorted(cache.cache_dir.glob("*_get_sector_boards.md"))
jc = sorted(cache.cache_dir.glob("*_get_sector_boards.cache.json"))
print(f"磁盘: {len(md)} MD + {len(jc)} JSON, {md[0].name[:10]} ~ {md[-1].name[:10]}")
print("✅ 完成")
