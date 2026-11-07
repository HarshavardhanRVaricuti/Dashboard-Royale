"""Generate dashboard_royale.lvdash.json (Databricks AI/BI dashboard).

    python databricks/build_dashboard.py [catalog.schema]

Import in Databricks: Dashboards -> Create -> Import dashboard from file.
"""
import json
import os
import sys

NS = sys.argv[1] if len(sys.argv) > 1 else "workspace.dashboard_royale"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_royale.lvdash.json")

PERIOD = "gaming_date BETWEEN :start_date AND :end_date"


def T(name):
    return f"{NS}.{name}"


# ---------------------------------------------------------------- datasets

DATASETS = {
    "kpi": ("Floor KPIs", True, f"""
SELECT
  SUM(coin_in_usd) AS coin_in_usd,
  SUM(house_win_usd) AS house_win_usd,
  SUM(theo_usd) AS theo_usd,
  SUM(house_win_usd) / SUM(coin_in_usd) AS observed_hold,
  SUM(theo_usd) / SUM(coin_in_usd) AS theo_hold,
  SUM(contribution_usd) AS contribution_usd,
  COUNT(*) AS gaming_days
FROM {T('g_property_day')}
WHERE {PERIOD}"""),

    "scorecard": ("Machine scorecard (period)", True, f"""
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
  FROM {T('g_machine_day')}
  WHERE {PERIOD}
  GROUP BY machine_id
),
p AS (SELECT DATEDIFF(:end_date, :start_date) + 1 AS period_days)
SELECT
  s.*,
  RANK() OVER (ORDER BY house_win_usd) AS manager_rank,
  CASE
    WHEN ABS(hit_z) > 4 THEN '1 Leak? Hit rate off published math -> inspect'
    WHEN days_on_floor < 0.8 * p.period_days THEN '2 Exposure: on floor part of period'
    WHEN availability < 0.97 THEN '3 Downtime'
    WHEN zone_name = 'Back Forty' AND luck_z > -2 THEN '4 Location: weak zone, result within luck'
    WHEN luck_z < -2 THEN '5 Unlucky (z < -2): re-test next period'
    ELSE '6 Within luck'
  END AS diagnosis
FROM s CROSS JOIN p"""),

    "zone_theme": ("Theo per available hour, theme x zone", True, f"""
SELECT theme, zone_name,
       SUM(theo_usd) / SUM(available_hours) AS theo_per_available_hour,
       SUM(occupied_hours) / SUM(available_hours) AS occupancy,
       COUNT(DISTINCT machine_id) AS machines
FROM {T('g_machine_day')}
WHERE {PERIOD}
GROUP BY theme, zone_name"""),

    "zone_week": ("Zone theo per day, weekly", True, f"""
SELECT DATE_TRUNC('WEEK', gaming_date) AS week, zone_name,
       SUM(theo_usd) / COUNT(DISTINCT gaming_date) AS theo_per_day,
       SUM(occupied_hours) / SUM(available_hours) AS occupancy,
       MAX(CAST(entrance_walkway_closed AS INT)) AS walkway_closed
FROM {T('g_machine_day')}
WHERE {PERIOD}
GROUP BY ALL"""),

    "daily": ("Daily floor", True, f"""
SELECT gaming_date, local_weekday, COALESCE(events_active, 'none') AS event,
       coin_in_usd, theo_usd, house_win_usd, occupied_machine_hours, total_zone_entries_observed,
       comp_cost_usd, faults_opened
FROM {T('g_property_day')}
WHERE {PERIOD}"""),

    "weekday": ("Coin-in by weekday", True, f"""
SELECT CASE local_weekday WHEN 'Mon' THEN '1 Mon' WHEN 'Tue' THEN '2 Tue' WHEN 'Wed' THEN '3 Wed'
         WHEN 'Thu' THEN '4 Thu' WHEN 'Fri' THEN '5 Fri' WHEN 'Sat' THEN '6 Sat' ELSE '7 Sun' END AS weekday,
       AVG(coin_in_usd) AS avg_coin_in_usd, COUNT(*) AS days
FROM {T('g_property_day')}
WHERE {PERIOD} AND events_active IS NULL
GROUP BY 1"""),

    "event_lift": ("Event lift vs weekday baseline", False, f"""
SELECT event_name, event_type, local_scope, days, coin_in_lift, extra_coin_in_usd, extra_theo_usd
FROM {T('g_event_lift')}"""),

    "city": ("Casino vs Las Vegas (real LVCVA)", False, f"""
WITH casino AS (
  SELECT DATE_FORMAT(gaming_date, 'yyyy-MM') AS month, AVG(coin_in_usd) AS casino_coin_in_per_day
  FROM {T('g_property_day')} GROUP BY 1
)
SELECT TO_DATE(c.month || '-01') AS month_start,
       c.casino_coin_in_per_day / FIRST_VALUE(c.casino_coin_in_per_day) OVER (ORDER BY c.month) AS casino_index,
       CAST(v.mean_visitors_per_calendar_day AS DOUBLE)
         / FIRST_VALUE(CAST(v.mean_visitors_per_calendar_day AS DOUBLE)) OVER (ORDER BY c.month) AS lv_visitors_index,
       CAST(v.visitor_yoy_ratio AS DOUBLE) AS lv_visitor_yoy
FROM casino c JOIN {T('city_visitation_monthly')} v USING (month)"""),

    "downtime": ("Downtime and lost theo by month x manufacturer", True, f"""
WITH rate AS (
  SELECT machine_id, SUM(theo_usd) / NULLIF(SUM(available_hours), 0) AS theo_per_available_hour
  FROM {T('g_machine_day')} WHERE {PERIOD} GROUP BY machine_id
)
SELECT TO_DATE(d.month || '-01') AS month_start, d.manufacturer,
       SUM(d.downtime_hours) AS downtime_hours,
       SUM(d.downtime_hours * r.theo_per_available_hour) AS lost_theo_usd
FROM {T('g_machine_day')} d JOIN rate r USING (machine_id)
WHERE {PERIOD.replace('gaming_date', 'd.gaming_date')}
GROUP BY ALL"""),

    "faults": ("Fault tickets", True, f"""
SELECT TO_DATE(DATE_FORMAT(gaming_date, 'yyyy-MM') || '-01') AS month_start, shift, manufacturer, zone_name,
       COUNT(*) AS tickets, AVG(wait_hours) AS avg_wait_hours, AVG(fix_hours) AS avg_fix_hours,
       SUM(down_hours) AS down_hours
FROM {T('g_fault_tickets')}
WHERE event_type = 'fault_repair' AND {PERIOD}
GROUP BY ALL"""),

    "reliability": ("Faults per 1,000 machine-days", True, f"""
WITH exposure AS (
  SELECT manufacturer, COUNT(*) AS machine_days FROM {T('g_machine_day')} WHERE {PERIOD} GROUP BY manufacturer
),
f AS (
  SELECT manufacturer, COUNT(*) AS faults, AVG(wait_hours) AS avg_wait_hours, AVG(down_hours) AS avg_down_hours
  FROM {T('g_fault_tickets')} WHERE event_type = 'fault_repair' AND {PERIOD} GROUP BY manufacturer
)
SELECT manufacturer, machine_days, faults, 1000.0 * faults / machine_days AS faults_per_1000_machine_days,
       avg_wait_hours, avg_down_hours
FROM exposure JOIN f USING (manufacturer)"""),

    "staff": ("Slot technician headcount", True, f"""
SELECT TO_DATE(DATE_FORMAT(gaming_date, 'yyyy-MM') || '-01') AS month_start, shift,
       AVG(planned_techs) AS planned_techs, AVG(actual_techs) AS actual_techs
FROM {T('g_tech_staffing')}
WHERE {PERIOD}
GROUP BY ALL"""),

    "players": ("Tracked players (period)", True, f"""
SELECT player_id,
       ANY_VALUE(opening_tier) AS tier,
       ANY_VALUE(home_region) AS home_region,
       ANY_VALUE(age_band) AS age_band,
       ANY_VALUE(theo_decile) AS theo_decile,
       SUM(coin_in_usd) AS coin_in_usd,
       SUM(payout_usd) AS payout_usd,
       SUM(player_net_usd) AS player_net_usd,
       SUM(house_win_usd) AS house_win_usd,
       SUM(theo_usd) AS theo_usd,
       SUM(comp_cost_usd) AS comp_cost_usd,
       CASE WHEN SUM(player_net_usd) > 0 THEN 1 ELSE 0 END AS ahead
FROM {T('g_player_period')}
WHERE month_start BETWEEN DATE_TRUNC('MONTH', :start_date) AND :end_date AND coin_in_usd > 0
GROUP BY player_id"""),

    "comp_month": ("Comp program by month", False, f"""
WITH p AS (
  SELECT month_start, SUM(theo_usd) AS tracked_theo_usd, SUM(comp_cost_usd) AS comp_cost_usd,
         SUM(comp_face_value_usd) AS comp_face_value_usd, SUM(points_earned) AS points_earned,
         SUM(points_redeemed) AS points_redeemed
  FROM {T('g_player_period')} GROUP BY month_start
),
r AS (
  SELECT TO_DATE(DATE_FORMAT(gaming_date, 'yyyy-MM') || '-01') AS month_start,
         SUM(redemptions) AS redemptions, SUM(points_redeemed) AS ledger_points_redeemed
  FROM {T('g_comp_redemptions')} GROUP BY 1
)
SELECT p.*, r.redemptions,
       p.comp_cost_usd / p.tracked_theo_usd AS comp_reinvestment,
       r.ledger_points_redeemed / r.redemptions AS points_per_redemption,
       p.comp_face_value_usd / p.points_redeemed * 100 AS face_cents_per_point
FROM p JOIN r USING (month_start)"""),

    "comp_benefit": ("Points price of each comp", False, f"""
SELECT TO_DATE(DATE_FORMAT(gaming_date, 'yyyy-MM') || '-01') AS month_start, benefit_id,
       SUM(points_redeemed) / SUM(redemptions) AS points_per_redemption,
       SUM(face_value_usd) / SUM(redemptions) AS face_value_usd
FROM {T('g_comp_redemptions')}
GROUP BY ALL"""),

    "forecast": ("Forecast vs actual", False, f"""
SELECT gaming_date, split, COALESCE(events_active, 'none') AS event, actual, pred_constant, pred_weekday, pred_weekday_event
FROM {T('g_forecast')}"""),

    "forecast_scores": ("Holdout scores", False, f"""
SELECT split, model, mae_usd, mape, days FROM {T('g_forecast_scores')}"""),

    "budget": ("Budget plan", False, f"""
SELECT action_type_id, name, quantity, targets, cost_usd, lead_days, evidence, expected_effect, uncertainty, measurement
FROM {T('g_budget_plan')}"""),

    "budget_total": ("Budget totals", False, f"""
SELECT SUM(cost_usd) AS spent_usd, 100000 - SUM(cost_usd) AS kept_usd,
       COUNT_IF(action_type_id <> 'A-HOLD') AS action_types
FROM {T('g_budget_plan')}"""),
}

PARAMS = [("start_date", "2025-01-01"), ("end_date", "2025-06-30")]


def dataset_json(key):
    display, uses_period, sql = DATASETS[key]
    ds = {"name": key, "displayName": display, "queryLines": [l + "\n" for l in sql.strip().splitlines()]}
    if uses_period:
        ds["parameters"] = [
            {
                "displayName": k,
                "keyword": k,
                "dataType": "DATE",
                "defaultSelection": {"values": {"dataType": "DATE", "values": [{"value": f"{v}T00:00:00.000"}]}},
            }
            for k, v in PARAMS
        ]
    return ds


# ---------------------------------------------------------------- widgets

_n = 0


def _name(prefix):
    global _n
    _n += 1
    return f"{prefix}_{_n}"


def place(widget, x, y, w, h):
    return {"widget": widget, "position": {"x": x, "y": y, "width": w, "height": h}}


def text(lines):
    return {"name": _name("text"), "multilineTextboxSpec": {"lines": lines}}


def frame(title, description=None):
    f = {"showTitle": True, "title": title}
    if description:
        f["showDescription"] = True
        f["description"] = description
    return f


USD = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact",
       "decimalPlaces": {"type": "max", "places": 1}}
PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
NUM = {"type": "number-plain", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 2}}


def query(ds, fields, disaggregated):
    return [{"name": "main_query", "query": {
        "datasetName": ds,
        "fields": [{"name": n, "expression": e} for n, e in fields],
        "disaggregated": disaggregated,
    }}]


def counter(ds, field, expr, title, fmt=None, description=None):
    value = {"fieldName": field, "displayName": title}
    if fmt:
        value["format"] = fmt
    return {
        "name": _name("counter"),
        "queries": query(ds, [(field, expr)], False),
        "spec": {"version": 2, "widgetType": "counter", "encodings": {"value": value},
                 "frame": frame(title, description)},
    }


def chart(kind, ds, x, y, title, color=None, x_type="categorical", y_fmt=None, description=None,
          disaggregated=True, y_title=None, x_title=None, extra_y=None, sort_x=None):
    """x, y, color: (field_name, expression). extra_y adds more y series (multi-series line)."""
    fields = [x] + ([y] if y else []) + ([color] if color else []) + (extra_y or [])
    enc = {"x": {"fieldName": x[0], "scale": {"type": x_type}, "displayName": x_title or x[0]}}
    if sort_x and x_type == "categorical":
        enc["x"]["scale"]["sort"] = {"by": sort_x}
    if extra_y:
        enc["y"] = {"scale": {"type": "quantitative"},
                    "fields": [{"fieldName": f[0], "displayName": f[0]} for f in [y] + extra_y]}
        if y_fmt:
            enc["y"]["format"] = y_fmt
    else:
        enc["y"] = {"fieldName": y[0], "scale": {"type": "quantitative"}, "displayName": y_title or y[0]}
        if y_fmt:
            enc["y"]["format"] = y_fmt
    if color:
        enc["color"] = {"fieldName": color[0], "scale": {"type": "categorical"}, "displayName": color[0]}
    return {
        "name": _name(kind),
        "queries": query(ds, fields, disaggregated),
        "spec": {"version": 3, "widgetType": kind, "encodings": enc, "frame": frame(title, description)},
    }


def heatmap(ds, x, y, color, title, description=None):
    return {
        "name": _name("heatmap"),
        "queries": query(ds, [(x, f"`{x}`"), (y, f"`{y}`"), (color, f"`{color}`")], True),
        "spec": {"version": 3, "widgetType": "heatmap", "encodings": {
            "x": {"fieldName": x, "scale": {"type": "categorical"}, "displayName": x},
            "y": {"fieldName": y, "scale": {"type": "categorical"}, "displayName": y},
            "color": {"fieldName": color, "scale": {"type": "quantitative"}, "displayName": color,
                      "format": {"type": "number-currency", "currencyCode": "USD",
                                 "decimalPlaces": {"type": "exact", "places": 1}}},
        }, "frame": frame(title, description)},
    }


def table(ds, columns, title, description=None):
    """columns: list of (field, display, kind) with kind in string|integer|float|usd|pct."""
    cols = []
    for i, (field, display, kind) in enumerate(columns):
        c = {
            "fieldName": field,
            "displayName": display,
            "title": display,
            "type": {"string": "string", "integer": "integer"}.get(kind, "float"),
            "displayAs": "string" if kind == "string" else "number",
            "visible": True,
            "order": 100000 + i,
            "alignContent": "left" if kind == "string" else "right",
            "allowSearch": kind == "string",
            "booleanValues": ["false", "true"],
            "imageUrlTemplate": "{{ @ }}",
            "imageTitleTemplate": "{{ @ }}",
            "imageWidth": "",
            "imageHeight": "",
            "linkUrlTemplate": "{{ @ }}",
            "linkTextTemplate": "{{ @ }}",
            "linkTitleTemplate": "{{ @ }}",
            "linkOpenInNewTab": True,
            "highlightLinks": False,
            "useMonospaceFont": False,
            "preserveWhitespace": False,
            "allowHTML": False,
        }
        if kind == "usd":
            c["numberFormat"] = "$0,0"
        elif kind == "pct":
            c["numberFormat"] = "0.0%"
        elif kind == "float":
            c["numberFormat"] = "0.00"
        elif kind == "integer":
            c["numberFormat"] = "0"
        cols.append(c)
    return {
        "name": _name("table"),
        "queries": query(ds, [(f, f"`{f}`") for f, _, _ in columns], True),
        "spec": {"version": 1, "widgetType": "table", "encodings": {"columns": cols},
                 "invisibleColumns": [], "allowHTMLByDefault": False, "itemsPerPage": 25,
                 "condensed": True, "withRowNumber": False, "frame": frame(title, description)},
    }


def period_pickers(datasets, y=0):
    """Two date pickers bound to :start_date / :end_date of every dataset on the page."""
    out = []
    for i, (kw, label) in enumerate([("start_date", "Period start"), ("end_date", "Period end")]):
        queries, fields = [], []
        for ds in datasets:
            qn = f"param_{ds}_{kw}"
            queries.append({"name": qn, "query": {"datasetName": ds,
                                                  "parameters": [{"name": kw, "keyword": kw}],
                                                  "disaggregated": False}})
            fields.append({"parameterName": kw, "queryName": qn})
        w = {"name": _name("period"), "queries": queries,
             "spec": {"version": 2, "widgetType": "filter-date-picker",
                      "encodings": {"fields": fields}, "frame": frame(label)}}
        out.append(place(w, i, y, 1, 1))
    return out


def multi_filter(field, label, datasets, x, y):
    queries, fields = [], []
    for ds in datasets:
        qn = f"filter_{ds}_{field}"
        queries.append({"name": qn, "query": {"datasetName": ds,
                                              "fields": [{"name": field, "expression": f"`{field}`"}],
                                              "disaggregated": False}})
        fields.append({"fieldName": field, "displayName": label, "queryName": qn})
    w = {"name": _name("filter"), "queries": queries,
         "spec": {"version": 2, "widgetType": "filter-multi-select",
                  "encodings": {"fields": fields}, "frame": frame(label)}}
    return place(w, x, y, 1, 1)


def page(key, title, layout):
    return {"name": key, "displayName": title, "pageType": "PAGE_TYPE_CANVAS", "layout": layout}


def f(name):
    return (name, f"`{name}`")


# ---------------------------------------------------------------- pages

pages = []

# 1. Decision
pages.append(page("decision", "1 · The decision", [
    place(text([
        "# Luck, location, or a leak? Don't replace the bottom 10.\n",
        "**The manager's list mostly measures *where* machines sit, not *what* they are.** "
        "9 of the 10 lowest earners are in **Back Forty**, where every theme earns 41–55% less theo per available hour than the same theme at the Main Entrance. "
        "3 of the 10 were on the floor for only part of the period. Most of the rest are within normal luck (|z| < 2).\n\n",
        "**One real leak:** M-1158 (Desert Gold, Back Forty) pays on 38.5% of spins vs 31.5% in its published math, every month, and holds 3.0% vs 10% theo. Inspect it; don't replace it.\n\n",
        "**Plan: spend $28,500, keep $71,500.** Inspect 5 machines · one promotion weekend · wayfinding for Back Forty. Pages 2–8 trace each claim to the data.",
    ]), 0, 0, 4, 5),
    place(counter("budget_total", "spent_usd", "SUM(`spent_usd`)", "Budget spent", USD), 4, 0, 1, 2),
    place(counter("budget_total", "kept_usd", "SUM(`kept_usd`)", "Budget kept", USD), 5, 0, 1, 2),
    place(counter("kpi", "house_win_usd", "SUM(`house_win_usd`)", "House win (period)", USD), 4, 2, 1, 2),
    place(counter("kpi", "observed_hold", "SUM(`observed_hold`)", "Observed hold", PCT,
                  "Ratio of sums. Missouri benchmark ≈ 9.6% (real)."), 5, 2, 1, 2),
    place(table("budget", [
        ("action_type_id", "Action", "string"), ("quantity", "Qty", "integer"), ("targets", "Targets", "string"),
        ("cost_usd", "Cost", "usd"), ("lead_days", "Lead days", "integer"), ("expected_effect", "Expected effect", "string"),
        ("uncertainty", "Uncertainty", "string"), ("measurement", "How we'll know", "string"),
        ("evidence", "Evidence", "string"),
    ], "Priced plan (30 days from July 1, 2025)"), 0, 5, 6, 7),
]))

# 2. Machines
pages.append(page("machines", "2 · Machines: luck, location, leak", [
    *period_pickers(["scorecard", "zone_theme"]),
    multi_filter("zone_name", "Zone", ["scorecard", "zone_theme"], 2, 0),
    multi_filter("bank_id", "Bank", ["scorecard"], 3, 0),
    multi_filter("diagnosis", "Diagnosis", ["scorecard"], 4, 0),
    place(text([
        "**How to read this.** *Luck z* = (house win − theo) ÷ its standard deviation, from each game's per-spin payout variance × Σ bet². "
        "|z| < 2 is ordinary luck. *Hit z* compares payout-positive spins with the published hit probability; a large value means the game is not behaving like its math (a lead to inspect, not proof of wrongdoing). "
        "*Theo per available hour* removes luck and downtime: it measures demand for the machine where it stands.",
    ]), 0, 1, 6, 2),
    place(table("scorecard", [
        ("manager_rank", "Manager rank", "integer"), ("machine_id", "Machine", "string"), ("theme", "Theme", "string"),
        ("zone_name", "Zone", "string"), ("bank_id", "Bank", "string"), ("diagnosis", "Diagnosis", "string"),
        ("days_on_floor", "Days", "integer"), ("availability", "Avail.", "pct"), ("occupancy", "Occup.", "pct"),
        ("house_win_usd", "House win", "usd"), ("theo_usd", "Theo", "usd"), ("luck_usd", "Luck $", "usd"),
        ("luck_z", "Luck z", "float"), ("observed_hold", "Hold", "pct"), ("theo_hold", "Theo hold", "pct"),
        ("hit_rate", "Hit rate", "pct"), ("published_hit_rate", "Published hit", "pct"), ("hit_z", "Hit z", "float"),
        ("theo_per_available_hour", "Theo / avail. hr", "float"),
    ], "Machine scorecard — sort by Manager rank to see the GM's bottom 10"), 0, 3, 6, 9),
    place(heatmap("zone_theme", "zone_name", "theme", "theo_per_available_hour",
                  "Theo per available hour: same theme, different zone",
                  "Every theme is weakest in Back Forty → location, not machine."), 0, 12, 3, 7),
    place(chart("scatter", "scorecard", f("theo_per_available_hour"), f("luck_z"),
                "Demand vs luck (each dot = machine)", color=f("zone_name"), x_type="quantitative",
                x_title="Theo per available hour ($)", y_title="Luck z"), 3, 12, 3, 7),
]))

# 3. Demand
pages.append(page("demand", "3 · Demand: what changed and why", [
    *period_pickers(["daily", "zone_week", "weekday"]),
    multi_filter("zone_name", "Zone", ["zone_week"], 2, 0),
    place(text([
        "**Three drivers.** (1) **Weekday rhythm**: Saturday coin-in is ≈64% above Tuesday. "
        "(2) **Events**: citywide sports weekends and the casino's own slot tournament added 16–23%; conventions added little. "
        "(3) **Access**: the Main Entrance → Back Forty walkway was closed for renovation Mar 3–Apr 6; Back Forty theo fell ≈30% and recovered on reopening. "
        "June softened in line with Las Vegas visitation (real LVCVA data: −11% YoY).",
    ]), 0, 1, 6, 2),
    place(chart("line", "daily", ("gaming_date", "`gaming_date`"), f("coin_in_usd"), "Daily floor coin-in",
                x_type="temporal", y_fmt=USD, y_title="Coin-in"), 0, 3, 4, 5),
    place(chart("bar", "weekday", f("weekday"), f("avg_coin_in_usd"), "Average coin-in by weekday (no-event days)",
                y_fmt=USD, y_title="Avg coin-in"), 4, 3, 2, 5),
    place(chart("line", "zone_week", ("week", "`week`"), f("theo_per_day"), "Theo per day by zone (weekly)",
                color=f("zone_name"), x_type="temporal", y_fmt=USD, y_title="Theo / day",
                description="Back Forty dips during the walkway closure (weeks of Mar 3 – Mar 31)."), 0, 8, 4, 6),
    place(table("event_lift", [
        ("event_name", "Event", "string"), ("event_type", "Type", "string"), ("local_scope", "Scope", "string"),
        ("days", "Days", "integer"), ("coin_in_lift", "Lift vs weekday", "pct"),
        ("extra_coin_in_usd", "Extra coin-in", "usd"), ("extra_theo_usd", "Extra theo", "usd"),
    ], "Event lift vs no-event weekday baseline (full period)"), 4, 8, 2, 6),
    place(chart("line", "city", ("month_start", "`month_start`"), f("casino_index"), "Casino vs Las Vegas visitors (Jan = 1.0)",
                x_type="temporal", extra_y=[f("lv_visitors_index")],
                description="LVCVA visitors per day (real, published after 2025, so not a forecast input)."), 0, 14, 3, 5),
]))

# 4. Downtime
pages.append(page("downtime", "4 · Downtime: how much and when", [
    *period_pickers(["downtime", "faults", "reliability", "staff"]),
    multi_filter("manufacturer", "Manufacturer", ["downtime", "faults", "reliability"], 2, 0),
    place(text([
        "**Downtime is real but small**: ≈5,000 machine-hours in six months (≈0.4% of scheduled machine-hours), worth ≈$90k theo at each machine's own earning rate, an upper bound since some play moves to a neighbour. "
        "**Ridgeline** faults 2.4–3.6× as often as the other makers. **Waits spiked in May** when day-shift techs fell from ≈1.7 to 0.9 vs plan; grave shift has one tech and the longest waits. "
        "A 30-day technician ($11,520) or Ridgeline preventive sweep ($9,000) would recover only ≈$1–4k theo in the horizon, so neither is funded.",
    ]), 0, 1, 6, 2),
    place(chart("bar", "downtime", ("month_start", "`month_start`"), f("lost_theo_usd"), "Lost theo from downtime",
                color=f("manufacturer"), x_type="temporal", y_fmt=USD, y_title="Lost theo"), 0, 3, 3, 5),
    place(chart("bar", "downtime", ("month_start", "`month_start`"), f("downtime_hours"), "Downtime hours",
                color=f("manufacturer"), x_type="temporal", y_title="Hours"), 3, 3, 3, 5),
    place(chart("line", "staff", ("month_start", "`month_start`"), f("actual_techs"), "Slot techs on shift (actual)",
                color=f("shift"), x_type="temporal", y_title="Avg techs", disaggregated=True), 0, 8, 3, 5),
    place(chart("bar", "faults", ("month_start", "`month_start`"), ("avg_wait_hours", "AVG(`avg_wait_hours`)"),
                "Average wait for a technician (hours)", color=f("shift"), x_type="temporal", disaggregated=False,
                y_title="Hours"), 3, 8, 3, 5),
    place(table("reliability", [
        ("manufacturer", "Manufacturer", "string"), ("machine_days", "Machine-days", "integer"),
        ("faults", "Faults", "integer"), ("faults_per_1000_machine_days", "Faults / 1,000 machine-days", "float"),
        ("avg_wait_hours", "Avg wait (h)", "float"), ("avg_down_hours", "Avg down (h)", "float"),
    ], "Reliability by manufacturer (exposure-adjusted)"), 0, 13, 6, 3),
]))

# 5. Players
pages.append(page("players", "5 · Tracked players", [
    *period_pickers(["players"]),
    multi_filter("tier", "Opening tier", ["players"], 2, 0),
    multi_filter("home_region", "Home region", ["players"], 3, 0),
    multi_filter("age_band", "Age band", ["players"], 4, 0),
    place(text([
        "**Carded play only** (≈66% of coin-in); uncarded guests are invisible here. Players' net = payout − coin-in. "
        "About 16% of tracked players finished the period ahead. Results are concentrated: the top 10% of players by theo generate ≈64% of tracked house win; the top 1% ≈20%. "
        "We do **not** recommend targeting heavy losers with promotions.",
    ]), 0, 1, 6, 2),
    place(counter("players", "n", "COUNT(`player_id`)", "Tracked players", NUM), 0, 3, 1, 2),
    place(counter("players", "coin_in_usd", "SUM(`coin_in_usd`)", "Wagered (coin-in)", USD), 1, 3, 1, 2),
    place(counter("players", "payout_usd", "SUM(`payout_usd`)", "Got back (payout)", USD), 2, 3, 1, 2),
    place(counter("players", "player_net_usd", "SUM(`player_net_usd`)", "Players' net", USD), 3, 3, 1, 2),
    place(counter("players", "theo_usd", "SUM(`theo_usd`)", "Expected loss (theo)", USD), 4, 3, 1, 2),
    place(counter("players", "ahead", "AVG(`ahead`)", "Share of players ahead", PCT), 5, 3, 1, 2),
    place(chart("bar", "players", ("theo_decile", "`theo_decile`"), ("house_win_usd", "SUM(`house_win_usd`)"),
                "House win by player decile (1 = top 10% by theo)", disaggregated=False, y_fmt=USD,
                y_title="House win"), 0, 5, 3, 6),
    place(chart("bar", "players", ("tier", "`tier`"), ("player_net_usd", "SUM(`player_net_usd`)"),
                "Players' net by opening tier", disaggregated=False, y_fmt=USD, y_title="Players' net"), 3, 5, 3, 6),
]))

# 6. Comps
pages.append(page("comps", "6 · Comp program", [
    place(text([
        "**What changed: on May 1 every comp's points price roughly halved** (e.g. a beer went from ≈114 to ≈53 points); menu value and cost per item did not change. "
        "Redemptions rose only ≈8% and comp cost rose from 1.11% of tracked theo (Jan) to 1.32% (Jun); there is no visible lift in play. "
        "Points are earned ~20× faster than redeemed, so the cheaper redemption price raises the value of the unredeemed balance. "
        "Comp cost is counted once (it sits inside POS cost of goods).",
    ]), 0, 0, 6, 2),
    place(chart("line", "comp_month", ("month_start", "`month_start`"), f("comp_reinvestment"),
                "Comp reinvestment (comp cost ÷ tracked theo)", x_type="temporal", y_fmt=PCT,
                y_title="Reinvestment"), 0, 2, 3, 5),
    place(chart("line", "comp_month", ("month_start", "`month_start`"), f("points_per_redemption"),
                "Average points per redemption", x_type="temporal", y_title="Points"), 3, 2, 3, 5),
    place(chart("line", "comp_benefit", ("month_start", "`month_start`"), f("points_per_redemption"),
                "Points price by comp item", color=f("benefit_id"), x_type="temporal", y_title="Points"), 0, 7, 3, 6),
    place(chart("bar", "comp_month", ("month_start", "`month_start`"), f("comp_cost_usd"),
                "Comp cost to the house", x_type="temporal", y_fmt=USD, y_title="Comp cost"), 3, 7, 3, 6),
]))

# 7. Model
pages.append(page("model", "7 · Model & validation", [
    place(text([
        "**Question:** how much will the floor wager on a given day? **Train:** Jan 1–Apr 30. **Holdout:** May 1–Jun 30 (time split, frozen before testing). "
        "**Baseline:** constant training-period daily mean. **Model:** training-period mean for that weekday. **Variant:** weekday mean (no-event days) × average training-period event uplift, applied only to events announced in advance. "
        "No lagged actuals from the holdout are used. Later-published tourism data is not an input.\n\n",
        "**Decision it changes:** Fri–Sun run ≈30–60% above Tue–Wed, and pre-announced events add ≈18% more. So technician coverage and the funded promotion weekend go on Fri–Sun, and the forecast is the counterfactual for measuring the promotion's lift.",
    ]), 0, 0, 6, 3),
    place(chart("line", "forecast", ("gaming_date", "`gaming_date`"), f("actual"), "Actual vs forecast daily coin-in",
                x_type="temporal", extra_y=[f("pred_weekday_event"), f("pred_weekday"), f("pred_constant")],
                y_fmt=USD), 0, 3, 4, 7),
    place(table("forecast_scores", [
        ("split", "Split", "string"), ("model", "Model", "string"), ("mae_usd", "MAE", "usd"),
        ("mape", "MAPE", "pct"), ("days", "Days", "integer"),
    ], "Mean absolute error (lower is better)"), 4, 3, 2, 7),
]))

# 8. Evidence
pages.append(page("evidence", "8 · Claims & evidence", [
    place(text([
        "| Claim | Table → query | Result | Alternative tested | Limitation |\n",
        "|---|---|---|---|---|\n",
        "| Bottom-10 is mostly location | `g_machine_day`: theo ÷ available hours by theme × zone | Back Forty 41–55% lower for every theme | Bad themes? Same theme performs well elsewhere | Zone and placement were not randomly assigned |\n",
        "| Access drives Back Forty | weekly zone theo vs `floor_walkways` closure | ≈−30% during Mar 3–Apr 6, recovered after | Seasonality? Main Entrance flat over the same weeks | One closure episode |\n",
        "| Replacing in place doesn't fix it | slot L-38-5: M-1120 → M-5076 (May 13) | $6.00 → $6.39 theo / avail. hr | Newer game might ramp up | 49 days after the swap |\n",
        "| New machines redistribute play | Aurora bank B-51 (Mar 24) vs rest of floor | +$5.4k/day on new bank, −$8k/day elsewhere | June citywide slowdown also lowers the rest | Before/after, no control |\n",
        "| M-1158 is a leak to inspect | `machine_day` × `game_math`: hits vs `hit_probability` | 38.5% vs 31.5% every month, z≈124 | Luck? z this large is not chance | Could be a meter/config error; inspection decides |\n",
        "| Other low earners are luck | luck z from Σ bet² × payout variance | SD of z = 1.09 across 310 machines; 20 have abs(z) > 2 vs ≈14 expected | Mis-specified variance? SD near 1 says no | Variance model assumes independent spins |\n",
        "| Promotion weekend pays | `g_event_lift`: Winter Slot Tournament | +18% coin-in, ≈+$80k theo, no dip after | Citywide event? none that weekend | Single example |\n",
        "| Comp points price halved May 1 | `loyalty_ledger` redeem points per benefit | Beer 114 → 53 points, same face value | Mix shift? every item halved | Reason for the change not in data |\n",
        "| Downtime too small to fund staff | `g_fault_tickets`, `g_tech_staffing` | ≈$90k theo / 6 months, May wait spike with day-shift gap | Demand loss? down hours × own theo rate | Upper bound: players may move to another machine |\n\n",
        "**AI use:** an AI coding assistant (Cursor) helped write SQL, the dashboard JSON and the text. All numbers come from the queries above and were re-run on Databricks.",
    ]), 0, 0, 6, 14),
]))


dashboard = {
    "datasets": [dataset_json(k) for k in DATASETS],
    "pages": pages,
}

with open(OUT, "w") as fh:
    json.dump(dashboard, fh, indent=2, ensure_ascii=False)
print(f"wrote {OUT}: {len(dashboard['datasets'])} datasets, {len(pages)} pages, "
      f"{sum(len(p['layout']) for p in pages)} widgets")
