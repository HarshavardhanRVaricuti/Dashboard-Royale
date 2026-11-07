from _db import connect

con = connect()

con.sql("""
CREATE TABLE p AS
SELECT player_id, any_value(opening_tier) tier, any_value(home_region) region, any_value(age_band) age,
       sum(tracked_coin_in_usd) ci, sum(tracked_payout_usd) po, sum(tracked_net_usd) net, sum(theo_usd) theo,
       sum(comp_cost_usd) comp_cost, sum(comp_face_value_usd) comp_face, sum(points_earned) pe, sum(points_redeemed) pr,
       sum(observed_visits) visits, sum(tracked_contribution_usd) contrib
FROM player_period GROUP BY 1
""")

print(con.sql("""
SELECT count(*) players, sum(ci>0) gamers, round(sum(ci)) coin_in, round(sum(po)) payout, round(sum(net)) net,
       round(sum(theo)) theo, round(avg((net>0)::int) FILTER (WHERE ci>0),3) share_ahead,
       round(median(net) FILTER (WHERE ci>0),2) median_net
FROM p
""").df())

print("== Concentration of losses (house win = -net) ==")
print(con.sql("""
WITH r AS (SELECT -net hw, theo, row_number() OVER (ORDER BY theo DESC) rk, count(*) OVER () n FROM p WHERE ci>0)
SELECT round(sum(theo) FILTER (WHERE rk <= n*0.01)/sum(theo),3) top1_theo,
       round(sum(theo) FILTER (WHERE rk <= n*0.10)/sum(theo),3) top10_theo,
       round(sum(hw) FILTER (WHERE rk <= n*0.01)/sum(hw),3) top1_win,
       round(sum(hw) FILTER (WHERE rk <= n*0.10)/sum(hw),3) top10_win
FROM r
""").df())
print(con.sql("""
WITH r AS (SELECT -net hw, row_number() OVER (ORDER BY -net DESC) rk, count(*) OVER () n FROM p WHERE ci>0)
SELECT round(sum(hw) FILTER (WHERE rk <= n*0.01)/sum(hw),3) top1_losers_share_of_win,
       round(sum(hw) FILTER (WHERE rk <= n*0.10)/sum(hw),3) top10_losers_share
FROM r
""").df())

print("== By tier ==")
print(con.sql("""
SELECT tier, count(*) n, round(sum(ci)) ci, round(sum(net)) net, round(sum(theo)) theo,
       round(avg((net>0)::int),3) ahead, round(sum(comp_cost)) comp_cost,
       round(sum(comp_cost)/nullif(sum(theo),0),4) reinvest
FROM p WHERE ci>0 GROUP BY 1 ORDER BY theo DESC
""").df())

print("== Comp by month ==")
print(con.sql("""
SELECT period_month, round(sum(theo_usd)) theo, round(sum(comp_cost_usd)) comp_cost, round(sum(comp_face_value_usd)) face,
       sum(comps_redeemed) n_comps, sum(points_earned) pe, sum(points_redeemed) pr,
       round(sum(comp_cost_usd)/sum(theo_usd),4) reinvest,
       round(sum(points_earned)/sum(tracked_coin_in_usd),4) pts_per_dollar,
       round(sum(comp_face_value_usd)/nullif(sum(points_redeemed),0),5) face_per_point
FROM player_period GROUP BY 1 ORDER BY 1
""").df())

print("== ledger redeem by month and benefit ==")
print(con.sql("""
SELECT strftime(event_at_utc - INTERVAL 14 HOUR,'%Y-%m') mo, count(*) n,
       round(sum(-points_delta)/count(*)) pts_per_redeem,
       round(sum(face_value_cents)/100.0/count(*),2) face_per_redeem,
       round(sum(face_value_cents)*1.0/sum(-points_delta),5) face_cents_per_pt,
       round(sum(economic_cost_cents)*1.0/sum(face_value_cents),3) cost_ratio
FROM loyalty_ledger WHERE event_type='redeem' GROUP BY 1 ORDER BY 1
""").df())
print(con.sql("""
SELECT strftime(event_at_utc - INTERVAL 14 HOUR,'%Y-%m') mo, count(*) n, sum(points_delta) pts
FROM loyalty_ledger WHERE event_type='award' GROUP BY 1 ORDER BY 1
""").df())
print(con.sql("""
SELECT benefit_id, strftime(event_at_utc - INTERVAL 14 HOUR,'%Y-%m') mo, count(*) n, round(avg(-points_delta)) pts,
       round(avg(face_value_cents)/100,2) face, round(avg(economic_cost_cents)/100,2) cost
FROM loyalty_ledger WHERE event_type='redeem' GROUP BY 1,2 ORDER BY 1,2
""").df())
