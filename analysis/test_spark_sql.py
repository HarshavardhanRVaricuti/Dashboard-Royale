"""Run databricks/02_build_gold.sql and the dashboard dataset queries on local PySpark."""
import glob
import json
import os
import re
import sys

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import TimestampNTZType

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spark = (SparkSession.builder.master("local[4]").appName("royale")
         .config("spark.sql.session.timeZone", "UTC")
         .config("spark.driver.memory", "4g")
         .config("spark.ui.enabled", "false")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

for path in glob.glob(os.path.join(ROOT, "data", "**", "*.parquet"), recursive=True):
    name = os.path.splitext(os.path.basename(path))[0]
    df = spark.read.parquet(path)
    for field in df.schema.fields:
        if isinstance(field.dataType, TimestampNTZType):
            df = df.withColumn(field.name, F.col(field.name).cast("timestamp"))
    df.createOrReplaceTempView(name)


def statements(sql_text):
    lines = [l for l in sql_text.splitlines() if not l.startswith("-- MAGIC") and not l.startswith("-- Databricks")]
    for chunk in "\n".join(lines).split("-- COMMAND ----------"):
        for stmt in chunk.split(";"):
            stmt = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
            if stmt and not stmt.upper().startswith("USE "):
                yield stmt


gold = open(os.path.join(ROOT, "databricks", "02_build_gold.sql")).read()
for stmt in statements(gold):
    m = re.match(r"CREATE OR REPLACE TABLE (\w+) AS\s+(.*)", stmt, re.S)
    if m:
        spark.sql(m.group(2)).cache().createOrReplaceTempView(m.group(1))
        print(f"{m.group(1):30s} {spark.table(m.group(1)).count():>8,d} rows")
    else:
        spark.sql(stmt).show(20, truncate=60)

if "--export" in sys.argv:
    os.environ["ROYALE_OUT"] = os.path.join(ROOT, "docs", "data")
    exec(open(os.path.join(ROOT, "databricks", "03_export_public.py")).read(), {"spark": spark})
    sys.exit(0)

dash_path = os.path.join(ROOT, "databricks", "dashboard_royale.lvdash.json")
if os.path.exists(dash_path) and "--gold-only" not in sys.argv:
    dash = json.load(open(dash_path))
    params = {"start_date": "2025-01-01", "end_date": "2025-06-30"}
    for ds in dash["datasets"]:
        q = "".join(ds["queryLines"]).replace("workspace.dashboard_royale.", "")
        for k, v in params.items():
            q = q.replace(f":{k}", f"DATE'{v}'")
        df = spark.sql(q)
        print(f"\n== dataset {ds['displayName']} ({df.count()} rows)")
        df.show(8, truncate=40)
