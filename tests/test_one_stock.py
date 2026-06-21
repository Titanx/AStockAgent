"""单股快速测试 — 验证缓存机制"""
import os, sys, time, logging
from pathlib import Path

project_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_dir))

from config.default_config import get_config
from graph.trading_graph import AStockTradingGraph
from dataflows.akshare_adapter import get_latest_trade_date
from dataflows.market_cache import MarketDataCache

logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(message)s")

TRADE_DATE = get_latest_trade_date()
CACHE = MarketDataCache.get_instance()
CACHE.set_trade_date(TRADE_DATE)

print("=" * 60)
print(f"  单股测试 — 通威股份 (600438)")
print(f"  交易日: {TRADE_DATE}")
print("=" * 60)

print("\n📦 预加载缓存...")
preload_status = CACHE.preload(symbols=["600438"])
for m, s in preload_status.items():
    print(f"    {s} {m}")

print(f"\n📂 公共缓存: {CACHE.cache_dir}")
print(f"📂 舆情缓存: {CACHE.opinion_cache_dir}")
print(f"📂 个股缓存: {CACHE.stock_cache_dir}")

config = get_config()
config["debug"] = True
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1
config["enable_opinion_monitor"] = True

agent = AStockTradingGraph(config=config, debug=True)
print("\n🤖 Agent 就绪")

t0 = time.time()
result = agent.analyze("600438", TRADE_DATE, "通威股份")
elapsed = time.time() - t0

rating = result.get("rating", "?")
action = result.get("action", "?")
conf = result.get("confidence", 0)

emoji = {"Buy": "🟢", "Overweight": "🟡", "Hold": "⚪",
         "Underweight": "🟠", "Sell": "🔴"}.get(rating, "❓")

print(f"\n{'=' * 60}")
print(f"  {emoji} 评级={rating} 动作={action} 信心度={conf:.0%} 耗时={elapsed:.0f}s")
print(f"{'=' * 60}")

# 查看缓存文件
print(f"\n📂 缓存文件:")
for f in sorted(CACHE.cache_dir.glob("*.md")):
    size = f.stat().st_size
    print(f"    公共: {f.name} ({size:,} bytes)")
for d in sorted(CACHE.opinion_cache_dir.glob("*/")):
    count = len(list(d.glob("*.cache.json")))
    print(f"    舆情: {d.name}/ ({count} json)")
for d in sorted(CACHE.stock_cache_dir.glob("*/")):
    count = len(list(d.glob("*.cache.json")))
    print(f"    个股: {d.name}/ ({count} json)")

agent_cache_dir = project_dir / "data" / "agent_cache"
if agent_cache_dir.exists():
    print(f"\n📂 Agent 辩论轨迹:")
    for d in sorted(agent_cache_dir.glob("*/")):
        for f in sorted(d.glob("*.md")):
            size = f.stat().st_size
            print(f"    {d.name}/{f.name} ({size:,} bytes)")

print("\n✅ 测试完成")
