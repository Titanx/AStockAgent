"""股票池 — 5 板块 × 5 只 = 25 只 A股

格式: (代码_前缀, 名称, 板块)
  - run_batch_date / collector 使用 sh/sz 前缀版本
  - batch_predict 使用 6 位纯数字版本
"""

STOCK_UNIVERSE = [
    ("600438", "通威股份", "光伏"),
    ("601012", "隆基绿能", "光伏"),
    ("300274", "阳光电源", "光伏"),
    ("300751", "迈为股份", "光伏"),
    ("002459", "晶澳科技", "光伏"),

    ("002202", "金风科技", "风电"),
    ("601615", "明阳智能", "风电"),
    ("603606", "东方电缆", "风电"),
    ("300850", "新强联",   "风电"),
    ("300129", "泰胜风能", "风电"),

    ("002230", "科大讯飞", "AI"),
    ("688256", "寒武纪",   "AI"),
    ("300308", "中际旭创", "AI"),
    ("300033", "同花顺",   "AI"),
    ("688041", "海光信息", "AI"),

    ("300750", "宁德时代", "储能"),
    ("300014", "亿纬锂能", "储能"),
    ("002074", "国轩高科", "储能"),
    ("300438", "鹏辉能源", "储能"),
    ("300073", "当升科技", "储能"),

    ("002415", "海康威视", "视觉"),
    ("002236", "大华股份", "视觉"),
    ("603501", "韦尔股份", "视觉"),
    ("002456", "欧菲光",   "视觉"),
    ("688400", "凌云光",   "视觉"),
]


def stocks_for_collector():
    """collector.py 格式 (sh/sz 前缀, 英文名, 英文板块)"""
    name_map = {
        "通威股份": "Tongwei", "隆基绿能": "LONGi", "阳光电源": "Sungrow",
        "迈为股份": "Maxwell", "晶澳科技": "JA",
        "金风科技": "Goldwind", "明阳智能": "MingYang", "东方电缆": "OrientCable",
        "新强联": "Xinqianglian", "泰胜风能": "TSP",
        "科大讯飞": "iFlytek", "寒武纪": "Cambricon",
        "中际旭创": "Zhongji", "同花顺": "Hithink", "海光信息": "Hygon",
        "宁德时代": "CATL", "亿纬锂能": "EVE", "国轩高科": "Guoxuan",
        "鹏辉能源": "GreatPower", "当升科技": "Easpring",
        "海康威视": "Hikvision", "大华股份": "Dahua",
        "韦尔股份": "WillSemi", "欧菲光": "OFilm", "凌云光": "Luster",
    }
    sector_map = {"光伏": "Solar", "风电": "Wind", "AI": "AI", "储能": "Energy", "视觉": "Vision"}

    result = []
    for code, name, sector in STOCK_UNIVERSE:
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        result.append(("{}{}".format(prefix, code), name_map.get(name, name), sector_map.get(sector, sector)))
    return result


def stocks_for_batch_predict():
    """batch_predict.py 格式 (纯 6 位代码, 中文名, 中文板块)"""
    return list(STOCK_UNIVERSE)
