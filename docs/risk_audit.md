# Momentum risk audit

291 saved one-tick momentum trades; unchanged strategy, one NQ, 2023–2024 only.

- trades: 291
- net_dollars: 84720.0
- max_minute_close_drawdown: 16785.0
- intraminute_drawdown_lower_bound: 17310.0
- intraminute_drawdown_upper_bound: 17365.0
- worst_trade_net: -6870.0
- largest_mae: 7290.0
- median_mae: 1090.0
- mae_95th_percentile: 4462.5
- longest_losing_streak: 6
- longest_underwater_calendar_days: 105.93680555555555
- underwater_interval: ('2023-11-20 20:15:00+00:00', '2024-03-05 18:44:00+00:00', 'recovered')
- best5_profit: 37485.0
- net_without_best5: 47235.0
- net_without_best10: 22425.0

## Interpretation and limitations

Minute-close equity includes realized P&L, mark-to-market P&L and entry-side commission. Final realized equity also includes exit-side commission and exit slippage. MAE/MFE use the entry fill and subsequent minute extremes, exclude commission, and do not imply executable fills at those extremes. Reversal exit bars are excluded from the old position and belong to the new one.

The intraminute drawdown lies between the reported conservative bounds under the source OHLC path and mark-to-market assumptions. Exact high/low sequencing is unknown. Time underwater uses minute-close equity and calendar elapsed time, including nights/weekends, with flat equity between trades. No initial capital, margin, liquidation or prop-firm rules are simulated.

The original dataset timestamp and rollover assumptions remain unverified; excluded incomplete sessions are not restored. Profit concentration and subgroup results are diagnostics, not new selection filters. No 2025 trades were evaluated.
