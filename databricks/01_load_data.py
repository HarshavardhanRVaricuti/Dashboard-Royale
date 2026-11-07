# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Load Dashboard Royale data into Unity Catalog
# MAGIC
# MAGIC Creates `<catalog>.<schema>` and a volume `raw`, copies every `.parquet` file into the volume,
# MAGIC and registers each one as a Delta table with the same name (e.g. `machine_day`).
# MAGIC
# MAGIC **Where the files come from (first match wins):**
# MAGIC 1. `source_dir` widget, if set.
# MAGIC 2. The `data/` folder of the Git folder this notebook lives in, or a Git folder of
# MAGIC    `https://github.com/tamu-datathon-org/dashboard-royale` at `/Workspace/Users/<you>/dashboard-royale`.
# MAGIC 3. Files you uploaded yourself anywhere under `/Volumes/<catalog>/<schema>/raw/`.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "dashboard_royale")
dbutils.widgets.text("source_dir", "")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
source_dir = dbutils.widgets.get("source_dir").strip()

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.raw")
volume = f"/Volumes/{catalog}/{schema}/raw"

# COMMAND ----------

import glob
import os
import shutil

if not source_dir:
    me = spark.sql("SELECT current_user()").first()[0]
    notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    candidates = [
        "/Workspace" + os.path.dirname(os.path.dirname(notebook_path)) + "/data",
        f"/Workspace/Users/{me}/dashboard-royale/data",
    ]
    source_dir = next((c for c in candidates if os.path.exists(c)), "")

if source_dir:
    copied = 0
    for src in glob.glob(f"{source_dir}/**/*.parquet", recursive=True):
        rel = os.path.relpath(src, source_dir)
        dst = os.path.join(volume, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        copied += 1
    print(f"Copied {copied} parquet files from {source_dir} to {volume}")
else:
    print(f"No source folder found; using files already uploaded to {volume}")

files = sorted(glob.glob(f"{volume}/**/*.parquet", recursive=True))
assert files, f"No parquet files found. Upload the repo's data/ folder to {volume} or set source_dir."
print(len(files), "parquet files")

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import TimestampNTZType

# Keep timestamps as stored (UTC or local wall clock, per the column suffix).
spark.conf.set("spark.sql.session.timeZone", "UTC")

for path in files:
    name = os.path.splitext(os.path.basename(path))[0]
    df = spark.read.parquet(path)
    for field in df.schema.fields:
        if isinstance(field.dataType, TimestampNTZType):
            df = df.withColumn(field.name, F.col(field.name).cast("timestamp"))
    (df.write.mode("overwrite").option("overwriteSchema", "true")
       .saveAsTable(f"{catalog}.{schema}.{name}"))
    print(f"{name:32s} {df.count():>10,d} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC Row counts should match `data/manifest.json` (e.g. `machine_day` 56,110, `sessions` 776,297).
# MAGIC Next: run `02_build_gold`.
