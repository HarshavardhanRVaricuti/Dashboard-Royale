from _db import connect

con = connect()

print("== M-1158 by month: hit rate vs published ==")
print(con.sql("""
SELECT md.month, m.config_id, count(*) AS n_days, sum(m.paid_spins) spins,
       round(sum(m.payout_positive_spins)/sum(m.paid_spins),4) hit_rate,
       round(sum(m.house_win_cents)/sum(m.coin_in_cents),4) hold,
       round(sum(m.theo_cents)/sum(m.coin_in_cents),4) theo_hold
FROM machine_day m JOIN calendar_day md USING (gaming_date)
WHERE machine_id='M-1158' AND active GROUP BY 1,2 ORDER BY 1
""").df())
print(con.sql("SELECT * FROM placements WHERE machine_id='M-1158'").df())
print(con.sql("SELECT event_type, opened_at_local, available_at_utc, direct_cost_cents FROM operations WHERE machine_id='M-1158' ORDER BY 2").df())

print("== Hit-rate drift across all machines by month (count of machines with |hit_z|>4) ==")
print(con.sql("""
WITH x AS (
  SELECT machine_id, c.month,
    (sum(payout_positive_spins) - sum(paid_spins*g.hit_probability))
      / nullif(sqrt(sum(paid_spins*g.hit_probability*(1-g.hit_probability))),0) hz
  FROM machine_day m JOIN game_math g USING (config_id) JOIN calendar_day c USING (gaming_date)
  WHERE active GROUP BY 1,2)
SELECT machine_id, list(month || ':' || round(hz,1) ORDER BY month) FROM x
WHERE machine_id IN (SELECT machine_id FROM x WHERE abs(hz)>4) GROUP BY 1
""").df())

print("== Floor by month ==")
print(con.sql("""
SELECT strftime(gaming_date,'%Y-%m') mo, count(*) AS n_days,
  round(avg(coin_in_usd)) coin_in_day, round(sum(house_win_usd)) hw, round(sum(theo_usd)) theo,
  round(sum(house_win_usd)/sum(coin_in_usd),4) hold,
  round(avg(occupied_machine_hours)) occ_hrs_day, round(avg(available_machine_hours)) avail_hrs_day,
  round(avg(total_zone_entries_observed)) entries_day, round(avg(counter_coverage_share),3) cov,
  round(avg(carded_coin_in_share),3) carded,
  round(sum(comp_cost_usd)) comp_cost, round(sum(pos_cash_usd)) pos_cash, sum(faults_opened) faults,
  round(sum(contribution_after_supplied_costs_usd)) contrib
FROM property_day GROUP BY 1 ORDER BY 1
""").df())

print("== Theo by zone by month ($/day) ==")
print(con.sql("""
PIVOT (SELECT zone_name, month, sum(theo_usd)/count(DISTINCT gaming_date) t FROM prepared_daily_view WHERE active GROUP BY 1,2)
ON month USING round(first(t))
""").df())

print("== Back Forty weekly theo/occupancy around walkway closure 2025-03-03 .. 2025-04-07 ==")
print(con.sql("""
SELECT date_trunc('week', gaming_date) wk, zone_name,
  round(sum(theo_usd)/count(DISTINCT gaming_date)) theo_day,
  round(sum(occupied_hours)/sum(available_hours),3) occ
FROM prepared_daily_view WHERE active AND zone_name IN ('Back Forty','Main Entrance')
GROUP BY 1,2 ORDER BY 2,1
""").df())

print("== Weekday pattern ==")
print(con.sql("""
SELECT local_weekday, count(*) n, round(avg(coin_in_usd)) coin_in FROM property_day GROUP BY 1 ORDER BY coin_in
""").df())

print("== Event days vs not ==")
print(con.sql("""
SELECT events_active, count(*) n, round(avg(coin_in_usd)) coin_in, round(avg(total_zone_entries_observed)) ent
FROM property_day GROUP BY 1 ORDER BY 1
""").df())
