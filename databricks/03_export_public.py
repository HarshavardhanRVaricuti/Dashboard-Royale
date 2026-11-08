# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Export data for the public dashboard
# MAGIC
# MAGIC Writes the `g_*` tables from `02_build_gold` as compact JSON into `docs/data/` of this Git folder.
# MAGIC `docs/index.html` (served by GitHub Pages) reads them and recomputes every ratio as a ratio of sums
# MAGIC for the period the viewer picks.
# MAGIC
# MAGIC After running: open the Git folder's **Git** dialog, commit `docs/data/*.json`, and push.

# COMMAND ----------

import json
import os
from decimal import Decimal

try:
    dbutils.widgets.text("catalog", "workspace")
    dbutils.widgets.text("schema", "dashboard_royale")
    NS = f"{dbutils.widgets.get('catalog')}.{dbutils.widgets.get('schema')}."
    notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    OUT = "/Workspace" + os.path.dirname(os.path.dirname(notebook_path)) + "/docs/data"
except NameError:  # local run via analysis/test_spark_sql.py
    NS = os.environ.get("ROYALE_NS", "")
    OUT = os.environ["ROYALE_OUT"]

os.makedirs(OUT, exist_ok=True)


def t(name):
    return NS + name


def columns(sql):
    """Query -> {column: [values]} (columnar keeps the JSON small)."""
    pdf = spark.sql(sql).toPandas()
    out = {}
    for c in pdf.columns:
        s = pdf[c]
        if str(s.dtype).startswith("datetime"):
            s = s.dt.strftime("%Y-%m-%d")
        out[c] = [None if v is None or v != v else float(v) if isinstance(v, Decimal) else v
                  for v in s.astype(object).tolist()]
    return out


def write(name, payload):
    path = os.path.join(OUT, name)
    with open(path, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"), default=str)
    print(f"{name:20s} {os.path.getsize(path) / 1e6:6.2f} MB")

# COMMAND ----------

# Dimensions: integer codes keep machine_day small.
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW x_dim AS
SELECT
  DENSE_RANK() OVER (ORDER BY machine_id) - 1 AS m,
  machine_id, theme, manufacturer,
  DATEDIFF(gaming_date, DATE'2025-01-01') AS d,
  zone_name, bank_id, gaming_date
FROM {t('g_machine_day')}
""")

machines = columns("SELECT DISTINCT m, machine_id AS id, theme, manufacturer FROM x_dim ORDER BY m")
zones = sorted({z for z in columns(f"SELECT DISTINCT zone_name FROM {t('g_machine_day')}")["zone_name"]})
banks = sorted({b for b in columns(f"SELECT DISTINCT bank_id FROM {t('g_machine_day')}")["bank_id"]})

machine_day = columns(f"""
SELECT
  DATEDIFF(g.gaming_date, DATE'2025-01-01') AS d,
  x.m,
  ARRAY_POSITION(ARRAY({','.join(repr(z) for z in zones)}), g.zone_name) - 1 AS z,
  ARRAY_POSITION(ARRAY({','.join(repr(b) for b in banks)}), g.bank_id) - 1 AS b,
  ROUND(g.scheduled_hours, 3) AS sch,
  ROUND(g.available_hours, 3) AS av,
  ROUND(g.occupied_hours, 3) AS occ,
  ROUND(g.coin_in_usd, 2) AS ci,
  ROUND(g.house_win_usd, 2) AS hw,
  ROUND(g.theo_usd, 2) AS th,
  ROUND(g.luck_variance_usd2, 0) AS lv,
  g.paid_spins AS sp,
  g.payout_positive_spins AS ps,
  ROUND(g.expected_hits, 1) AS eh,
  ROUND(g.hit_variance, 1) AS hv
FROM {t('g_machine_day')} g
JOIN (SELECT DISTINCT m, machine_id FROM x_dim) x USING (machine_id)
ORDER BY d, m
""")

write("machine_day.json", {"machines": machines, "zones": zones, "banks": banks, "rows": machine_day})

# COMMAND ----------

PRESETS = [
    ("all", "Jan – Jun", "2025-01", "2025-06"),
    ("jan_apr", "Jan – Apr (model training)", "2025-01", "2025-04"),
    ("may_jun", "May – Jun (holdout, new comp price)", "2025-05", "2025-06"),
] + [(f"2025-0{i}", f"{m} 2025", f"2025-0{i}", f"2025-0{i}")
     for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun"], start=1)]

preset_values = ", ".join(f"('{k}', '{a}', '{b}')" for k, _, a, b in PRESETS)

players = columns(f"""
WITH presets AS (SELECT * FROM VALUES {preset_values} AS p(preset, m0, m1)),
per_player AS (
  SELECT p.preset, g.player_id,
         ANY_VALUE(g.opening_tier) AS tier, ANY_VALUE(g.home_region) AS region,
         ANY_VALUE(g.age_band) AS age, ANY_VALUE(g.theo_decile) AS decile,
         SUM(g.coin_in_usd) AS ci, SUM(g.payout_usd) AS po, SUM(g.player_net_usd) AS net,
         SUM(g.theo_usd) AS th, SUM(g.comp_cost_usd) AS comp
  FROM {t('g_player_period')} g
  JOIN presets p ON g.period_month BETWEEN p.m0 AND p.m1
  WHERE g.coin_in_usd > 0
  GROUP BY p.preset, g.player_id
)
SELECT preset, tier, region, age, decile,
       COUNT(*) AS n,
       ROUND(SUM(ci), 2) AS ci, ROUND(SUM(po), 2) AS po, ROUND(SUM(net), 2) AS net,
       ROUND(SUM(th), 2) AS th, ROUND(SUM(comp), 2) AS comp,
       SUM(CASE WHEN net > 0 THEN 1 ELSE 0 END) AS ahead
FROM per_player
GROUP BY ALL
""")

write("players.json", {"presets": [{"key": k, "label": l} for k, l, _, _ in PRESETS], "rows": players})

# COMMAND ----------

small = {
    "property_day": columns(f"""
        SELECT gaming_date, local_weekday, events_active, coin_in_usd, house_win_usd, theo_usd,
               contribution_usd, comp_cost_usd, faults_opened
        FROM {t('g_property_day')} ORDER BY gaming_date"""),
    "faults": columns(f"""
        SELECT DATEDIFF(gaming_date, DATE'2025-01-01') AS d, shift, manufacturer, zone_name, bank_id AS bank,
               ROUND(wait_hours, 3) AS wait, ROUND(fix_hours, 3) AS fix, ROUND(down_hours, 3) AS down
        FROM {t('g_fault_tickets')} WHERE event_type = 'fault_repair'"""),
    "staff": columns(f"""
        SELECT DATEDIFF(gaming_date, DATE'2025-01-01') AS d, shift, planned_techs, actual_techs
        FROM {t('g_tech_staffing')}"""),
    "event_lift": columns(f"SELECT * FROM {t('g_event_lift')} ORDER BY coin_in_lift DESC"),
    "city": columns(f"""
        WITH casino AS (
          SELECT DATE_FORMAT(gaming_date, 'yyyy-MM') AS month, AVG(coin_in_usd) AS casino_coin_in_per_day
          FROM {t('g_property_day')} GROUP BY 1
        )
        SELECT c.month, c.casino_coin_in_per_day,
               CAST(v.mean_visitors_per_calendar_day AS DOUBLE) AS lv_visitors_per_day,
               CAST(v.visitor_yoy_ratio AS DOUBLE) AS lv_visitor_yoy
        FROM casino c JOIN {t('city_visitation_monthly')} v USING (month) ORDER BY c.month"""),
    "forecast": columns(f"SELECT * FROM {t('g_forecast')} ORDER BY gaming_date"),
    "forecast_scores": columns(f"SELECT * FROM {t('g_forecast_scores')} ORDER BY split DESC, mae_usd"),
    "budget": columns(f"SELECT * FROM {t('g_budget_plan')}"),
    "comp_month": columns(f"""
        WITH p AS (
          SELECT period_month AS month, SUM(theo_usd) AS tracked_theo_usd, SUM(comp_cost_usd) AS comp_cost_usd,
                 SUM(points_earned) AS points_earned, SUM(points_redeemed) AS points_redeemed
          FROM {t('g_player_period')} GROUP BY 1
        ),
        r AS (
          SELECT DATE_FORMAT(gaming_date, 'yyyy-MM') AS month, SUM(redemptions) AS redemptions,
                 SUM(points_redeemed) AS ledger_points
          FROM {t('g_comp_redemptions')} GROUP BY 1
        )
        SELECT p.*, r.redemptions, p.comp_cost_usd / p.tracked_theo_usd AS reinvestment,
               r.ledger_points / r.redemptions AS points_per_redemption
        FROM p JOIN r USING (month) ORDER BY month"""),
    "comp_benefit": columns(f"""
        SELECT DATE_FORMAT(gaming_date, 'yyyy-MM') AS month, benefit_id,
               SUM(points_redeemed) / SUM(redemptions) AS points_per_redemption,
               SUM(face_value_usd) / SUM(redemptions) AS face_value_usd,
               SUM(redemptions) AS redemptions
        FROM {t('g_comp_redemptions')} GROUP BY ALL ORDER BY benefit_id, month"""),
}
write("tables.json", small)

# COMMAND ----------

# MAGIC %md
# MAGIC Next: commit and push `docs/data/` from the Git folder. GitHub Pages (Settings → Pages → `main` / `docs`)
# MAGIC republishes within a minute.
