# Claims & Evidence appendix

All tables are in `workspace.dashboard_royale` and are built by `databricks/02_build_gold.sql`. Period: gaming dates 2025-01-01 to 2025-06-30.

| # | Claim | Table → query | Result | Alternative explanation tested | Limitation |
|---|---|---|---|---|---|
| 1 | The bottom 10 is mostly about location | `g_machine_day`: Σ theo ÷ Σ available hours by theme × zone | Back Forty is 41–55% lower for every theme | Bad themes? The same themes earn well elsewhere | Placement was not random |
| 2 | Access drives Back Forty | weekly zone theo per day vs `floor_walkways` closure (W-ENT-B40) | ≈−30% during Mar 3–Apr 6, recovered after reopening | Seasonality? Main Entrance was flat over the same weeks | One closure episode |
| 3 | Replacing a machine in place doesn't fix it | `g_machine_day`, slot L-38-5: M-1120 → M-5076 on May 13 | $6.00 → $6.39 theo per available hour | A new game might ramp up | Only 49 days after the swap |
| 4 | New machines mostly redistribute play | Aurora bank B-51 (installed Mar 24) vs rest of floor, walkway weeks excluded | +$5.4k/day on the new bank, −$8.1k/day elsewhere | June citywide slowdown also lowers the rest | Before/after comparison, no control |
| 5 | M-1158 is a lead to inspect | `g_machine_scorecard`: payout-positive spins vs `game_math.hit_probability` | 38.5% vs 31.5% in every month, hit z ≈ 124, hold 3.0% vs 10% theo | Luck? A z this large is not chance | Could be a meter or config error; the inspection decides. Not evidence of wrongdoing |
| 6 | Other low earners are within luck | luck z = Σ(house win − theo) ÷ √Σ(bet² × payout variance) | SD of z = 1.09 across 310 machines; 20 have abs(z) > 2 vs ≈14 expected | Mis-specified variance? SD near 1 says no | Assumes independent spins |
| 7 | Exposure distorts the manager's list | `g_machine_scorecard.days_on_floor` | 3 of the bottom 10 were on the floor for 49–132 days | — | — |
| 8 | Promotions lift play | `g_event_lift`: Winter Slot Tournament (Feb 21–23) | +18% coin-in vs the no-event weekday mean, ≈+$80k theo, no dip on surrounding days | A citywide event that weekend? None in `events` | Single example; July may differ |
| 9 | The comp points price halved on May 1 | `g_comp_redemptions`: points per redemption by benefit | e.g. beer 114 → 53 points with the same $9 face value; every item halved | Mix shift? Every item changed | The reason for the change is not in the data |
| 10 | Comp cost rose without a lift in play | `comp_month` dataset: comp cost ÷ tracked theo | 1.11% (Jan) → 1.32% (Jun); coin-in flat | Higher demand? Coin-in per day did not rise | Carded play only |
| 11 | Downtime is too small to fund staff | `g_fault_tickets`, `g_tech_staffing`, `g_machine_day` | ≈5,000 down hours, ≈$90k theo over 6 months; May waits spiked when day-shift techs averaged 0.9 vs 1.7 planned | Lost demand? Valued at each machine's own theo rate | Upper bound: players may switch machines |
| 12 | Ridgeline is least reliable | `g_manufacturer_reliability` | 40.4 faults per 1,000 machine-days vs 11.1 (Halcyon) and 16.7 (Northwind) | Older machines in busy zones? Rate is per machine-day | Machine age is not separated out |
| 13 | Weekday forecast beats the baseline | `g_forecast_scores`, holdout May–Jun | MAE $218k (constant) → $69k (weekday) → $51k (with events) | Overfitting? Frozen on Jan–Apr, scored on unseen months | Two holdout months |
| 14 | Player results are concentrated | `g_player_period`, deciles by full-period theo | Top 10% = 64% of tracked house win; top 1% ≈ 20%; 16% of players ahead | — | Carded only (≈66% of coin-in) |

## Budget arithmetic

Cost = quantity × (unit cost + daily cost × max(0, 30 − lead days)).

| Action | Calculation | Cost |
|---|---|---:|
| A-INSPECT × 5 | 5 × $1,200 | $6,000 |
| A-PROMO × 1 | 1 × $15,000 | $15,000 |
| A-WAYFINDING × 1 (Z-B40) | 1 × $7,500 | $7,500 |
| **Total spent** | | **$28,500** |
| **Kept** | | **$71,500** |

Sensitivity: if inspection finds nothing on M-1158, the plan loses $6,000. If the promotion lifts coin-in by only 5% (the Locals week rate), the expected theo is about +$22k, still above its cost. Wayfinding is the most uncertain action. If the manager prefers to act on comps, swap wayfinding for the comp pilot with a control group ($4,000), reverting the May 1 points price for half of the members.

## AI-use disclosure

An AI coding assistant (Cursor) helped write the DuckDB exploration scripts, the Databricks notebooks and Spark SQL, the dashboard definition, and drafts of this text. We re-ran every number in Databricks and checked each one against the queries named above.
