import sqlite3
from pathlib import Path
import pandas as pd

PROJECT_ROOT=Path(__file__).resolve().parents[1]
CSV_PATH=PROJECT_ROOT/"data"/"cleaned_user_behavior.csv"
DB_PATH=PROJECT_ROOT/"data"/"user_behavior.db"

def main()->None:
    conn=sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS user_behavior;")
    conn.execute(
        """
        CREATE TABLE user_behavior(
          user_id INTEGER,
          item_id INTEGER,
          category_id INTEGER,
          behavior_type TEXT,
          behavior_name_en TEXT,
          behavior_name_cn TEXT,
          timestamp INTEGER,
          behavior_time TEXT,
          date TEXT,
          hour INTEGER,
          weekday TEXT
        );
        """
    )

    for chunk in pd.read_csv(CSV_PATH, chunksize=50000):
        chunk.to_sql("user_behavior",conn,if_exists="append",index=False)
    conn.commit()
    count =conn.execute("SELECT COUNT(*) FROM user_behavior").fetchone()[0]
    print(f"IMPORTED {count:,} rows into {DB_PATH}")

    conn.close()

if __name__=="__main__":
    main()