# Running this on Databricks Free Edition

About 15 minutes end to end. Everything runs on serverless compute and the single Free Edition SQL warehouse.

## 1. Get the repo into your workspace

1. Push this folder to your own public GitHub repo (the submission needs "all code" anyway).
2. In Databricks: **Workspace → Create → Git folder**, paste your repo URL, name it `dashboard-royale`.

The `data/` folder (245 MB of Parquet + CSV) comes along with the Git folder.

> No GitHub? Create a Git folder from `https://github.com/tamu-datathon-org/dashboard-royale` for the data,
> then **Workspace → Import** the files in `databricks/` into the same folder's `databricks/` subfolder.

## 2. Load the data — `databricks/01_load_data`

Open the notebook, attach **Serverless**, **Run all**. It creates `workspace.dashboard_royale`, a volume `raw`,
copies the Parquet files into the volume and registers one Delta table per file. Check the printed row counts
against `data/manifest.json` (e.g. `machine_day` 56,110).

## 3. Build the analysis tables — `databricks/02_build_gold`

**Run all.** It creates the `g_*` tables and prints the holdout scores and the budget plan:

| Split | Model | MAE |
| --- | --- | ---: |
| test (May–Jun) | Baseline: constant mean | ≈ $218k |
| test (May–Jun) | Model: weekday mean | ≈ $69k |
| test (May–Jun) | Variant: weekday + event uplift | ≈ $51k |

## 4. Import the dashboard

1. **Dashboards → Create dashboard ▾ → Import dashboard from file** → `databricks/dashboard_royale.lvdash.json`
   (download it from the Git folder first, or regenerate it with `python databricks/build_dashboard.py`).
2. If the import complains about a widget, open the dashboard anyway: the datasets (Data tab) import even when a
   single widget spec needs a tweak in the editor.
3. Pick the **Serverless Starter Warehouse** when asked.

If you used another catalog/schema: `python databricks/build_dashboard.py my_catalog.my_schema` and edit the
`USE` lines at the top of `02_build_gold`.

## 5. Publish and share the Databricks dashboard

**Publish** with *Share data permissions* (default). Free Edition can only share with people **registered to
your Databricks account** (they sign in with an email one-time code). A public no-login link and external
embedding are not available, so the public link comes from step 6.

## 6. Public dashboard on GitHub Pages — `databricks/03_export_public`

1. **Run all.** It writes `docs/data/machine_day.json`, `players.json` and `tables.json` into this Git folder
   (≈4.7 MB, ≈1.3 MB once GitHub compresses it).
2. Open the Git folder's **Git** dialog (branch name at the top of the folder), commit `docs/data/`, **Push**.
   If the write or push is blocked, download the three files and commit them from your laptop instead.
3. On GitHub: **Settings → Pages → Deploy from a branch → `main` / `docs`**. The dashboard is live at
   `https://<your-user>.github.io/<repo>/` within a minute. Open it in a private window before submitting.

`docs/index.html` + `docs/app.js` recompute every ratio as ratio of sums for any period, zone or bank, so the
public page matches the Databricks dashboard. Rerun step 6 whenever the gold tables change.

Preview locally: `cd docs && python3 -m http.server 8765`, then open <http://localhost:8765>.

## What the judges' 4 checks map to

| Judge action | Where |
| --- | --- |
| Change the analysis period | Databricks: *Period start / end* pickers on pages 2–5 · public page: *From / To* and presets (all tabs) |
| Drill into one bank or guest group | *Zone / Bank* filters (machines, demand, downtime) · page 5 *tier / region / age* filters |
| Find how the model was validated | Page 7 |
| Trace a recommendation to its evidence | Page 1 plan table → page 8 claims table → the `g_*` table named there |

## Local checks (optional)

`analysis/` holds the DuckDB exploration scripts and `test_spark_sql.py`, which runs `02_build_gold.sql`
and every dashboard query on local PySpark (`pip install duckdb pandas pyarrow pyspark==3.5.*`, Java 17).
