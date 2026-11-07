from _db import connect

con = connect()

con.sql("""
CREATE TABLE machine_scorecard AS
WITH d AS (
    SELECT md.*, gm.configured_rtp, gm.payout_multiplier_variance, gm.hit_probability
    FROM machine_day md
    JOIN game_math gm USING (config_id)
    WHERE md.active
)
SELECT
    machine_id,
    COUNT(*)                                          AS days_on_floor,
    SUM(scheduled_seconds) / 3600.0                   AS scheduled_hours,
    SUM(available_seconds) / 3600.0                   AS available_hours,
    SUM(available_seconds) / SUM(scheduled_seconds)   AS availability,
    SUM(occupied_seconds) / NULLIF(SUM(available_seconds), 0) AS occupancy,
    SUM(coin_in_cents) / 100.0                        AS coin_in,
    SUM(house_win_cents) / 100.0                      AS house_win,
    SUM(theo_cents) / 100.0                           AS theo,
    SUM(house_win_cents - theo_cents) / 100.0         AS luck,
    SQRT(SUM(sum_bet_squared * payout_multiplier_variance)) / 100.0 AS luck_sd,
    SUM(house_win_cents - theo_cents)
        / NULLIF(SQRT(SUM(sum_bet_squared * payout_multiplier_variance)), 0) AS luck_z,
    SUM(house_win_cents) / NULLIF(SUM(coin_in_cents), 0)::DOUBLE AS observed_hold,
    SUM(theo_cents) / NULLIF(SUM(coin_in_cents), 0)::DOUBLE      AS theo_hold,
    SUM(payout_positive_spins) / NULLIF(SUM(paid_spins), 0)::DOUBLE AS hit_rate,
    SUM(paid_spins * hit_probability) / NULLIF(SUM(paid_spins), 0) AS expected_hit_rate,
    (SUM(payout_positive_spins) - SUM(paid_spins * hit_probability))
        / NULLIF(SQRT(SUM(paid_spins * hit_probability * (1 - hit_probability))), 0) AS hit_z,
    SUM(theo_cents) / 100.0 / NULLIF(SUM(available_seconds) / 3600.0, 0) AS theo_per_avail_hour,
    SUM(house_win_cents) / 100.0 / NULLIF(SUM(available_seconds) / 3600.0, 0) AS win_per_avail_hour
FROM d
GROUP BY machine_id
""")

con.sql("""
CREATE TABLE scorecard AS
SELECT s.*, m.manufacturer, m.theme, m.install_date, m.retire_date, m.lease_class,
       p.zone_name, p.bank_id
FROM machine_scorecard s
JOIN machines m USING (machine_id)
LEFT JOIN (
    SELECT machine_id, ARG_MAX(zone_name, gaming_date) AS zone_name, ARG_MAX(bank_id, gaming_date) AS bank_id
    FROM prepared_daily_view WHERE active GROUP BY machine_id
) p USING (machine_id)
""")

print("== Manager's bottom 10 by raw house win ==")
print(con.sql("""
SELECT machine_id, theme, zone_name, days_on_floor, round(availability,3) av, round(occupancy,3) occ,
       round(house_win) hw, round(theo) theo, round(luck) luck, round(luck_z,2) z,
       round(observed_hold,4) hold, round(theo_hold,4) th, round(hit_z,1) hit_z, retire_date
FROM scorecard ORDER BY house_win LIMIT 10
""").df())

print("== Bottom 15 by theo per available hour ==")
print(con.sql("""
SELECT machine_id, theme, zone_name, bank_id, days_on_floor, round(availability,3) av, round(occupancy,3) occ,
       round(theo_per_avail_hour,2) theo_hr, round(luck_z,2) z, round(hit_z,1) hit_z
FROM scorecard ORDER BY theo_per_avail_hour LIMIT 15
""").df())

print("== Extreme luck z ==")
print(con.sql("""
SELECT machine_id, theme, zone_name, round(luck) luck, round(luck_z,2) z, round(observed_hold,4) hold,
       round(theo_hold,4) th, round(hit_rate,4) hr, round(expected_hit_rate,4) ehr, round(hit_z,1) hit_z
FROM scorecard WHERE abs(luck_z) > 2.5 OR abs(hit_z) > 4 ORDER BY luck_z
""").df())

print(con.sql("SELECT count(*) n, sum(abs(luck_z)>2) z2, sum(abs(luck_z)>3) z3, stddev(luck_z) sd FROM scorecard").df())

print("== Availability bottom ==")
print(con.sql("""
SELECT machine_id, theme, manufacturer, zone_name, round(availability,3) av, days_on_floor
FROM scorecard ORDER BY availability LIMIT 15
""").df())
print(con.sql("""
SELECT manufacturer, count(*) n, round(sum(available_hours)/sum(scheduled_hours),4) av
FROM scorecard GROUP BY 1 ORDER BY av
""").df())
print(con.sql("""
SELECT zone_name, count(*) n, round(sum(theo)/sum(available_hours),2) theo_hr,
       round(sum(occupancy*available_hours)/sum(available_hours),3) occ
FROM scorecard GROUP BY 1 ORDER BY theo_hr
""").df())
