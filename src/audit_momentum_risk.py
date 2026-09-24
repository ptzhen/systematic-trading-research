"""Minute OHLC risk audit of saved one-tick momentum trades; no strategy changes."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['text.parse_math']=False


def main():
    root=Path('outputs/momentum_risk_audit'); root.mkdir(parents=True,exist_ok=True)
    t=pd.read_csv('outputs/intraday_candidates/trades.csv')
    t=t[(t.strategy=='momentum_opposite_band')&(t.slippage_ticks==1)].copy()
    t['entry_ts']=pd.to_datetime(t.entry_time,utc=True).dt.tz_convert('America/New_York')
    t['exit_ts']=pd.to_datetime(t.exit_time,utc=True).dt.tz_convert('America/New_York')
    t=t.sort_values('entry_ts').reset_index(drop=True)
    raw=pd.read_csv('Dataset_NQ_1min_2022_2025.csv',usecols=['timestamp ET','open','high','low','close'])
    stamp=pd.to_datetime(raw.pop('timestamp ET'),format='%m/%d/%Y %H:%M')
    keep=stamp.ge('2023-01-01')&stamp.lt('2025-01-01')
    raw=raw.loc[keep].copy(); raw.index=pd.DatetimeIndex(stamp.loc[keep].dt.tz_localize('America/New_York'))
    observations=[]; details=[]; realized=0.; peak_close=0.; peak_upper=0.; max_lower=0.; max_upper=0.
    def record(time,low,high,close,kind):
        nonlocal peak_close,peak_upper,max_lower,max_upper
        # Close-to-close equity drawdown is observable. High-before-low within a bar
        # is unknown; including same-bar high yields a conservative upper bound.
        peak_upper=max(peak_upper,high)
        upper=peak_upper-low
        lower=max(0.,peak_close-low)
        peak_close=max(peak_close,close)
        dd_close=peak_close-close
        max_lower=max(max_lower,lower,dd_close)
        max_upper=max(max_upper,upper)
        observations.append(dict(time=str(time),kind=kind,equity_close=close,
            equity_low=low,equity_high=high,drawdown_close=dd_close,drawdown_upper_bound=upper))
    for i,r in t.iterrows():
        path=raw.loc[(raw.index>=r.entry_ts)&(raw.index<r.exit_ts)]
        assert len(path)==int((r.exit_ts-r.entry_ts).total_seconds()/60)
        assert abs(r.entry-(path.open.iloc[0]+r.direction*.25))<1e-7
        base=realized
        # One-side entry fee $2.50; open equity excludes hypothetical closing costs.
        record(r.entry_ts,base-2.5,base-2.5,base-2.5,'entry_fill')
        worst_price=path.low.min() if r.direction==1 else path.high.max()
        best_price=path.high.max() if r.direction==1 else path.low.min()
        mae=max(0.,-r.direction*(worst_price-r.entry)*20)
        mfe=max(0.,r.direction*(best_price-r.entry)*20)
        for b in path.itertuples():
            adverse=b.low if r.direction==1 else b.high
            favorable=b.high if r.direction==1 else b.low
            lo=base-2.5+r.direction*(adverse-r.entry)*20
            hi=base-2.5+r.direction*(favorable-r.entry)*20
            close=base-2.5+r.direction*(b.close-r.entry)*20
            record(b.Index,lo,hi,close,'minute')
        realized+=r.net_dollars
        record(r.exit_ts,realized,realized,realized,'exit_fill')
        details.append(dict(trade_id=i+1,date=r.date,direction='long' if r.direction==1 else 'short',
            entry_time=r.entry_time,exit_time=r.exit_time,entry=r.entry,exit=r.exit,
            reason=r.reason,net_dollars=r.net_dollars,mae_dollars=mae,mfe_dollars=mfe,
            holding_minutes=len(path),intratrade_net_low=-mae-2.5))
    detail=pd.DataFrame(details); obs=pd.DataFrame(observations)
    detail.to_csv(root/'trade_excursions.csv',index=False)
    obs.to_csv(root/'minute_equity.csv',index=False)
    streak=longest=0
    for v in detail.net_dollars:
        streak=streak+1 if v<0 else 0; longest=max(longest,streak)
    # Longest interval without recovering a minute-close equity high, elapsed calendar time.
    timestamps=pd.to_datetime(obs.time,utc=True)
    underwater_start=None; longest_duration=pd.Timedelta(0); interval=None
    for j in range(len(obs)):
        if obs.drawdown_close.iloc[j]>1e-7:
            if underwater_start is None:
                underwater_start=timestamps.iloc[max(0,j-1)]
        elif underwater_start is not None:
            duration=timestamps.iloc[j]-underwater_start
            if duration>longest_duration:
                longest_duration=duration; interval=(str(underwater_start),str(timestamps.iloc[j]),'recovered')
            underwater_start=None
    if underwater_start is not None:
        duration=timestamps.iloc[-1]-underwater_start
        if duration>longest_duration:
            longest_duration=duration; interval=(str(underwater_start),str(timestamps.iloc[-1]),'ongoing_at_end')
    stats=dict(trades=len(t),net_dollars=float(realized),max_minute_close_drawdown=float(obs.drawdown_close.max()),
        intraminute_drawdown_lower_bound=float(max_lower),intraminute_drawdown_upper_bound=float(max_upper),
        worst_trade_net=float(detail.net_dollars.min()),largest_mae=float(detail.mae_dollars.max()),
        median_mae=float(detail.mae_dollars.median()),mae_95th_percentile=float(detail.mae_dollars.quantile(.95)),
        longest_losing_streak=longest,longest_underwater_calendar_days=longest_duration.total_seconds()/86400,
        underwater_interval=interval,best5_profit=float(detail.net_dollars.nlargest(5).sum()),
        net_without_best5=float(realized-detail.net_dollars.nlargest(5).sum()),
        net_without_best10=float(realized-detail.net_dollars.nlargest(10).sum()))
    assert abs(realized-t.net_dollars.sum())<1e-7
    assert max_upper+1e-7>=max_lower>=obs.drawdown_close.max()-1e-7
    assert (detail.mae_dollars>=0).all() and (detail.mfe_dollars>=0).all()
    (root/'metrics.json').write_text(json.dumps(stats,indent=2))
    groups=[]
    detail['quarter']=pd.to_datetime(detail.date).dt.to_period('Q').astype(str)
    detail['entry_hour']=pd.to_datetime(detail.entry_time,utc=True).dt.tz_convert('America/New_York').dt.strftime('%H:%M')
    for col in ['quarter','direction','entry_hour']:
        for label,g in detail.groupby(col):
            groups.append(dict(group=col,label=label,trades=len(g),win_rate=(g.net_dollars>0).mean(),
                net_dollars=g.net_dollars.sum(),avg_net_dollars=g.net_dollars.mean(),worst_trade=g.net_dollars.min()))
    pd.DataFrame(groups).to_csv(root/'breakdown.csv',index=False)
    detail.nsmallest(10,'net_dollars').to_csv(root/'worst_trades.csv',index=False)
    # Downsample for display only; retain full resolution audit in CSV.
    plot=obs.copy(); plot.index=pd.DatetimeIndex(timestamps)
    daily=plot.resample('D').agg(equity_close=('equity_close','last'),drawdown_close=('drawdown_close','max'),drawdown_upper_bound=('drawdown_upper_bound','max'))
    daily.equity_close=daily.equity_close.ffill()
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    axes[0].plot(daily.index,daily.equity_close/1000,color='#2563eb'); axes[0].set_ylabel('Net equity ($ thousands)')
    axes[1].plot(daily.index,-daily.drawdown_close/1000,label='Worst minute-close drawdown each day',color='#2563eb')
    axes[1].plot(daily.index,-daily.drawdown_upper_bound/1000,label='Intraminute conservative upper bound',color='#dc2626',alpha=.7)
    axes[1].set_ylabel('Drawdown ($ thousands)'); axes[1].legend()
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle('Momentum risk audit · one NQ · 2023–2024',fontsize=16)
    fig.text(.5,.02,'Open equity uses trade prices, not executable bid/ask. Entry fee charged immediately; exit fee at exit.\nOHLC does not reveal high/low order; red curve is a bound, not an exact tick drawdown. Excluded sessions remain excluded.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.07,1,.96)); fig.savefig(root/'risk_audit.png',dpi=150); plt.close(fig)
    report='# Momentum risk audit\n\n291 saved one-tick momentum trades; unchanged strategy, one NQ, 2023–2024 only.\n\n'
    for k,v in stats.items():
        report+=f'- {k}: {v}\n'
    report+='\n## Interpretation and limitations\n\nMinute-close equity includes realized P&L, mark-to-market P&L and entry-side commission. Final realized equity also includes exit-side commission and exit slippage. MAE/MFE use the entry fill and subsequent minute extremes, exclude commission, and do not imply executable fills at those extremes. Reversal exit bars are excluded from the old position and belong to the new one.\n\n'
    report+='The intraminute drawdown lies between the reported conservative bounds under the source OHLC path and mark-to-market assumptions. Exact high/low sequencing is unknown. Time underwater uses minute-close equity and calendar elapsed time, including nights/weekends, with flat equity between trades. No initial capital, margin, liquidation or prop-firm rules are simulated.\n\n'
    report+='The original dataset timestamp and rollover assumptions remain unverified; excluded incomplete sessions are not restored. Profit concentration and subgroup results are diagnostics, not new selection filters. No 2025 trades were evaluated.\n'
    (root/'REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps(stats,indent=2)); print(pd.DataFrame(groups).query("group == 'direction'").to_string(index=False))


if __name__=='__main__':
    main()
