# Momentum candidate freeze v1

Candidate frozen; data-convention verification pending; OOS NOT run

The selected strategy is stopped momentum, not the failed pullback candidate. The snapshot preserves the existing research code and frozen prop presets; it is not yet an OOS runner.

## Timestamp clues: development data only

| Source label | Rows | Median volume | Mean volume |
|---|---:|---:|---:|
| 09:29 | 516 | 672 | 756 |
| 09:30 | 516 | 894 | 984 |
| 09:31 | 516 | 5114 | 5160 |
| 09:32 | 516 | 3939 | 4033 |
| 16:59 | 496 | 84 | 102 |
| 17:00 | 495 | 144 | 164 |
| 17:01 | 0 | 0 | 0 |
| 17:59 | 0 | 0 | 0 |
| 18:00 | 0 | 0 | 0 |
| 18:01 | 515 | 329 | 429 |
| 18:02 | 515 | 158 | 217 |

Restarts after gaps of at least 50 minutes: {'18:01': 514, '20:01': 1, '18:04': 1}

These patterns cannot prove bar-label convention. Required external evidence: vendor/platform and export settings, what a 09:31 row represents, timezone/DST treatment, and individual-contract versus adjusted continuous futures construction.

## Frozen validation protocol

1. Confirm source timestamp convention, timezone, and continuous-contract roll construction before OOS execution.
2. If timestamp interpretation requires correction, rerun development with the correction and preserve this superseded freeze.
3. Use late-2024 history to warm up the 14-session bands, M5 ATR and prior close. No 2025 information may enter an earlier signal.
4. Keep the 2xATR stop, half-hour signals, neutral/opposite reentry reset, one position, and 16:00 exit unchanged. No target.
5. Report 2025 strategy returns once at fixed 1 NQ with base and doubled slippage, plus quarter diagnostics without retuning.
6. For prop replay prioritize the frozen 3 MNQ pair. Predeclare chronological starts and report actual available follow-up; do not fabricate 240 future sessions or wrap the holdout.
7. Report net cash, fees, payouts, pass times, breaches and censored/open accounts separately. Do not report censored accounts as failures or realized lifetime EV.
8. Keep full-year strategy evidence separate from incomplete account-lifecycle evidence. Any changes after viewing 2025 retire it as an untouched holdout.

Primary prop size: 3 MNQ for Topstep 50K Standard and Tradeify 50K Select Flex, retaining the earlier comparator rather than selecting the highest EV grid result. NQ data remains a proxy for MNQ execution.

No 2025 strategy results were computed. Code snapshots and SHA-256 digests are stored with manifest.json.
