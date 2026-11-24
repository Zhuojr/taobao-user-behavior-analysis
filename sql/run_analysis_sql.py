from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "user_behavior.db"
SQL_PATH = PROJECT_ROOT / "sql" / "taobao_behavior_analysis_sqlite.sql"
PREVIEW_ROWS = 10


def split_statements(sql_text: str) -> list[str]:
    """按分号切分 SQL 语句，忽略字符串字面量（含 '' 转义）与 -- 注释内部的分号。"""
    statements: list[str] = []
    buffer: list[str] = []
    in_string = False
    index = 0

    while index < len(sql_text):
        char = sql_text[index]

        if in_string:
            buffer.append(char)
            if char == "'":
                if sql_text[index : index + 2] == "''":  # SQL 转义的单引号
                    buffer.append("'")
                    index += 1
                else:
                    in_string = False
        elif char == "'":
            in_string = True
            buffer.append(char)
        elif sql_text[index : index + 2] == "--":  # 注释直到行尾，整体保留
            line_end = sql_text.find("\n", index)
            if line_end == -1:
                line_end = len(sql_text)
            buffer.append(sql_text[index:line_end])
            index = line_end - 1
        elif char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(char)

        index += 1

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)

    return statements


def check_database(conn: sqlite3.Connection) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "user_behavior" not in tables:
        raise SystemExit(
            f"数据库 {DB_PATH} 中没有 user_behavior 表（当前表：{sorted(tables) or '无'}）。\n"
            "请先运行 `python sql/sqlite_import.py` 完成数据导入后再执行本脚本。"
        )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    check_database(conn)
    statements = split_statements(SQL_PATH.read_text(encoding="utf-8"))

    for index, stmt in enumerate(statements, start=1):
        try:
            df = pd.read_sql(stmt, conn)
        except Exception as error:
            print(f"\n=== Query {index} ERROR: {error} ===")
            continue

        print(f"\n=== Query {index}: {len(df)} rows ===")
        print(df.head(PREVIEW_ROWS).to_string(index=False))
        if len(df) > PREVIEW_ROWS:
            print(f"... (仅显示前 {PREVIEW_ROWS} 行)")

    conn.close()


if __name__ == "__main__":
    main()
