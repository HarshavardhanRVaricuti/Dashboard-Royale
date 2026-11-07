-- Databricks notebook source
-- MAGIC %md
-- MAGIC # 02 · Gold tables for the dashboard
-- MAGIC
-- MAGIC Every table keeps **additive components** (sums of dollars, hours, spins, variances) so that the dashboard
-- MAGIC can recompute ratios as **ratio of sums** for whatever period a judge picks.
-- MAGIC
-- MAGIC | Table | Grain | Feeds |
-- MAGIC | --- | --- | --- |
-- MAGIC | `g_machine_day` | machine × day on the floor | Q1 scorecard, Q2 zone trends, Q3 downtime |
-- MAGIC | `g_property_day` | day | Q2 demand, model |
-- MAGIC | `g_forecast` | day | Model: weekday-mean forecast vs constant baseline |
-- MAGIC | `g_fault_tickets` | fault ticket | Q3 downtime by manufacturer / shift |
-- MAGIC | `g_tech_staffing` | day × shift | Q3 technician headcount |
-- MAGIC | `g_player_period` | player × month | Q4 player outcomes |
-- MAGIC | `g_comp_redemptions` | day × benefit | Q5 comp program |
-- MAGIC | `g_budget_plan` | action | Q6 priced plan |
-- MAGIC
-- MAGIC Change the catalog/schema below if you used different names in `01_load_data`.

-- COMMAND ----------

USE CATALOG workspace;
USE SCHEMA dashboard_royale;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `g_machine_day`
-- MAGIC Luck test: house win − theo, scaled by its standard deviation. Per-spin payout variance comes from
-- MAGIC `game_math.payout_multiplier_variance`, so Var(house win) = Σ bet² × variance (`sum_bet_squared` is in `machine_day`).
-- MAGIC Leak test: payout-positive spins vs `paid_spins × hit_probability` (binomial).

-- COMMAND ----------

CREATE OR REPLACE TABLE g_machine_day AS
SELECT
  m.machine_id,
  m.gaming_date,
  p.month,
  p.local_weekday,
  p.is_weekend,
  p.events_active,
  p.zone_id,
  p.zone_name,
  p.bank_id,
  m.location_id,
  m.config_id,
  p.theme,
  p.manufacturer,
  p.volatility_class,
  p.lease_class,
  CAST(g.configured_rtp AS DOUBLE) AS configured_rtp,
  m.gaming_date BETWEEN DATE'2025-03-03' AND DATE'2025-04-06' AS entrance_walkway_closed,
  m.scheduled_seconds / 3600.0 AS scheduled_hours,
  m.available_seconds / 3600.0 AS available_hours,
  m.occupied_seconds / 3600.0 AS occupied_hours,
  (m.scheduled_seconds - m.available_seconds) / 3600.0 AS downtime_hours,
  m.paid_spins,
  m.payout_positive_spins,
  m.paid_spins * CAST(g.hit_probability AS DOUBLE) AS expected_hits,
  m.paid_spins * CAST(g.hit_probability AS DOUBLE) * (1 - CAST(g.hit_probability AS DOUBLE)) AS hit_variance,
  m.coin_in_cents / 100.0 AS coin_in_usd,
  m.payout_cents / 100.0 AS payout_usd,
  m.house_win_cents / 100.0 AS house_win_usd,
  CAST(m.theo_cents AS DOUBLE) / 100.0 AS theo_usd,
  (m.house_win_cents - CAST(m.theo_cents AS DOUBLE)) / 100.0 AS luck_usd,
  m.sum_bet_squared * CAST(g.payout_multiplier_variance AS DOUBLE) / 10000.0 AS luck_variance_usd2,
  m.carded_coin_in_cents / 100.0 AS carded_coin_in_usd,
  p.faults_opened,
  CAST(p.contribution_after_supplied_costs_usd AS DOUBLE) AS contribution_usd
FROM machine_day m
JOIN game_math g USING (config_id)
JOIN prepared_daily_view p USING (machine_id, gaming_date)
WHERE m.active;

-- COMMAND ----------

-- Full-period scorecard (the dashboard recomputes this for any period).
CREATE OR REPLACE TABLE g_machine_scorecard AS
WITH s AS (
  SELECT
    machine_id,
    MAX_BY(zone_name, gaming_date) AS zone_name,
    MAX_BY(bank_id, gaming_date) AS bank_id,
    ANY_VALUE(theme) AS theme,
    ANY_VALUE(manufacturer) AS manufacturer,
    COUNT(*) AS days_on_floor,
    SUM(available_hours) / SUM(scheduled_hours) AS availability,
    SUM(occupied_hours) / NULLIF(SUM(available_hours), 0) AS occupancy,
    SUM(house_win_usd) AS house_win_usd,
    SUM(theo_usd) AS theo_usd,
    SUM(luck_usd) AS luck_usd,
    SUM(luck_usd) / NULLIF(SQRT(SUM(luck_variance_usd2)), 0) AS luck_z,
    SUM(house_win_usd) / NULLIF(SUM(coin_in_usd), 0) AS observed_hold,
    SUM(theo_usd) / NULLIF(SUM(coin_in_usd), 0) AS theo_hold,
    SUM(payout_positive_spins) / NULLIF(SUM(paid_spins), 0) AS hit_rate,
    SUM(expected_hits) / NULLIF(SUM(paid_spins), 0) AS published_hit_rate,
    (SUM(payout_positive_spins) - SUM(expected_hits)) / NULLIF(SQRT(SUM(hit_variance)), 0) AS hit_z,
    SUM(theo_usd) / NULLIF(SUM(available_hours), 0) AS theo_per_available_hour
  FROM g_machine_day
  GROUP BY machine_id
)
SELECT
  *,
  RANK() OVER (ORDER BY house_win_usd) AS manager_rank,
  CASE
    WHEN ABS(hit_z) > 4 THEN 'Leak? Hit rate off published math: inspect'
    WHEN days_on_floor < 150 THEN 'Exposure: partial period on floor'
    WHEN zone_name = 'Back Forty' AND luck_z > -2 THEN 'Location: weak zone, play within luck'
    WHEN luck_z < -2 THEN 'Unlucky (|z|>2): watch, re-test'
    ELSE 'Within luck'
  END AS diagnosis
FROM s;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `g_property_day` and `g_forecast`
-- MAGIC Model (frozen on Jan–Apr, tested on May–Jun): forecast daily floor coin-in as the training-period mean for that weekday.
-- MAGIC Baseline: constant training-period daily mean. A third variant adds a training-period event uplift for
-- MAGIC events announced in advance; it is reported honestly even though it is worse on the holdout.

-- COMMAND ----------

CREATE OR REPLACE TABLE g_property_day AS
SELECT
  p.gaming_date,
  p.local_weekday,
  c.is_weekend,
  c.federal_holiday,
  p.events_active,
  p.active_machines,
  CAST(p.coin_in_usd AS DOUBLE) AS coin_in_usd,
  CAST(p.payout_usd AS DOUBLE) AS payout_usd,
  CAST(p.house_win_usd AS DOUBLE) AS house_win_usd,
  CAST(p.theo_usd AS DOUBLE) AS theo_usd,
  p.available_machine_hours,
  p.occupied_machine_hours,
  p.carded_coin_in_share,
  CAST(p.pos_cash_usd AS DOUBLE) AS pos_cash_usd,
  CAST(p.pos_cogs_usd AS DOUBLE) AS pos_cogs_usd,
  CAST(p.comp_cost_usd AS DOUBLE) AS comp_cost_usd,
  p.faults_opened,
  p.total_zone_entries_observed,
  p.counter_coverage_share,
  CAST(p.contribution_after_supplied_costs_usd AS DOUBLE) AS contribution_usd,
  CAST(w.tmax_c AS DOUBLE) AS tmax_c,
  CAST(w.prcp_mm AS DOUBLE) AS prcp_mm
FROM property_day p
JOIN calendar_day c USING (gaming_date)
LEFT JOIN weather_daily w ON w.source_date = p.gaming_date;

-- COMMAND ----------

CREATE OR REPLACE TABLE g_forecast AS
WITH train AS (
  SELECT * FROM g_property_day WHERE gaming_date < DATE'2025-05-01'
),
weekday_mean AS (
  SELECT local_weekday, AVG(coin_in_usd) AS pred_weekday FROM train GROUP BY local_weekday
),
weekday_mean_no_event AS (
  SELECT local_weekday, AVG(coin_in_usd) AS base FROM train WHERE events_active IS NULL GROUP BY local_weekday
),
event_lift AS (
  SELECT AVG(t.coin_in_usd / b.base) AS lift
  FROM train t JOIN weekday_mean_no_event b USING (local_weekday)
  WHERE t.events_active IS NOT NULL
),
constant AS (
  SELECT AVG(coin_in_usd) AS pred_constant FROM train
)
SELECT
  p.gaming_date,
  p.local_weekday,
  p.events_active,
  CASE WHEN p.gaming_date < DATE'2025-05-01' THEN 'train (Jan–Apr)' ELSE 'test (May–Jun)' END AS split,
  p.coin_in_usd AS actual,
  c.pred_constant,
  w.pred_weekday,
  b.base * CASE WHEN p.events_active IS NOT NULL THEN e.lift ELSE 1 END AS pred_weekday_event
FROM g_property_day p
JOIN weekday_mean w USING (local_weekday)
JOIN weekday_mean_no_event b USING (local_weekday)
CROSS JOIN event_lift e
CROSS JOIN constant c;

-- COMMAND ----------

CREATE OR REPLACE TABLE g_forecast_scores AS
SELECT
  split,
  model,
  AVG(ABS(actual - pred)) AS mae_usd,
  AVG(ABS(actual - pred) / actual) AS mape,
  COUNT(*) AS days
FROM g_forecast
LATERAL VIEW STACK(3,
  'Baseline: constant mean', pred_constant,
  'Model: weekday mean', pred_weekday,
  'Variant: weekday + event uplift', pred_weekday_event
) s AS model, pred
GROUP BY split, model;

SELECT * FROM g_forecast_scores ORDER BY split DESC, mae_usd;

-- COMMAND ----------

-- Event lift vs the no-event weekday baseline (all six months): how much did each event add?
CREATE OR REPLACE TABLE g_event_lift AS
WITH base AS (
  SELECT local_weekday, AVG(coin_in_usd) AS base FROM g_property_day WHERE events_active IS NULL GROUP BY local_weekday
)
SELECT
  p.events_active AS event_name,
  e.event_type,
  e.local_scope,
  COUNT(*) AS days,
  AVG(p.coin_in_usd / b.base - 1) AS coin_in_lift,
  SUM(p.coin_in_usd - b.base) AS extra_coin_in_usd,
  SUM(p.coin_in_usd - b.base) * SUM(p.theo_usd) / SUM(p.coin_in_usd) AS extra_theo_usd
FROM g_property_day p
JOIN base b USING (local_weekday)
LEFT JOIN events e ON e.name = p.events_active
WHERE p.events_active IS NOT NULL
GROUP BY p.events_active, e.event_type, e.local_scope;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Downtime: `g_fault_tickets`, `g_tech_staffing`

-- COMMAND ----------

CREATE OR REPLACE TABLE g_fault_tickets AS
SELECT
  o.operation_id,
  o.machine_id,
  m.manufacturer,
  z.zone_name,
  o.event_type,
  CAST(o.opened_at_local - INTERVAL 6 HOURS AS DATE) AS gaming_date,
  HOUR(o.opened_at_local) AS opened_local_hour,
  CASE
    WHEN HOUR(o.opened_at_local) BETWEEN 6 AND 13 THEN '1 Day (06–14)'
    WHEN HOUR(o.opened_at_local) BETWEEN 14 AND 21 THEN '2 Swing (14–22)'
    ELSE '3 Grave (22–06)'
  END AS shift,
  TIMESTAMPDIFF(SECOND, o.opened_at_utc, o.work_started_at_utc) / 3600.0 AS wait_hours,
  TIMESTAMPDIFF(SECOND, o.work_started_at_utc, o.available_at_utc) / 3600.0 AS fix_hours,
  TIMESTAMPDIFF(SECOND, o.opened_at_utc, o.available_at_utc) / 3600.0 AS down_hours,
  o.direct_cost_cents / 100.0 AS direct_cost_usd
FROM operations o
JOIN machines m USING (machine_id)
LEFT JOIN (SELECT DISTINCT location_id, zone_name FROM prepared_daily_view WHERE location_id IS NOT NULL) z
  ON z.location_id = o.location_id;

-- COMMAND ----------

CREATE OR REPLACE TABLE g_tech_staffing AS
SELECT
  gaming_date,
  shift,
  SUM(planned_headcount) AS planned_techs,
  SUM(actual_headcount) AS actual_techs
FROM shift_roster
WHERE role = 'slot_tech'
GROUP BY gaming_date, shift;

-- COMMAND ----------

-- Faults per 1,000 machine-days by manufacturer (exposure-adjusted).
CREATE OR REPLACE TABLE g_manufacturer_reliability AS
WITH exposure AS (
  SELECT manufacturer, COUNT(*) AS machine_days, SUM(downtime_hours) AS downtime_hours,
         SUM(theo_usd) / SUM(available_hours) AS theo_per_available_hour
  FROM g_machine_day GROUP BY manufacturer
),
faults AS (
  SELECT manufacturer, COUNT(*) AS faults, AVG(wait_hours) AS avg_wait_hours, AVG(down_hours) AS avg_down_hours
  FROM g_fault_tickets WHERE event_type = 'fault_repair' GROUP BY manufacturer
)
SELECT
  e.manufacturer,
  e.machine_days,
  f.faults,
  1000.0 * f.faults / e.machine_days AS faults_per_1000_machine_days,
  f.avg_wait_hours,
  f.avg_down_hours,
  e.downtime_hours,
  e.downtime_hours * e.theo_per_available_hour AS lost_theo_usd
FROM exposure e JOIN faults f USING (manufacturer);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### Guests: `g_player_period`, `g_comp_redemptions`
-- MAGIC Carded play only. `theo_decile` ranks players by full-period theo (1 = top 10%).

-- COMMAND ----------

CREATE OR REPLACE TABLE g_player_period AS
WITH totals AS (
  SELECT player_id, SUM(theo_usd) AS total_theo, SUM(tracked_coin_in_usd) AS total_coin_in
  FROM player_period GROUP BY player_id
),
ranked AS (
  SELECT player_id, NTILE(10) OVER (ORDER BY total_theo DESC, player_id) AS theo_decile
  FROM totals WHERE total_coin_in > 0
)
SELECT
  pp.player_id,
  pp.period_month,
  TO_DATE(pp.period_month || '-01') AS month_start,
  pp.home_region,
  COALESCE(pp.age_band, 'unknown') AS age_band,
  pp.opening_tier,
  pp.tier_end,
  r.theo_decile,
  pp.observed_visits,
  pp.sessions,
  pp.carded_play_hours,
  CAST(pp.tracked_coin_in_usd AS DOUBLE) AS coin_in_usd,
  CAST(pp.tracked_payout_usd AS DOUBLE) AS payout_usd,
  CAST(pp.tracked_net_usd AS DOUBLE) AS player_net_usd,
  -CAST(pp.tracked_net_usd AS DOUBLE) AS house_win_usd,
  CAST(pp.theo_usd AS DOUBLE) AS theo_usd,
  CAST(pp.luck_residual_usd AS DOUBLE) AS luck_residual_usd,
  CAST(pp.comp_cost_usd AS DOUBLE) AS comp_cost_usd,
  CAST(pp.comp_face_value_usd AS DOUBLE) AS comp_face_value_usd,
  pp.comps_redeemed,
  pp.points_earned,
  pp.points_redeemed,
  CAST(pp.tracked_contribution_usd AS DOUBLE) AS contribution_usd
FROM player_period pp
LEFT JOIN ranked r USING (player_id);

-- COMMAND ----------

CREATE OR REPLACE TABLE g_comp_redemptions AS
SELECT
  CAST(FROM_UTC_TIMESTAMP(event_at_utc, 'America/Los_Angeles') - INTERVAL 6 HOURS AS DATE) AS gaming_date,
  benefit_id,
  COUNT(*) AS redemptions,
  SUM(-points_delta) AS points_redeemed,
  SUM(face_value_cents) / 100.0 AS face_value_usd,
  SUM(economic_cost_cents) / 100.0 AS economic_cost_usd
FROM loyalty_ledger
WHERE event_type = 'redeem'
GROUP BY ALL;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ### `g_budget_plan`
-- MAGIC Cost = quantity × (unit cost + daily cost × max(0, 30 − lead days)). Benefits are estimates from the evidence above. Dollar amounts are written as `¤` and restored with `chr(36)`: SQL notebooks treat a dollar sign followed by a name as a widget reference.

-- COMMAND ----------

CREATE OR REPLACE TABLE g_budget_plan AS
WITH plan AS (
  SELECT * FROM VALUES
    ('A-INSPECT', 5,
     'M-1158, M-1054, M-1210, M-1181, M-5076',
     'Leak: M-1158 hits 38.5% of spins vs 31.5% published every month (z≈124) and holds 3.0% vs 10% theo. Others are the most negative luck z-scores — inspection rules them in or out.',
     'If M-1158 is mis-set and fixed: ≈+¤5.8k house win in the 29 effective days (7 pts of hold × ≈¤87k/month coin-in), then ≈¤6k every month after. Other 4: likely no finding (they look like luck).',
     'High for M-1158 (pattern stable all six months). Low for the other four.',
     'Post-fix hit rate within ±1 pt of 31.5% and hold converging to 10% over 30 days — compare with machine-level 95% luck band.'),
    ('A-PROMO', 1,
     'One Fri–Sun slot tournament weekend, late July (14-day lead)',
     'Winter Slot Tournament (Feb 21–23) ran +18% coin-in vs the weekday baseline (+¤842k coin-in, ≈+¤80k theo) with no dip on surrounding days.',
     'Central ≈ +¤40k theo (50% haircut for one prior example and summer softness). Range ¤0–¤80k.',
     'Medium–high: single prior example — June demand was soft citywide (LVCVA visitors −11% YoY).',
     'Weekend coin-in vs the frozen weekday-mean forecast (model page) — check the following week for pull-forward — never target players by losses.'),
    ('A-WAYFINDING', 1,
     'Back Forty (Z-B40)',
     'Every theme earns 41–55% less theo per available hour in Back Forty than the same theme at Main Entrance. When the entrance–Back Forty walkway closed (Mar 3–Apr 6), Back Forty theo fell ≈30% and recovered after reopening: access drives this zone.',
     'Central +5% Back Forty theo for 20 days ≈ +¤13k theo — part may be shifted from other zones (new Aurora bank showed floor-wide play mostly redistributes).',
     'High: signage effect size is unknown and partly zero-sum.',
     'Difference-in-differences: Back Forty theo per available hour vs other zones, 20 days after vs 28 days before — Z-B40 counter entries (counter_status = ok only).'),
    ('A-HOLD', 1,
     'Remaining budget',
     'Replacing the bottom-10 is not supported: 9 of 10 sit in Back Forty, 3 had partial exposure, and the in-slot replacement of M-1120 by M-5076 changed theo/hour only ¤6.00 → ¤6.39.',
     'Avoids ≈¤34k (10 leases) to ¤220k (10 purchases) for no measurable uplift.',
     'n/a',
     'Revisit after wayfinding and inspection results.')
  AS t(action_type_id, quantity, targets, evidence, expected_effect, uncertainty, measurement)
)
SELECT
  p.action_type_id,
  a.name,
  p.quantity,
  p.targets,
  p.quantity * (a.unit_cost_cents + a.recurring_cost_cents_per_day * GREATEST(0, 30 - a.lead_days)) / 100.0 AS cost_usd,
  a.lead_days,
  replace(p.evidence, '¤', chr(36)) AS evidence,
  replace(p.expected_effect, '¤', chr(36)) AS expected_effect,
  p.uncertainty,
  p.measurement
FROM plan p
JOIN action_catalog a USING (action_type_id);

SELECT action_type_id, quantity, cost_usd FROM g_budget_plan;
