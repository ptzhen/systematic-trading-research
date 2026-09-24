# Topstep / Tradeify scenario study

Rule snapshot: 2026-09-17. Nine rule-inspired plans: Topstep Standard and No Activation pricing with XFA Standard payout, plus Tradeify Select Flex, each 50/100/150K. No DLL add-ons. Not exact firm replication or a purchasing recommendation.

Each run buys one evaluation and, if passed, activates one funded account. No resets, rebuy cycles or multiple simultaneous accounts. Stop after 120 evaluation sessions, 120 funded sessions or three payouts. Horizons are analyst limits, NOT firm deadlines; residual balances and future payouts are unvalued. Three-payout censoring avoids extrapolating uncertain live transitions.

477 eligible sessions from the selected 2023/24 momentum backtest. 238 overlapping historical starts and 500 ten-session block-bootstrap paths (250 each seeds 42 and 123). These are correlated resamples of a small selected history, NOT independent evidence or out-of-sample forecasts. 2025 remains untested.

EOD trailing floors are checked against minute equity lows throughout each session; floor locks at $0 for Topstep and +$100 for Tradeify, including after first payout. Evaluation targets 3000/6000/9000, drawdown 2000/3000/4500. Consistency 55% Topstep, 40% Tradeify. Five qualifying profit days per payout, positive cycle profit after first payout. Withdraw up to half balance subject to size cap; 90% receipt. Tradeify qualifying days 150/200/250; Topstep 150. Request at first eligibility, skip next calendar day as conservative processing treatment. Topstep $30 withdrawal fee modeled; Tradeify $0 assumed. Calendar monthly Topstep billing; synthetic bootstrap uses a weekday calendar without holidays. Current rules applied counterfactually to older returns, not historical account performance.

NQ price paths proxy MNQ execution; this is NOT observed MNQ data. Costs replace original $5 round trip with $5.76/NQ or $1.82/MNQ. These are Tradeify published rates applied as a common conservative modeling assumption also to Topstep, not verified Topstep commissions. Slippage starts at one tick each side; separate stress doubles it. Other standalone stresses add 25% to evaluation/activation fees or pause five calendar days after payouts. No combined stress, taxes, FX, payment rejection, slippage jumps at breach, inactivity rules or discretionary risk interventions. Sizes stay at/below one mini equivalent.

The underlying dataset has unresolved timestamp/rollover conventions; excluded sessions remain excluded. No assumption that payout qualification guarantees receipt: model assumes payment succeeds. Funded EV columns are conditional on passing within the horizon and include three-payout truncation. Censored outcomes must not be treated as terminal failures. No unsupported claim of lifetime EV.

Sources and numerical presets are in sources.json and plans.json. Full baseline attempts are saved per plan/size; summary.csv includes all stress results. Fees and rules can change; verify checkout before use.

## Highest historical cash EV scenarios (selection-biased; not recommendations)

| Plan | Position | Pass | Payout | Cash EV | Median cash |
|---|---|---:|---:|---:|---:|
| Topstep_50K_standard | 3 MNQ | 43.7% | 16.8% | $-44.66 | $-49.00 |
| Tradeify_50K_Select_Flex | 3 MNQ | 37.8% | 16.4% | $-46.70 | $-165.00 |
| Topstep_50K_no_activation | 3 MNQ | 43.7% | 16.8% | $-51.25 | $-95.00 |
| Topstep_50K_standard | 10 MNQ | 14.7% | 0.8% | $-56.66 | $-49.00 |
| Topstep_50K_standard | 1 NQ | 15.5% | 0.8% | $-57.91 | $-49.00 |
| Topstep_50K_standard | 5 MNQ | 17.2% | 0.8% | $-68.45 | $-49.00 |
| Topstep_50K_no_activation | 10 MNQ | 14.7% | 0.8% | $-81.32 | $-95.00 |
| Topstep_50K_no_activation | 1 NQ | 15.5% | 0.8% | $-81.32 | $-95.00 |
| Topstep_50K_no_activation | 5 MNQ | 17.2% | 0.8% | $-92.65 | $-95.00 |
| Topstep_100K_standard | 10 MNQ | 16.0% | 0.8% | $-108.94 | $-99.00 |
| Topstep_100K_standard | 1 NQ | 17.6% | 0.8% | $-110.56 | $-99.00 |
| Tradeify_50K_Select_Flex | 2 MNQ | 31.5% | 10.9% | $-114.73 | $-165.00 |

## Method disagreement
All base historical-window cash EVs were negative, while many bootstrap EVs were positive. Historical starts need 240 future eligible sessions, concentrating starts early in the sample. Bootstrap draws from the entire sample, including later profitable periods, and disrupts longer regimes. These methods are not directly interchangeable. Do not average them into a forecast or pick the best seed.
