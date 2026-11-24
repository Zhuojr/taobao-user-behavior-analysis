from __future__ import annotations
from pathlib import Path
import pandas as pd

from data_analysis import (
   DEFAULT_INPUT,
   high_value_users,
   load_data,
   user_item_sequential_funnel,
)
from prepare_data import DEFAULT_END_DATE,DEFAULT_START_DATE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BI_OUTPUT_DIR = PROJECT_ROOT / "data" / "bi"

#行为维度：sort_order 即漏斗顺序，Power BI 中用于"按列排序"漏斗视觉对象
DIM_BEHAVIOR = pd.DataFrame(
    {
        "behavior_type": ["pv", "fav", "cart", "buy"],
        "behavior_name_en": ["page_view", "favorite", "add_to_cart", "purchase"],
        "behavior_name_cn": ["浏览", "收藏", "加购", "购买"],
        "sort_order": [1, 2, 3, 4],
    }
)

def build_fact(df:pd.DataFrame)->pd.DataFrame:
    """事实表：明细瘦身。timestamp/行为名称/weekday 挪到维度表，fact 只留外键与度量。"""
    fact=df[
        ["user_id","item_id","category_id","behavior_type","behavior_time","date","hour"]
    ].copy()

    fact["behavior_time"]=fact["behavior_time"].astype(str)

    return fact

def build_dim_date(df:pd.DataFrame)->pd.DataFrame:
    """日期维度：从明细日期派生。date 保持 YYYY-MM-DD 字符串，作关系键。"""
    dates=pd.to_datetime(pd.Series(df["date"].unique()))
    dim=pd.DataFrame({"date":dates.dt.strftime("%Y-%m-%d")})
    dim["weekday"]=dates.dt.day_name()
    dim["weekday_no"]=dates.dt.dayofweek+1# ISO 口径：周一=1 ... 周日=7
    dim["is_weekend"] = dim["weekday_no"] >= 6

    return dim.sort_values("date").reset_index(drop=True)

def build_agg_funnel(df: pd.DataFrame) -> pd.DataFrame:
    """严格顺序漏斗预聚合：转长表 metric_name/metric_value，键名与 SQL 端一致，便于对照验证。"""
    funnel = user_item_sequential_funnel(df)
    return pd.DataFrame(
        {"metric_name": list(funnel.keys()), "metric_value": list(funnel.values())}
    )

def build_agg_user_value(df: pd.DataFrame) -> pd.DataFrame:
    """用户价值预聚合：导出全部购买用户（而非仅 Top N），看板里才能动态筛选 Top N。"""
    return high_value_users(df, top_n=df["user_id"].nunique())[
        [
            "user_id",
            "purchase_count",
            "distinct_items_bought",
            "distinct_categories_bought",
            "active_days",
            "value_score",
        ]
    ]

def validate(tables:dict[str,pd.DataFrame],df:pd.DataFrame)->None:
    """导出前自检：任何一项失败说明口径被改动，先修再导（作用等同 pytest）。"""
    fact=tables["fact_user_behavior.csv"]
    dim_date=tables["dim_date.csv"]
    dim_behavior=tables["dim_behavior.csv"]
    agg_funnel=tables["agg_strict_funnel.csv"]

    # 1. 事实表行数必须与清洗数据一致（导出只瘦身、不过滤）
    assert len(fact) == len(df), f"fact 行数 {len(fact)} != 清洗数据 {len(df)}"

    # 2. 日期维度：行数 = 窗口天数，且落在共享常量窗口内
    expected_days = (pd.Timestamp(DEFAULT_END_DATE) - pd.Timestamp(DEFAULT_START_DATE)).days
    assert len(dim_date) == expected_days, f"dim_date {len(dim_date)} 天 != 窗口 {expected_days} 天"
    assert dim_date["date"].iloc[0] >= DEFAULT_START_DATE
    assert dim_date["date"].iloc[-1] < DEFAULT_END_DATE

    # 3. 行为维度：4 种行为、sort_order 唯一
    assert len(dim_behavior) == 4 and dim_behavior["sort_order"].is_unique

    # 4. 漏斗比率指标必须落在 [0, 1]
    rates = agg_funnel.loc[agg_funnel["metric_name"].str.contains("rate"), "metric_value"]
    assert rates.between(0, 1).all(), "漏斗比率指标越界"

def main() -> None:
    df = load_data(DEFAULT_INPUT)

    tables: dict[str, pd.DataFrame] = {
        "fact_user_behavior.csv": build_fact(df),
        "dim_date.csv": build_dim_date(df),
        "dim_behavior.csv": DIM_BEHAVIOR,
        "agg_strict_funnel.csv": build_agg_funnel(df),
        "agg_user_value.csv": build_agg_user_value(df),
    }

    validate(tables, df)

    BI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    #utf-8-sig：带 BOM，Windows 下的 Power Query 读中文列名不乱码
    for name, table in tables.items():
        table.to_csv(BI_OUTPUT_DIR / name, index=False, encoding="utf-8-sig")
        print(f"EXPORTED {name}: {len(table):,} rows")

    print(f"All BI tables exported under {BI_OUTPUT_DIR}")


if __name__ == "__main__":
    main()





