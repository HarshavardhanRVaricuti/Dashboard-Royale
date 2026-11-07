import glob
import os

import duckdb
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 200)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def connect():
    con = duckdb.connect()
    for path in glob.glob(os.path.join(ROOT, "data", "**", "*.parquet"), recursive=True):
        name = os.path.splitext(os.path.basename(path))[0]
        con.sql(f"CREATE VIEW {name} AS SELECT * FROM '{path}'")
    return con
