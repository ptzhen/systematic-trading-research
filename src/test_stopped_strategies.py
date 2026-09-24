"""Two predeclared stopped strategy experiments; no 2025 and no optimization."""
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
from backtest_open_candle import resolve_bar

RULES={
 'momentum_stop':'Original half-hour noise-band entries/reversals; fixed stop 2 x ATR14 of completed M5 bars at entry, rounded outward to tick; no target. After stop, require a neutral/opposite half-hour signal before same-direction reentry. Flat 16:00.',
 'pullback':'M15 EMA20>EMA50 and EMA20 rising over 4 bars = long; mirror for short. M5 previous candle touches EMA20 from trend side and is countertrend; next candle bullish and closes above previous high (mirror shorts). Entry next minute, stop beyond both setup extremes by one tick, target 1.5R, 60-minute timeout. Entries 10:00-15:00. Fresh two-bar setup after exit.',
 'indicators':'Full available complete bars including overnight; EMA adjust=False with minimum periods; ATR14 simple average of true ranges. Bar index denotes closing time for indicators.',
 'costs':'$5 round trip per NQ, 1 and 2 adverse ticks per market/stop fill. Limits touch-fill without slippage.',
 'scope':'2023/2024; prior 14 complete cash sessions warmup; same 477 dates as existing comparison. No sizing optimization, no daily lockout. One NQ per trade; R normalizes initial price risk.',
 'limitations':'Source timestamps assumed starts, unverified. Incomplete cash sessions excluded ex post. Unknown rollover adjustments. Missing overnight bars skipped in indicators. Not a prop account simulation.'}


def aggregate(d,n):
    b=d.resample(f'{n}min',label='right',closed='left').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),count=('close','count'))
    return b[b['count'].eq(n)].copy()


def indicators(d):
    m5=aggregate(d,5); m15=aggregate(d,15)
    m5['ema']=m5.close.ewm(span=20,adjust=False,min_periods=20).mean()
    prev=m5.close.shift()
    m5['atr']=pd.concat([m5.high-m5.low,(m5.high-prev).abs(),(m5.low-prev).abs()],axis=1).max(axis=1).rolling(14).mean()
    fast=m15.close.ewm(span=20,adjust=False,min_periods=20).mean()
    slow=m15.close.ewm(span=50,adjust=False,min_periods=50).mean()
    m15['regime']=np.select([(fast>slow)&(fast>fast.shift(4)),(fast<slow)&(fast<fast.shift(4))],[1,-1],default=0)
    return m5,m15


def run(day,d,m5,m15,upper,lower,strategy,ticks):
    rows=[]; position=None; blocked=0; last_exit=None
    def finish(t,price,reason,ambiguous=False):
        nonlocal position,last_exit
        s=position; net=s['direction']*(price-s['entry'])*20-5
        rows.append(dict(date=str(day),strategy=strategy,ticks=ticks,entry_time=str(s['time']),exit_time=str(t),
            direction=s['direction'],entry=s['entry'],stop=s['stop'],risk_points=s['risk'],exit=price,
            reason=reason,net_dollars=net,net_r=net/(s['risk']*20),ambiguous=ambiguous,
            duration_minutes=(t-s['time']).total_seconds()/60))
        position=None;last_exit=t
    for k,b in enumerate(d.itertuples()):
        t=b.Index; direction=0; signal_stop=None
        if strategy=='momentum_stop' and k>=30 and k%30==0:
            close=d.close.iloc[k-1]
            sig=1 if close>upper[k-1] else -1 if close<lower[k-1] else 0
            if sig!=blocked: blocked=0
            if position and sig==-position['direction']:
                finish(t,b.open-position['direction']*ticks*.25,'reverse')
            if position is None and sig and sig!=blocked and t in m5.index:
                atr=m5.loc[t,'atr']
                if np.isfinite(atr) and atr>0:
                    direction=sig; signal_stop=math.ceil(2*atr*4)/4
        elif strategy=='pullback' and position is None and t in m5.index and 600<=t.hour*60+t.minute<=900:
            previous_time=t-pd.Timedelta(minutes=5)
            if previous_time in m5.index and (last_exit is None or t-pd.Timedelta(minutes=10)>last_exit):
                j=m15.index.searchsorted(t,side='right')-1
                regime=int(m15.iloc[j].regime) if j>=0 else 0
                a,c=m5.loc[previous_time],m5.loc[t]
                if regime==1 and a.open>a.ema and a.low<=a.ema and a.close<a.open and c.close>c.open and c.close>a.high:
                    direction=1;signal_stop=min(a.low,c.low)-.25
                if regime==-1 and a.open<a.ema and a.high>=a.ema and a.close>a.open and c.close<c.open and c.close<a.low:
                    direction=-1;signal_stop=max(a.high,c.high)+.25
        if direction and position is None:
            entry=b.open+direction*ticks*.25
            stop=entry-direction*signal_stop if strategy=='momentum_stop' else signal_stop
            risk=direction*(entry-stop)
            if risk>0:
                target=entry+direction*math.floor(1.5*risk*4)/4 if strategy=='pullback' else direction*np.inf
                position=dict(time=t,entry=entry,stop=stop,risk=risk,direction=direction,target=target)
        if position:
            s=position
            result=resolve_bar(b.open,b.high,b.low,s['direction'],s['stop'],s['target'])
            if result:
                price,reason,ambiguous=result
                if reason!='target': price-=s['direction']*ticks*.25
                old_direction=s['direction'];finish(t,price,reason,ambiguous)
                if strategy=='momentum_stop': blocked=old_direction
            elif k==389 or (strategy=='pullback' and t+pd.Timedelta(minutes=1)>=s['time']+pd.Timedelta(minutes=60)):
                finish(t+pd.Timedelta(minutes=1),b.close-s['direction']*ticks*.25,'time_exit')
    return rows


def main(bar_label='start', out_dir='outputs/stopped_strategies', evaluation_start='2023-01-01', evaluation_end='2025-01-01', strategies=('momentum_stop','pullback')):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    rules=dict(RULES, bar_label_assumption=bar_label)
    rules['scope']=f'{evaluation_start} to {evaluation_end} exclusive; prior data for warmup only; 14 complete cash sessions; one NQ.'
    rules['limitations']=f'Source timestamps assumed {bar_label}s, unverified. Incomplete cash sessions excluded ex post; unknown rollover adjustments.'
    (out/'rules.json').write_text(json.dumps(rules,indent=2))
    raw=pd.read_csv('Dataset_NQ_1min_2022_2025.csv',usecols=['timestamp ET','open','high','low','close'])
    t=pd.to_datetime(raw.pop('timestamp ET'),format='%m/%d/%Y %H:%M')
    if bar_label=='end': t=t-pd.Timedelta(minutes=1)
    keep=t.ge('2023-01-01')&t.lt(evaluation_end)
    raw=raw.loc[keep].copy();raw.index=pd.DatetimeIndex(t.loc[keep].dt.tz_localize('America/New_York'));raw.sort_index(inplace=True)
    assert not raw.index.has_duplicates and np.isfinite(raw.to_numpy()).all()
    m5,m15=indicators(raw)
    allowed=set();session_rows=[]
    history=[];previous_close=None;rows=[]
    for day,group in raw.groupby(raw.index.date):
        if pd.Timestamp(day).dayofweek>=5:continue
        start=pd.Timestamp(day).tz_localize('America/New_York')+pd.Timedelta(hours=9,minutes=30)
        d=group.reindex(pd.date_range(start,periods=390,freq='min'))
        complete=not d.isna().any().any()
        in_scope=evaluation_start<=str(day)<evaluation_end
        eligible=complete and len(history)>=14 and in_scope
        if in_scope: session_rows.append(dict(date=str(day),complete=complete,eligible=eligible))
        if not complete:continue
        if eligible:
            allowed.add(str(day))
            sigma=np.mean(history[-14:],axis=0)
            upper=max(d.open.iloc[0],previous_close)*(1+sigma);lower=min(d.open.iloc[0],previous_close)*(1-sigma)
            for ticks in [1,2]:
                for strategy in strategies:
                    rows.extend(run(day,d,m5,m15,upper,lower,strategy,ticks))
        history.append(np.abs(d.close.to_numpy()/d.open.iloc[0]-1));previous_close=d.close.iloc[-1]
    pd.DataFrame(session_rows).to_csv(out/'sessions.csv',index=False)
    trades=pd.DataFrame(rows);trades['year']=pd.to_datetime(trades.date).dt.year
    trades['quarter']=pd.to_datetime(trades.date).dt.to_period('Q').astype(str)
    trades.to_csv(out/'trades.csv',index=False)
    stats=[]
    for (strategy,ticks),g in trades.groupby(['strategy','ticks']):
        for period,f in [('combined',g),*list(g.groupby('year')),*list(g.groupby('quarter'))]:
            days=sum(str(period)=='combined' or date.startswith(str(period)) for date in allowed) if 'Q' not in str(period) else sum(str(pd.Period(date,freq='Q'))==str(period) for date in allowed)
            pnl=f.net_dollars;eq=np.r_[0,pnl.cumsum()];loss=-pnl[pnl<0].sum()
            stats.append(dict(strategy=strategy,ticks=ticks,period=str(period),trades=len(f),trades_per_day=len(f)/days,
                win_rate=(pnl>0).mean(),net_dollars=pnl.sum(),net_r=f.net_r.sum(),avg_r=f.net_r.mean(),
                profit_factor=pnl[pnl>0].sum()/loss if loss else np.nan,drawdown_dollars=(np.maximum.accumulate(eq)-eq).max(),
                avg_duration_minutes=f.duration_minutes.mean(),worst_trade=pnl.min()))
    summary=pd.DataFrame(stats);summary.to_csv(out/'summary.csv',index=False)
    report=f'# Fixed protective-stop strategy tests\n\nTimestamp assumption: {bar_label}. Evaluation {evaluation_start} to {evaluation_end} exclusive. No optimization. {len(allowed)} eligible cash sessions.\n\n'
    annual=summary[~summary.period.str.contains('Q')]
    report+='| Strategy | Ticks | Period | Trades | Trades/day | Win rate | Net $ | Net R | PF |\n|---|---:|---|---:|---:|---:|---:|---:|---:|\n'
    for r in annual.itertuples():report+=f'| {r.strategy} | {r.ticks} | {r.period} | {r.trades} | {r.trades_per_day:.2f} | {r.win_rate:.1%} | {r.net_dollars:.0f} | {r.net_r:.2f} | {r.profit_factor:.2f} |\n'
    report+='\nOne NQ, $5 round-trip fees. Dollar results are not fixed-dollar-risk sizing. Stop gap fills can exceed initial risk. Intrabar ambiguous stop/target touches are stop-first. Drawdown uses closed trades. Trades within their exit minute cannot be timed more precisely. See rules.json for timestamp, coverage, and rollover limitations. No prop pass/payout estimate is claimed from these trade totals.\n'
    (out/'REPORT.md').write_text(report,encoding='utf-8');print(annual.to_string(index=False))


if __name__=='__main__':main()
