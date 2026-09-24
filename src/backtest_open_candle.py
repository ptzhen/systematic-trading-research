"""M5 candle-color strategy, evaluated on M1 OHLC. 2025 is excluded.

Default signal: 09:30-09:35 New York candle; enter at 09:35.
Source timestamps default to starts; confirm this with the data vendor.
Costs are explicit illustrative inputs, not broker quotes. Results use one NQ.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd


def resolve_bar(o, h, l, direction, stop, target):
    """Return price/reason/ambiguity. Stops gap at open; limits fill at limit."""
    if direction * (o - stop) <= 0:
        return o, "stop_gap", False
    if direction * (o - target) >= 0:
        return target, "target", False
    stopped = l <= stop if direction == 1 else h >= stop
    won = h >= target if direction == 1 else l <= target
    if stopped:
        return stop, "stop", bool(won)
    if won:
        return target, "target", False
    return None


def summarize(frame):
    r = frame.net_r
    equity = np.r_[0, r.cumsum().to_numpy()]
    losses = -r[r < 0].sum()
    return dict(trades=len(frame), win_rate=float((r > 0).mean()),
                gross_r=float(frame.gross_r.sum()), net_r=float(r.sum()),
                expectancy_net_r=float(r.mean()),
                profit_factor_r=float(r[r > 0].sum() / losses) if losses else None,
                max_drawdown_r=float((np.maximum.accumulate(equity) - equity).max()),
                ambiguous_bars=int(frame.ambiguous.sum()),
                net_dollars_one_nq=float(frame.net_dollars.sum()))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--signal-start", choices=["09:30", "09:35"], default="09:30",
                   help="New York signal candle start; default 09:30, entry 09:35")
    p.add_argument("--exit-policy", choices=["16:00", "hold"], default="16:00",
                   help="Default: close remaining trades at 16:00 New York time")
    p.add_argument("--bar-label", choices=["start", "end"], default="start")
    p.add_argument("--commission", type=float, default=5.0, help="USD round trip per NQ, illustrative")
    p.add_argument("--slippage-ticks", type=int, default=1, help="Adverse ticks on market/stop fills; target has none")
    p.add_argument("--target-r", type=float, default=.5, help="Reward / initial risk; default 0.5")
    p.add_argument("--variant", choices=["baseline", "rvol", "body", "breakout"], default="baseline")
    p.add_argument("--warmup", type=int, default=0, help="Prior complete sessions required; use 20 for matched experiments")
    p.add_argument("--input", type=Path, default=Path("Dataset_NQ_1min_2022_2025.csv"))
    p.add_argument("--output", type=Path, default=Path("outputs/open_candle_backtest"))
    args = p.parse_args()
    if args.commission < 0 or args.slippage_ticks < 0:
        p.error("Costs cannot be negative")
    if not math.isfinite(args.target_r) or args.target_r <= 0:
        p.error("--target-r must be finite and positive")
    data = pd.read_csv(args.input, usecols=["timestamp ET", "open", "high", "low", "close", "volume"])
    ts = pd.to_datetime(data.pop("timestamp ET"), format="%m/%d/%Y %H:%M")
    # Filter before any strategy evaluation. Do not score 2025.
    keep = ts.ge("2023-01-01") & ts.lt("2025-01-01")
    data = data.loc[keep].copy()
    ts = ts.loc[keep].dt.tz_localize("America/New_York", ambiguous="raise", nonexistent="raise")
    if args.bar_label == "end":
        ts -= pd.Timedelta(minutes=1)
    data.index = pd.DatetimeIndex(ts)
    data.sort_index(inplace=True)
    if data.index.has_duplicates or not np.isfinite(data.to_numpy()).all():
        raise ValueError("Duplicate timestamps or invalid OHLC")
    if ((data.high < data[["open", "close", "low"]].max(axis=1)) |
        (data.low > data[["open", "close"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC ordering")
    trades, skipped = [], []
    busy_until = None
    hour, minute = map(int, args.signal_start.split(":"))
    slip = args.slippage_ticks * .25
    history_volume, history_range = [], []
    for day, daily in data.groupby(data.index.date):
        if pd.Timestamp(day).dayofweek >= 5:
            continue
        start = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=hour, minutes=minute)
        entry_time = start + pd.Timedelta(minutes=5)
        if busy_until is not None and entry_time <= busy_until:
            skipped.append(dict(date=str(day), reason="previous_trade_open"))
            continue
        signal = daily.reindex(pd.date_range(start, periods=5, freq="min"))
        if signal.isna().any().any() or entry_time not in daily.index:
            skipped.append(dict(date=str(day), reason="missing_signal_or_entry"))
            continue
        opening_range = float(signal.high.max() - signal.low.min())
        opening_volume = float(signal.volume.sum())
        prior_sessions = len(history_volume)
        rvol = opening_volume / np.mean(history_volume[-14:]) if prior_sessions >= 14 and np.mean(history_volume[-14:]) > 0 else np.nan
        range_ratio = opening_range / np.median(history_range[-20:]) if prior_sessions >= 20 and np.median(history_range[-20:]) > 0 else np.nan
        body_fraction = abs(float(signal.close.iloc[-1] - signal.open.iloc[0])) / opening_range if opening_range else 0
        history_volume.append(opening_volume)
        history_range.append(opening_range)
        if prior_sessions < args.warmup:
            skipped.append(dict(date=str(day), reason="warmup"))
            continue
        if args.variant == "rvol" and not rvol > 1:
            skipped.append(dict(date=str(day), reason="rvol_filter_or_warmup"))
            continue
        if args.variant == "body" and body_fraction < .5:
            skipped.append(dict(date=str(day), reason="body_filter"))
            continue
        direction = int(np.sign(signal.close.iloc[-1] - signal.open.iloc[0]))
        if not direction:
            skipped.append(dict(date=str(day), reason="doji"))
            continue
        entry = float(daily.loc[entry_time, "open"]) + direction * slip
        stop = float(signal.low.min() if direction == 1 else signal.high.max())
        cutoff = start.normalize() + pd.Timedelta(hours=16)
        intrabar_entry = False
        if args.variant == "breakout":
            # A strict break: one tick beyond the opening extreme. Order expires at 16:00.
            trigger = float(signal.high.max() + .25 if direction == 1 else signal.low.min() - .25)
            expected_trigger_time = entry_time
            found = False
            for t, bar in daily.loc[(daily.index >= entry_time) & (daily.index < cutoff)].iterrows():
                if t != expected_trigger_time:
                    break
                expected_trigger_time = t + pd.Timedelta(minutes=1)
                if (bar.high >= trigger if direction == 1 else bar.low <= trigger):
                    at_open = direction * (bar.open - trigger) >= 0
                    entry = float(bar.open if at_open else trigger) + direction * slip
                    intrabar_entry = not at_open
                    entry_time = t
                    found = True
                    break
            if not found:
                skipped.append(dict(date=str(day), reason="no_breakout_or_missing_pre_entry_data"))
                continue
        risk = direction * (entry - stop)
        if risk <= 0:
            skipped.append(dict(date=str(day), reason="invalid_risk"))
            continue
        # Round target distance down to a tradable tick, conservatively <= requested R.
        reward = math.floor((risk * args.target_r + 1e-9) / .25) * .25
        if reward <= 0:
            skipped.append(dict(date=str(day), reason="target_below_tick"))
            continue
        target = entry + direction * reward
        cutoff = start.normalize() + pd.Timedelta(hours=16)
        path = daily.loc[(daily.index >= entry_time) & (daily.index < cutoff)] if args.exit_policy == "16:00" else data.loc[data.index >= entry_time]
        expected = entry_time
        outcome = None
        for t, bar in path.iterrows():
            # Missing minutes can conceal a stop/target hit. Do not invent an outcome.
            if t != expected:
                break
            expected = t + pd.Timedelta(minutes=1)
            # On an intrabar stop-entry, the earlier bar open cannot be an exit fill.
            # If the entry bar also touches the stop, conservatively assume it happens after entry.
            effective_open = entry if t == entry_time and intrabar_entry else bar.open
            result = resolve_bar(effective_open, bar.high, bar.low, direction, stop, target)
            if result:
                price, reason, ambiguous = result
                ambiguous = ambiguous or (t == entry_time and intrabar_entry and reason.startswith("stop"))
                if reason != "target":
                    price -= direction * slip
                outcome = (t, price, reason, ambiguous)
                break
            if args.exit_policy == "16:00" and expected == cutoff:
                outcome = (cutoff, float(bar.close) - direction * slip, "time_exit", False)
        if outcome is None:
            skipped.append(dict(date=str(day), reason="unresolved_missing_minutes_or_end"))
            if args.exit_policy == "hold":
                raise ValueError("Unresolved held trade across a data gap/end; cannot safely simulate later entries")
            continue
        exit_time, price, reason, ambiguous = outcome
        busy_until = exit_time
        points = direction * (price - entry)
        net_dollars = points * 20 - args.commission
        trades.append(dict(date=str(day), entry_time=str(entry_time), exit_bar_time=str(exit_time),
                           direction="long" if direction == 1 else "short", entry=entry, stop=stop,
                           target=target, initial_risk_points=risk, exit=price, reason=reason,
                           ambiguous=ambiguous, gross_r=points/risk,
                           rvol=rvol, body_fraction=body_fraction, range_ratio=range_ratio,
                           net_r=net_dollars/(risk*20), net_dollars=net_dollars))
    if not trades:
        raise ValueError("No resolved trades")
    frame = pd.DataFrame(trades)
    frame["year"] = pd.to_datetime(frame.date).dt.year
    frame["quarter"] = pd.to_datetime(frame.date).dt.to_period("Q").astype(str)
    stats = []
    for key in ["year", "quarter"]:
        for period, subset in frame.groupby(key, sort=True):
            stats.append(dict(period=str(period), **summarize(subset)))
    args.output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output / "trades.csv", index=False)
    pd.DataFrame(skipped, columns=["date", "reason"]).to_csv(args.output / "skipped.csv", index=False)
    pd.DataFrame(stats).to_csv(args.output / "summary.csv", index=False)
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    config.update(evaluated_years=[2023, 2024], target_r=args.target_r, tick_size=.25, point_value=20,
                  same_minute_policy="stop_first", missing_minutes="unresolved_excluded_and_logged",
                  target_fill="touch_at_limit", gross_r="includes_slippage_excludes_commission")
    config.update(breakout_trigger="one tick beyond signal extreme; expires 16:00",
                  breakout_entry_bar="stop touch assumed after entry and flagged ambiguous",
                  feature_history="previous complete signal+entry sessions only; excludes current day",
                  rvol_threshold=1, body_threshold=.5, timestamp_status="unverified")
    (args.output / "assumptions.json").write_text(json.dumps(config, indent=2))
    print(pd.DataFrame(stats).to_string(index=False))
    print("Skipped:", pd.Series([x["reason"] for x in skipped]).value_counts().to_dict())
    print("2025 was not evaluated.")


if __name__ == "__main__":
    main()
