from _db import connect

con = connect()

print("== Forecast: train Jan-Apr, test May-Jun ==")
con.sql("""
CREATE TABLE f AS
WITH train AS (SELECT * FROM property_day WHERE gaming_date < DATE '2025-05-01'),
     wk AS (SELECT local_weekday, avg(coin_in_usd) wk_mean FROM train WHERE events_active IS NULL GROUP BY 1),
     ev AS (SELECT avg(coin_in_usd) / (SELECT avg(coin_in_usd) FROM train WHERE events_active IS NULL) lift
            FROM train WHERE events_active IS NOT NULL),
     const AS (SELECT avg(coin_in_usd) c FROM train)
SELECT p.gaming_date, p.local_weekday, p.events_active, p.coin_in_usd::DOUBLE actual,
       const.c AS pred_constant,
       wk.wk_mean AS pred_weekday,
       wk.wk_mean * CASE WHEN p.events_active IS NOT NULL THEN ev.lift ELSE 1 END AS pred_weekday_event,
       p.gaming_date >= DATE '2025-05-01' AS is_test
FROM property_day p JOIN wk USING (local_weekday), ev, const
""")
print(con.sql("""
SELECT is_test, round(avg(abs(actual-pred_constant))) mae_constant, round(avg(abs(actual-pred_weekday))) mae_weekday,
       round(avg(abs(actual-pred_weekday_event))) mae_weekday_event,
       round(avg(abs(actual-pred_weekday_event)/actual),4) mape_wke
FROM f GROUP BY 1
""").df())

print("== Missouri benchmark hold ==")
print(con.sql("""
SELECT month, round(sum(agr_usd)/sum(handle_usd),4) hold, sum(slot_units) units FROM benchmark_state_monthly GROUP BY 1 ORDER BY 1
""").df())
print(con.sql("SELECT month, visitor_volume, round(visitor_yoy_ratio,4) yoy, convention_attendance, round(hotel_occupancy_ratio,3) occ FROM city_visitation_monthly ORDER BY 1").df())

print("== Floor capacity ==")
print(con.sql("""
WITH slots AS (SELECT zone_id, count(*) n_slots FROM floor_locations WHERE node_type='slot' GROUP BY 1),
     used AS (SELECT split_part(location_id,'-',2) b, zone_id, count(DISTINCT location_id) used
              FROM prepared_daily_view WHERE gaming_date = DATE '2025-06-30' AND active GROUP BY 1,2)
SELECT s.zone_id, s.n_slots, sum(u.used) used FROM slots s LEFT JOIN used u USING (zone_id) GROUP BY 1,2 ORDER BY 1
""").df())
print(con.sql("SELECT node_type, count(*) FROM floor_locations GROUP BY 1").df())
print(con.sql("SELECT * FROM floor_locations WHERE node_type IN ('zone','entrance') ORDER BY node_type").df())

print("== Retired/new machines ==")
print(con.sql("SELECT * FROM machines WHERE retire_date IS NOT NULL OR install_date > DATE '2025-01-01'").df())

print("== Theme performance per available hour (exposure-adjusted), zone-controlled ==")
print(con.sql("""
SELECT theme, round(sum(theo_usd)/sum(available_hours),2) theo_hr, round(sum(occupied_hours)/sum(available_hours),3) occ,
       count(DISTINCT machine_id) n
FROM prepared_daily_view WHERE active GROUP BY 1 ORDER BY theo_hr
""").df())
print(con.sql("""
PIVOT (SELECT theme, zone_name, round(sum(theo_usd)/sum(available_hours),1) t
       FROM prepared_daily_view WHERE active GROUP BY 1,2)
ON zone_name USING first(t) GROUP BY theme ORDER BY theme
""").df())
