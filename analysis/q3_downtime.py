from _db import connect

con = connect()

con.sql("""
CREATE TABLE ops AS
SELECT o.*, m.manufacturer,
       date_diff('second', opened_at_utc, available_at_utc) / 3600.0 AS down_hours,
       date_diff('second', opened_at_utc, work_started_at_utc) / 3600.0 AS wait_hours,
       date_diff('second', work_started_at_utc, available_at_utc) / 3600.0 AS fix_hours,
       hour(opened_at_local) AS open_hour,
       strftime(opened_at_local, '%Y-%m') AS mo
FROM operations o JOIN machines m USING (machine_id)
""")

print(con.sql("""
SELECT event_type, count(*) n, round(sum(down_hours)) down_h, round(median(wait_hours),2) med_wait,
       round(median(fix_hours),2) med_fix, round(sum(direct_cost_cents)/100) cost
FROM ops GROUP BY 1
""").df())

print("== fault_repair by month ==")
print(con.sql("""
SELECT mo, count(*) n, round(sum(down_hours)) down_h, round(avg(wait_hours),2) avg_wait, round(avg(fix_hours),2) avg_fix
FROM ops WHERE event_type='fault_repair' GROUP BY 1 ORDER BY 1
""").df())

print("== fault_repair by manufacturer ==")
print(con.sql("""
WITH mdays AS (SELECT manufacturer, count(*) md FROM machine_day JOIN machines USING (machine_id) WHERE active GROUP BY 1)
SELECT manufacturer, count(*) n, round(count(*)*1000.0/any_value(md),2) per_1000_mdays,
       round(avg(down_hours),2) avg_down, round(avg(wait_hours),2) avg_wait
FROM ops JOIN mdays USING (manufacturer) WHERE event_type='fault_repair' GROUP BY 1
""").df())

print("== fault wait by opened hour bucket ==")
print(con.sql("""
SELECT CASE WHEN open_hour BETWEEN 6 AND 13 THEN '1 day 06-14'
            WHEN open_hour BETWEEN 14 AND 21 THEN '2 swing 14-22' ELSE '3 grave 22-06' END shift,
       count(*) n, round(avg(wait_hours),2) avg_wait, round(avg(fix_hours),2) avg_fix, round(sum(down_hours)) down_h
FROM ops WHERE event_type='fault_repair' GROUP BY 1 ORDER BY 1
""").df())

print("== by month x shift avg wait ==")
print(con.sql("""
PIVOT (SELECT mo, CASE WHEN open_hour BETWEEN 6 AND 13 THEN 'day' WHEN open_hour BETWEEN 14 AND 21 THEN 'swing' ELSE 'grave' END s, wait_hours
       FROM ops WHERE event_type='fault_repair') ON s USING round(avg(wait_hours),2) GROUP BY mo ORDER BY mo
""").df())

print("== slot tech roster ==")
print(con.sql("""
SELECT strftime(gaming_date,'%Y-%m') mo, shift, round(avg(planned_headcount),2) plan, round(avg(actual_headcount),2) actual
FROM shift_roster WHERE role='slot_tech' GROUP BY 1,2 ORDER BY 2,1
""").df())

print("== scheduled maintenance by month/manufacturer ==")
print(con.sql("""
PIVOT (SELECT mo, manufacturer FROM ops WHERE event_type='scheduled_maintenance') ON manufacturer USING count(*) GROUP BY mo ORDER BY mo
""").df())

print("== lost play estimate: downtime hours x zone theo per occupied... use theo/available hr by machine ==")
print(con.sql("""
SELECT strftime(gaming_date,'%Y-%m') mo,
  round(sum((d.scheduled_seconds - d.available_seconds)/3600.0)) down_h,
  round(sum((d.scheduled_seconds - d.available_seconds)/3600.0 * s.theo_per_avail_hour)) lost_theo
FROM machine_day d JOIN (
  SELECT machine_id, sum(theo_cents)/100.0/nullif(sum(available_seconds)/3600.0,0) theo_per_avail_hour
  FROM machine_day WHERE active GROUP BY 1) s USING (machine_id)
WHERE d.active GROUP BY 1 ORDER BY 1
""").df())
