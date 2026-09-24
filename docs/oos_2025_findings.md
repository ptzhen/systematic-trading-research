# Frozen 2025 out-of-sample test

Strategy rules and code hashes recorded in freeze.json before execution. End-label assumption retained. 2025 is now evaluated and must not be treated as untouched for subsequent changes.

234 eligible cash sessions. Incomplete sessions excluded ex post; indicators warmed using 2023–2024 without evaluating those trades again.

| Period | Ticks | Trades | Win rate | Net $ | PF | Closed-trade DD $ |
|---|---:|---:|---:|---:|---:|---:|
| combined | 1 | 160 | 35.0% | -705 | 1.00 | 30,295 |
| 2025Q1 | 1 | 42 | 38.1% | 1,370 | 1.03 | 12,400 |
| 2025Q2 | 1 | 39 | 33.3% | 5,160 | 1.10 | 22,175 |
| 2025Q3 | 1 | 43 | 32.6% | -13,070 | 0.59 | 13,290 |
| 2025Q4 | 1 | 36 | 36.1% | 5,835 | 1.14 | 15,890 |
| combined | 2 | 160 | 35.0% | -1,835 | 0.99 | 30,770 |
| 2025Q1 | 2 | 42 | 38.1% | 1,075 | 1.02 | 12,500 |
| 2025Q2 | 2 | 39 | 33.3% | 4,890 | 1.10 | 22,230 |
| 2025Q3 | 2 | 43 | 32.6% | -13,375 | 0.58 | 13,430 |
| 2025Q4 | 2 | 36 | 36.1% | 5,575 | 1.13 | 16,050 |

![OOS equity](equity.png)

## Prop replay: observed cash only, not lifetime EV

| Plan | Scenario | Observed mean net $ | Pass | Any payout | Censored |
|---|---|---:|---:|---:|---:|
| Topstep_50K_standard | base | -71.75 | 6.8% | 0.0% | 6.8% |
| Topstep_50K_standard | double_slippage | -71.75 | 6.8% | 0.0% | 6.8% |
| Topstep_50K_standard | fees_plus25 | -89.69 | 6.8% | 0.0% | 6.8% |
| Topstep_50K_standard | payout_delay5 | -71.75 | 6.8% | 0.0% | 6.8% |
| Tradeify_50K_Select_Flex | base | -165.00 | 0.0% | 0.0% | 6.8% |
| Tradeify_50K_Select_Flex | double_slippage | -165.00 | 0.0% | 0.0% | 6.8% |
| Tradeify_50K_Select_Flex | fees_plus25 | -206.25 | 0.0% | 0.0% | 6.8% |
| Tradeify_50K_Select_Flex | payout_delay5 | -165.00 | 0.0% | 0.0% | 6.8% |

Every eligible starting date is followed only to available data end or the existing horizon/three-payout limit. Late starts have less follow-up. Windows overlap and are not independent. Censored balances and later payouts are unvalued, so these means are not comparable lifetime EV estimates or forecasts.

Frozen simplified firm presets, 3 MNQ using NQ prices as proxy. Costs and payout assumptions unchanged. Extra-slippage prop stress adds costs to saved fills. No rolling purchases, budget depletion, portfolio correlation, taxes or actual execution validation. Timestamp semantics and roll construction remain unresolved.

Validation: simulator synthetic checks and replay reconciliation passed; no earlier stop missed; every entry reconciles to the assumed next-bar open plus slippage. Positive OOS results alone do not establish business readiness.
