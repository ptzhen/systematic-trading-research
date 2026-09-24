"""Replay stopped momentum through frozen prop-plan scenarios; 2023/24 only."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from stress_prop_firms import main as stress_main


def build_tape(bar_label='start', strategy_dir='outputs/stopped_strategies', out_dir='outputs/stopped_prop', sessions_path='outputs/intraday_candidates/sessions.csv', evaluation_start='2023-01-01', evaluation_end='2025-01-01'):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    trades=pd.read_csv(Path(strategy_dir)/'trades.csv')
    trades=trades[(trades.strategy=='momentum_stop') & (trades.ticks==1)].copy()
    assert trades.date.ge(evaluation_start).all() and trades.date.lt(evaluation_end).all()
    for col in ['entry_time','exit_time']:
        trades[col]=pd.to_datetime(trades[col],utc=True).dt.tz_convert('America/New_York')
    trades=trades.sort_values('entry_time')
    raw=pd.read_csv('Dataset_NQ_1min_2022_2025.csv',usecols=['timestamp ET','open','high','low','close'])
    stamp=pd.to_datetime(raw.pop('timestamp ET'),format='%m/%d/%Y %H:%M')
    if bar_label=='end': stamp=stamp-pd.Timedelta(minutes=1)
    keep=stamp.ge(evaluation_start) & stamp.lt(evaluation_end)
    raw=raw.loc[keep].copy(); raw.index=pd.DatetimeIndex(stamp.loc[keep].dt.tz_localize('America/New_York'))
    events=[]; realized=0.
    for r in trades.itertuples():
        base=realized
        events.append((r.entry_time,'entry_fill',base-2.5,base-2.5))
        # Exit-minute extremes after a stop would create fictitious open risk.
        # Earlier complete bars plus the actual stop/gap fill bound adverse equity.
        path=raw.loc[(raw.index>=r.entry_time)&(raw.index<r.exit_time)]
        assert len(path)==int((r.exit_time-r.entry_time).total_seconds()/60)
        assert np.isclose(r.entry,raw.loc[r.entry_time,'open']+r.direction*.25)
        for b in path.itertuples():
            adverse=b.low if r.direction==1 else b.high
            assert r.direction*(adverse-r.stop)>0, 'Missed stop before recorded exit'
            low=base-2.5+r.direction*(adverse-r.entry)*20
            close=base-2.5+r.direction*(b.close-r.entry)*20
            events.append((b.Index,'minute',low,close))
        realized+=r.net_dollars
        events.append((r.exit_time,'exit_fill',realized,realized))
    assert np.isclose(realized,trades.net_dollars.sum())
    a=pd.DataFrame(events,columns=['time','kind','equity_low','equity_close'])
    assert a.time.is_monotonic_increasing
    a.to_csv(out/'minute_equity.csv',index=False)
    a['date']=a.time.dt.strftime('%Y-%m-%d')
    sessions=pd.read_csv(sessions_path)
    dates=pd.to_datetime(sessions.loc[sessions.eligible,'date']).tolist()
    groups={k:g for k,g in a.groupby('date',sort=False)}
    daily=[]; previous=0.
    for date in dates:
        g=groups.get(str(date.date()))
        if g is None:
            daily.append((np.zeros(1),0.,np.zeros(1),False));continue
        counts=g.kind.isin(['entry_fill','exit_fill']).cumsum().to_numpy()
        daily.append((g.equity_low.to_numpy()-previous,float(g.equity_close.iloc[-1])-previous,counts,True))
        previous=float(g.equity_close.iloc[-1])
    assert np.isclose(sum(d[1] for d in daily),realized)
    assert sum(d[2][-1] for d in daily)==2*len(trades)
    (out/'replay_checks.json').write_text(json.dumps(dict(trades=len(trades),net_dollars=realized,
        eligible_sessions=len(dates),fill_count=int(sum(d[2][-1] for d in daily)),
        checks=f'P&L reconciles; no missed earlier stops; entry fills reconcile; ordered events; scope {evaluation_start} to {evaluation_end}.',
        stress='Extra slippage is charged on fixed saved fills; stress does not recalculate strategy stop placement.',
        exit_minutes='Stop fill replaces exit-minute extremes; exact within-minute stop time is unavailable.'),indent=2))
    print('Reconciled stopped momentum tape:',len(trades),'trades, $',realized,flush=True)
    return dates,daily


if __name__=='__main__':
    stress_main(build_tape(),'outputs/stopped_prop','Momentum with 2x M5 ATR14 stop')
