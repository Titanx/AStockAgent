import json, pathlib
d = pathlib.Path(r"c:\Users\44263\Documents\xhl\skills\量化交易\AStockAgent\data\results")
files = list(d.glob("*2026-06-22*_analysis.cache.json"))
for f in sorted(files):
    data = json.loads(f.read_text(encoding="utf-8"))
    print(f"  {data['symbol']}: {data['rating']:12s} conf={data['confidence']:.0%}")
print(f"\n{len(files)}/25")
