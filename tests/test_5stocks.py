"""5股一日游策略测试"""
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

# 选5股：储能/光伏/AI/风电/视觉各1
TEST_STOCKS = [
    ("300750", "宁德时代", "储能"),
    ("600438", "通威股份", "光伏"),
    ("300033", "同花顺", "AI"),
    ("002202", "金风科技", "风电"),
    ("002415", "海康威视", "视觉"),
]

print("=" * 60)
print(f"  5股一日游策略测试")
print(f"  交易日: {TRADE_DATE}")
print("=" * 60)

symbols = [s[0] for s in TEST_STOCKS]

print("\n📦 预加载缓存...")
preload_status = CACHE.preload(symbols=symbols)
for m, s in preload_status.items():
    print(f"    {s} {m}")

config = get_config()
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1

print("\n" + "=" * 60)
print(f"  开始分析 5 只股票...")
print("=" * 60)

for symbol, name, sector in TEST_STOCKS:
    print(f"\n{'─' * 50}")
    print(f"  🎯 {symbol} {name} [{sector}]")
    print(f"{'─' * 50}")

    t0 = time.time()
    try:
        graph = AStockTradingGraph(config=config)
        result = graph.analyze(
            symbol=symbol,
            trade_date=TRADE_DATE,
            stock_name=name,
        )
        elapsed = time.time() - t0

        rating = result.get("rating", "?")
        confidence = result.get("confidence", 0)
        action = result.get("action", "?")
        debate = result.get("debate_rounds", "?")
        risk = result.get("risk_rounds", "?")
        decision_text = result.get("decision", "")

        # 提取核心论题
        import re, json
        logic = ""
        try:
            t = decision_text.strip()
            t = re.sub(r"^```json\s*", "", t)
            t = re.sub(r"\s*```$", "", t)
            obj = json.loads(t)
            dec = obj.get("decision", obj)
            logic = dec.get("executive_summary") or dec.get("investment_thesis") or dec.get("investment_logic") or ""
        except:
            pass
        if len(logic) > 120:
            logic = logic[:117] + "..."

        print(f"  📊 评级: {rating} | 动作: {action} | 信心度: {confidence:.0%}")
        print(f"  🎯 预期涨 ≥1%: {'✅' if confidence >= 0.5 else '❌'} (信心度 {confidence:.0%})")
        print(f"  💬 辩论轮: {debate} | 风险轮: {risk}")
        if logic:
            print(f"  💡 {logic}")
        print(f"  ⏱️ 耗时: {elapsed:.0f}s")

    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ❌ 失败 ({elapsed:.0f}s): {e}")

print("\n" + "=" * 60)
print("  5股测试完成 ✅")
print("=" * 60)
