"""batch_predict.py — 批量预测统一入口 (并发 + 增量 + 大盘预加载 + 日期参数)

用法:
  python scripts/batch_predict.py                           # 今天 → 下一交易日
  python scripts/batch_predict.py 2026-06-26                # 指定日期 → 下一交易日
  python scripts/batch_predict.py 2026-06-26 --fresh         # 强制重跑全部

特性:
  - 并发: 5 workers 并行分析 (I/O 密集, ~5x 提速)
  - 增量: 跳过已有结果的股票 (rating != ERR)
  - 大盘预加载: 上证/深证/创业板 + 市场情绪 + 北向资金 只拉一次
  - 共享上下文: market_overview + sector_context 注入每个 agent 的 prompt
"""

import sys, time, os, logging, json, argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from collections import defaultdict

project_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_dir))
sys.path.insert(0, str(project_dir / "libs"))

from dotenv import load_dotenv
load_dotenv(project_dir / ".env", override=True)

logging.basicConfig(level=logging.WARNING, format="%(levelname)-5s %(message)s")

from config.default_config import get_config
from graph.trading_graph import AStockTradingGraph
from scripts.stock_universe import stocks_for_batch_predict
from scripts.market_overview import load_overview, overview_to_prompt
from dataflows.market_cache import MarketDataCache

ALL_STOCKS = stocks_for_batch_predict()

SECTOR_DESCRIPTIONS = {
    "光伏": "新能源光伏产业链，受政策补贴、海外需求、硅料价格影响。近期板块波动较大，关注超跌反弹信号。",
    "风电": "风力发电设备产业链，受益于碳中和政策，关注海上风电招标和原材料价格。",
    "AI": "人工智能/算力芯片板块，受AI应用落地、国产替代、海外芯片禁令影响。高波动高弹性。",
    "储能": "储能电池产业链，新能源配套刚需，关注宁德时代产业链延伸和锂价走势。",
    "视觉": "计算机视觉/安防/车载视觉板块，受智慧城市、自动驾驶、AI+应用落地驱动。",
}


def is_done(code, trade_date):
    cache_file = project_dir / "data" / "results" / f"{code}_{trade_date}_analysis.cache.json"
    if cache_file.exists():
        try:
            d = json.loads(cache_file.read_text("utf-8"))
            if d.get("rating", "ERR") != "ERR":
                return True, d["rating"]
        except:
            pass
    return False, None


def get_next_trade_date(date_str: str) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d")
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description="批量一日游预测")
    parser.add_argument("date", nargs="?", default="auto", help="分析日期 (YYYY-MM-DD), 默认今天")
    parser.add_argument("--fresh", action="store_true", help="强制重跑所有股票")
    parser.add_argument("--workers", type=int, default=5, help="并发数 (默认5)")
    parser.add_argument("--no-overview", action="store_true", help="跳过大盘预加载")
    args = parser.parse_args()

    if args.date == "auto":
        from datetime import datetime
        trade_date = datetime.now().strftime("%Y-%m-%d")
    else:
        trade_date = args.date

    next_date = get_next_trade_date(trade_date)

    # --- Skip completed ---
    skipped = []
    todo = []
    for code, name, sector in ALL_STOCKS:
        if args.fresh:
            todo.append((code, name, sector))
        else:
            done, rating = is_done(code, trade_date)
            if done:
                skipped.append((code, name, sector, rating))
            else:
                todo.append((code, name, sector))

    print("=" * 60)
    print(f"📅 交易日: {trade_date} → {next_date}")
    print(f"📊 总股票: {len(ALL_STOCKS)} | 跳过: {len(skipped)} | 待跑: {len(todo)} | 🔥 {args.workers} workers")
    print("=" * 60)

    if not todo:
        print("全部完成！")
        return

    # --- Phase 0: Market Overview (once) ---
    config = get_config()
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1

    if not args.no_overview:
        print("\n📊 Phase 0: 大盘数据预加载 ...")
        overview = load_overview(trade_date)
        shared_overview = overview_to_prompt(overview)
        idx_parts = []
        for k, v in overview.get('indices', {}).items():
            idx_parts.append(f"{k}({v.get('close', '?')})")
        print(f"   指数: {', '.join(idx_parts)}")
        print("=" * 60)

        # Preload stock price data (一次拉全部50只)
        cache = MarketDataCache.get_instance()
        cache.set_trade_date(trade_date)
        symbols = [c for c, n, s in ALL_STOCKS]
        print(f"📂 预加载 {len(symbols)} 只股票日线数据 ...")
        cache.preload_stock_data(symbols)
        cache.load_stock_price_history(symbols, days=30)
    else:
        shared_overview = ""

    # --- Phase 1: Concurrent Analysis ---
    print("\n🚀 Phase 1: 并发分析 ...\n")
    print_lock = Lock()
    results = []
    start_time = time.time()

    def analyze_one(code, name, sector, idx, total):
        t0 = time.time()
        cfg = dict(config)
        cfg["market_overview"] = shared_overview
        cfg["sector_context"] = SECTOR_DESCRIPTIONS.get(sector, "")
        try:
            agent = AStockTradingGraph(config=cfg)
            result = agent.analyze(symbol=code, trade_date=trade_date, stock_name=name)
            dt = time.time() - t0
            rating = result.get("rating", "?")
            conf = result.get("confidence", 0)
            with print_lock:
                elapsed = time.time() - start_time
                eta = (elapsed / max(idx, 1)) * (total - idx) if idx > 0 else 0
                print(f"[{idx:2d}/{total}] {code} {name} ({sector}) → {rating} ({conf:.0%}) ⏱{dt:.0f}s | ETA {eta/60:.0f}min")
            return {"code": code, "name": name, "sector": sector, "rating": rating, "conf": conf, "ok": True}
        except Exception as e:
            dt = time.time() - t0
            with print_lock:
                print(f"[{idx:2d}/{total}] {code} {name} ({sector}) → ❌ {str(e)[:80]} ⏱{dt:.0f}s")
            return {"code": code, "name": name, "sector": sector, "rating": "ERR", "conf": 0, "ok": False}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for i, (code, name, sector) in enumerate(todo):
            fut = executor.submit(analyze_one, code, name, sector, i + 1, len(todo))
            futures[fut] = (code, name, sector)
        for fut in as_completed(futures):
            results.append(fut.result())

    total_t = (time.time() - start_time) / 60
    ok_count = sum(1 for r in results if r["ok"])

    # --- Summary ---
    all_results = [{"code": c, "name": n, "sector": s, "rating": r, "conf": 0, "ok": True} for c,n,s,r in skipped]
    all_results += results
    by_rating = defaultdict(int)
    for r in all_results:
        by_rating[r["rating"]] += 1

    print("\n" + "=" * 60)
    print(f"📊 {trade_date} → {next_date} 预测 ({len(all_results)}只) | 耗时: {total_t:.1f}min | 成功: {ok_count}/{len(todo)}")
    for rating in ["Buy", "Overweight", "Hold", "Underweight", "Sell", "ERR"]:
        if by_rating[rating]:
            emoji = {"Buy": "🟢", "Overweight": "🟡", "Hold": "⚪", "Underweight": "🟠", "Sell": "🔴", "ERR": "❌"}[rating]
            print(f"  {emoji} {rating}: {by_rating[rating]} 只")

    for rating in ["Buy", "Overweight", "Hold", "Underweight", "Sell", "ERR"]:
        if by_rating[rating]:
            items = [r for r in all_results if r["rating"] == rating]
            print(f"\n{rating}:")
            for r in items:
                print(f"  {r['code']} {r['name']} ({r['sector']}) conf={r['conf']:.0%}")


if __name__ == "__main__":
    main()
