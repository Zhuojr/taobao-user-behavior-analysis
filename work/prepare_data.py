from __future__ import annotations
import argparse
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = PROJECT_ROOT/"data"/"sample_100k.csv"
DEFAULT_OUTPUT = PROJECT_ROOT/"data"/"cleaned_user_behavior.csv"
DEFAULT_TIMEZONE = "Asia/Shanghai"
#分析窗口口径（全项目唯一出处）：起点含当日 00:00，终点为开区间（不含当日），
#即默认窗口 [2017-11-25, 2017-12-04)，数据实际覆盖 2017-11-25 至 2017-12-03。
#清洗（prepare_data / prepare_big_data）与质量核查（generate_reports）共用这两个常量。
DEFAULT_START_DATE = "2017-11-25"
DEFAULT_END_DATE = "2017-12-04"
REQUIRED_COLUMNS = ["user_id", "item_id", "category_id", "behavior_type", "timestamp"]
VALID_BEHAVIORS = {
    "pv": ("page_view", "浏览"),
    "fav": ("favorite", "收藏"),
    "cart": ("add_to_cart", "加购"),
    "buy": ("purchase", "购买"),
}

#读取行为数据,带表头时只读五列
def read_behavior_data(input_path: Path) -> pd.DataFrame:
    preview=pd.read_csv(input_path,nrows=0)

    if set(REQUIRED_COLUMNS).issubset(preview.columns):
        return pd.read_csv(input_path,usecols=REQUIRED_COLUMNS)
    else:
        return pd.read_csv(input_path, header=None, names=REQUIRED_COLUMNS)

#清洗
def clean_user_behavior(
        input_path: Path = DEFAULT_INPUT,
        output_path: Path = DEFAULT_OUTPUT,
        start_date: str = DEFAULT_START_DATE,
        end_date: str = DEFAULT_END_DATE,
        timezone: str = DEFAULT_TIMEZONE,)-> pd.DataFrame:

    df=read_behavior_data(input_path)
    original_rows = len(df)#记录清洗行数

    #1.去重
    df=df.drop_duplicates()

    #2.过滤必要字段缺失
    df=df.dropna(subset=REQUIRED_COLUMNS)

    #3.数值字段去掉空值与非法值
    for column in ["user_id", "item_id", "category_id","timestamp"]:
        df[column]=pd.to_numeric(df[column],errors="coerce")#把非法值统一为nan

    df=df.dropna(subset=["user_id", "item_id", "category_id","timestamp"])

    #4标准化
    df["behavior_type"]=df["behavior_type"].astype(str).str.lower().str.strip()
    df=df[df["behavior_type"].isin(VALID_BEHAVIORS)]

    #5.时间戳转换
    df["behavior_time"]=(
        pd.to_datetime(df["timestamp"],unit="s",utc=True,errors="coerce")
        .dt.tz_convert(timezone)
        .dt.tz_localize(None)
    )
    df=df.dropna(subset=["behavior_time"])

    start_ts=pd.Timestamp(start_date)
    end_ts=pd.Timestamp(end_date)#终点为开区间，与其他脚本共享同一口径
    df=df[(df["behavior_time"]>=start_ts)&(df["behavior_time"]<end_ts)]

    #6.添加新字段
    for column in ["user_id", "item_id", "category_id","timestamp"]:
        df[column]=df[column].astype("int64")
    df["date"]=df["behavior_time"].dt.date.astype(str)
    df["hour"]=df["behavior_time"].dt.hour
    df["weekday"] = df["behavior_time"].dt.day_name()
    df["behavior_name_en"] = df["behavior_type"].map(lambda x: VALID_BEHAVIORS[x][0])
    df["behavior_name_cn"] = df["behavior_type"].map(lambda x: VALID_BEHAVIORS[x][1])

    #7.输出
    ordered_column=["user_id", "item_id", "category_id", "behavior_type", "timestamp",
                    "behavior_time", "date", "hour", "weekday",
                    "behavior_name_en", "behavior_name_cn"]
    df=df[ordered_column].sort_values(by=["behavior_time","user_id","item_id"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(output_path,index=False)

    print(f"清洗完成，共{original_rows}行，清洗后{len(df)}行")
    print(f"清洗行数，共{len(df)}行")
    print(f"移除行数，共{original_rows-len(df)}行")
    print(f"输出文件：{output_path}")

    return df

def main()->None:
    parser=argparse.ArgumentParser(description="清洗用户行为数据")
    parser.add_argument("--input",type=Path,default=DEFAULT_INPUT,help="输入文件路径")
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT,help="输出文件路径")
    parser.add_argument("--start_date",type=str,default=DEFAULT_START_DATE,help="开始日期（含）")
    parser.add_argument("--end_date",type=str,default=DEFAULT_END_DATE,help="结束日期（不含）")
    parser.add_argument("--timezone",default=DEFAULT_TIMEZONE,help="时区")
    args=parser.parse_args()

    clean_user_behavior(
        input_path=args.input,
        output_path=args.output,
        start_date=args.start_date,
        end_date=args.end_date,
        timezone=args.timezone,
    )

if __name__=="__main__":
    main()