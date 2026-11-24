from __future__ import annotations
import argparse
import gc

import pandas as pd
from pathlib import Path

from prepare_data import DEFAULT_END_DATE, DEFAULT_START_DATE

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = PROJECT_ROOT/"data"/"UserBehavior.csv"
DEFAULT_OUTPUT = PROJECT_ROOT/"data"/"cleaned_user_behavior.csv"
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_CHUNK_SIZE = 2_000_000  #每次读200万行,避免一次性加载1亿行爆内存
REQUIRED_COLUMNS = ["user_id", "item_id", "category_id", "behavior_type", "timestamp"]
NUMERIC_COLUMNS = ["user_id", "item_id", "category_id", "timestamp"]
LOW_CARDINALITY_COLUMNS = ["behavior_type", "date", "weekday", "behavior_name_en", "behavior_name_cn"]
OUTPUT_COLUMNS = ["user_id", "item_id", "category_id", "behavior_type", "timestamp",
                  "behavior_time", "date", "hour", "weekday",
                  "behavior_name_en", "behavior_name_cn"]
VALID_BEHAVIORS = {
    "pv": ("page_view", "浏览"),
    "fav": ("favorite", "收藏"),
    "cart": ("add_to_cart", "加购"),
    "buy": ("purchase", "购买"),
}
BEHAVIOR_EN = {k: v[0] for k, v in VALID_BEHAVIORS.items()}
BEHAVIOR_CN = {k: v[1] for k, v in VALID_BEHAVIORS.items()}

#分块读取,带表头时只读五列
def iter_behavior_chunks(input_path: Path, chunksize: int = DEFAULT_CHUNK_SIZE):
    preview = pd.read_csv(input_path, nrows=0)
    has_header = set(REQUIRED_COLUMNS).issubset(preview.columns)
    return pd.read_csv(
        input_path,
        header=0 if has_header else None,
        names=None if has_header else REQUIRED_COLUMNS,
        usecols=REQUIRED_COLUMNS if has_header else None,
        chunksize=chunksize,
    )

#单块清洗,只在一小片数据上操作,内存占用可控
def _clean_chunk(df: pd.DataFrame, start_ts, end_ts, timezone: str) -> pd.DataFrame:
    #1.去重(块内)
    df = df.drop_duplicates()

    #2.过滤必要字段缺失
    df = df.dropna(subset=REQUIRED_COLUMNS)

    #3.数值字段去掉空值与非法值
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=NUMERIC_COLUMNS)

    #4.行为类型标准化
    df["behavior_type"] = df["behavior_type"].astype(str).str.lower().str.strip()
    df = df[df["behavior_type"].isin(VALID_BEHAVIORS)]

    #5.时间戳转换
    df["behavior_time"] = (
        pd.to_datetime(df["timestamp"], unit="s", utc=True, errors="coerce")
        .dt.tz_convert(timezone)
        .dt.tz_localize(None)
    )
    df = df.dropna(subset=["behavior_time"])
    df = df[(df["behavior_time"] >= start_ts) & (df["behavior_time"] < end_ts)]

    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)



    #7.派生字段
    df["hour"] = df["behavior_time"].dt.hour.astype("int8")
    df["date"] = df["behavior_time"].dt.date.astype(str)
    df["weekday"] = df["behavior_time"].dt.day_name()
    df["behavior_name_en"] = df["behavior_type"].map(BEHAVIOR_EN)
    df["behavior_name_cn"] = df["behavior_type"].map(BEHAVIOR_CN)

    return df[OUTPUT_COLUMNS]

#清洗主流程
def clean_user_behavior(
        input_path: Path = DEFAULT_INPUT,
        output_path: Path = DEFAULT_OUTPUT,
        start_date: str = DEFAULT_START_DATE,
        end_date: str = DEFAULT_END_DATE,
        timezone: str = DEFAULT_TIMEZONE,
        chunksize: int = DEFAULT_CHUNK_SIZE,
        sort_output: bool = True,
        ) -> pd.DataFrame:

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)#终点为开区间，与 prepare_data / 质量核查共享同一口径

    original_rows = 0
    cleaned_rows = 0
    chunks = []

    for i, chunk in enumerate(iter_behavior_chunks(input_path, chunksize), start=1):
        original_rows += len(chunk)
        cleaned = _clean_chunk(chunk, start_ts, end_ts, timezone)
        cleaned_rows += len(cleaned)
        if not cleaned.empty:
            chunks.append(cleaned)
        del chunk, cleaned
        gc.collect()
        print(f"已处理第{i}块:累计读取{original_rows}行,保留{cleaned_rows}行")

    if chunks:
        df = pd.concat(chunks, ignore_index=True)
    else:
        df = pd.DataFrame(columns=OUTPUT_COLUMNS)
    del chunks
    gc.collect()

    #低基数字符串列转为category,1亿行的date/weekday/behavior列可省数GB内存
    for column in LOW_CARDINALITY_COLUMNS:
        df[column] = df[column].astype("category")

    #全局排序(内存开销较大,可用--no-sort跳过)
    if sort_output and not df.empty:
        df = df.sort_values(by=["behavior_time", "user_id", "item_id"], ignore_index=True)

    #输出
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"清洗完成,共读取{original_rows}行,保留{len(df)}行,移除{original_rows-len(df)}行")
    print(f"注:去重在各分块内完成,极端情况下跨块边界的重复行不会被去除")
    print(f"输出文件:{output_path}")

    return df

def main()->None:
    parser=argparse.ArgumentParser(description="清洗用户行为数据")
    parser.add_argument("--input",type=Path,default=DEFAULT_INPUT,help="输入文件路径")
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT,help="输出文件路径")
    parser.add_argument("--start_date",type=str,default=DEFAULT_START_DATE,help="开始日期（含）")
    parser.add_argument("--end_date",type=str,default=DEFAULT_END_DATE,help="结束日期（不含）")
    parser.add_argument("--timezone",default=DEFAULT_TIMEZONE,help="时区")
    parser.add_argument("--chunksize",type=int,default=DEFAULT_CHUNK_SIZE,help="每块行数,内存紧张时调小")
    parser.add_argument("--no-sort",dest="sort_output",action="store_false",help="跳过最终全局排序以节省内存")
    args=parser.parse_args()

    clean_user_behavior(
        input_path=args.input,
        output_path=args.output,
        start_date=args.start_date,
        end_date=args.end_date,
        timezone=args.timezone,
        chunksize=args.chunksize,
        sort_output=args.sort_output,
    )

if __name__=="__main__":
    main()
