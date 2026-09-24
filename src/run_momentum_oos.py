"""
Run the frozen 2025 out-of-sample evaluation.

The strategy specification is kept unchanged from the development period.
This script evaluates the frozen strategy on previously unseen 2025 data,
produces strategy diagnostics, and replays selected risk-constraint scenarios.

Important:
- 2025 is treated as a one-time holdout.
- No strategy parameters are optimised using 2025 results.
- Historical performance is not evidence of future profitability.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from test_stopped_strategies import main as strategy_main
from simulate_stopped_prop import build_tape
from stress_prop_firms import plans, scale_tape, simulate, checks

out=Path('outputs/momentum_oos_2025')
out.mkdir(parents=True,exist_ok=True)
if (out/'freeze.json').exists():
    raise FileExistsError('OOS already initiated. Preserve its results; do not silently rerun.')
files=['test_stopped_strategies.py','backtest_open_candle.py','simulate_stopped_prop.py','stress_prop_firms.py','run_momentum_oos.py']
hashes={}
for name in files:
    data=Path(name).read_bytes(); hashes[name]=hashlib.sha256(data).hexdigest()
    dest=out/'snapshot'/name;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(data)
selected=[p for p in plans() if p['name'] in ['Topstep_50K_standard','Tradeify_50K_Select_Flex']]
(out/'freeze.json').write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),
    sha256=hashes,plans=selected,position='3 MNQ',bar_label='end',start='2025-01-01',end_exclusive='2025-12-12',
    protocol='Unchanged momentum_stop only; 2023/24 warmup; one/two tick strategy costs. Prop: every eligible chronological start to data end; no bootstrap or wrapping; unfinished paths censored. Primary diagnostic: net after both strategy cost settings >0; does not prove business viability.'),indent=2))
checks()
strategy_main('end',str(out/'strategy'),'2025-01-01','2025-12-12',('momentum_stop',))
dates,tape=build_tape('end',str(out/'strategy'),str(out/'risk'),str(out/'strategy/sessions.csv'),'2025-01-01','2025-12-12')
rows=[]
for scenario in ['base','double_slippage','fees_plus25','payout_delay5']:
    scaled=scale_tape(tape,'MNQ',3,scenario)
    for p in selected:
        for start in range(len(dates)):
            path=[(d,*scaled[i]) for i,d in enumerate(dates[start:],start)]
            r=simulate(path,p,scenario)
            # Horizon reasons also stand for exhaustion of the available history.
            censored=r['outcome'] in ['eval_horizon','funded_horizon','three_payout_censor']
            rows.append(dict(plan=p['name'],scenario=scenario,start=str(dates[start].date()),
                available_sessions=len(path),censored=censored,**r))
attempts=pd.DataFrame(rows);attempts.to_csv(out/'prop_attempts.csv',index=False)
stats=[]
for (plan,scenario),g in attempts.groupby(['plan','scenario']):
    stats.append(dict(plan=plan,scenario=scenario,attempts=len(g),pass_rate=g.passed.mean(),
        payout_rate=g.payouts.gt(0).mean(),mean_observed_cash=g.net.mean(),
        average_fees=g.fees.mean(),average_receipts=g.receipts.mean(),censored_rate=g.censored.mean(),
        median_pass_sessions=g.loc[g.passed,'pass_days'].median()))
prop=pd.DataFrame(stats);prop.to_csv(out/'prop_summary.csv',index=False)
summary=pd.read_csv(out/'strategy/summary.csv')
t=pd.read_csv(out/'strategy/trades.csv')
fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
for ticks,g in t.groupby('ticks'):
    eq=pd.Series(np.r_[0,g.net_dollars.cumsum().to_numpy()])
    ts=[pd.Timestamp('2025-01-01',tz='UTC'),*pd.to_datetime(g.exit_time,utc=True)]
    axes[0].plot(ts,eq/1000,label=f'{ticks} tick(s) per fill')
    axes[1].plot(ts,(eq-eq.cummax())/1000)
axes[0].legend();axes[0].set_ylabel('Net P&L ($000)');axes[1].set_ylabel('Closed-trade DD ($000)')
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Frozen stopped momentum | 2025 out-of-sample | 1 NQ')
fig.text(.5,.015,'End labels assumed · $5 round-trip commission · Closed-trade equity excludes intratrade drawdown',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.05,1,.95));fig.savefig(out/'equity.png',dpi=150);plt.close(fig)
report=['# Frozen 2025 out-of-sample test','',
 'Strategy rules and code hashes recorded in freeze.json before execution. End-label assumption retained. 2025 is now evaluated and must not be treated as untouched for subsequent changes.', '',
 f'{len(dates)} eligible cash sessions. Incomplete sessions excluded ex post; indicators warmed using 2023–2024 without evaluating those trades again.', '',
 '| Period | Ticks | Trades | Win rate | Net $ | PF | Closed-trade DD $ |','|---|---:|---:|---:|---:|---:|---:|']
for r in summary[summary.period.ne('2025')].itertuples():
    report.append(f'| {r.period} | {r.ticks} | {r.trades} | {r.win_rate:.1%} | {r.net_dollars:,.0f} | {r.profit_factor:.2f} | {r.drawdown_dollars:,.0f} |')
report+=['','![OOS equity](equity.png)','','## Prop replay: observed cash only, not lifetime EV','',
 '| Plan | Scenario | Observed mean net $ | Pass | Any payout | Censored |','|---|---|---:|---:|---:|---:|']
for r in prop.itertuples():report.append(f'| {r.plan} | {r.scenario} | {r.mean_observed_cash:.2f} | {r.pass_rate:.1%} | {r.payout_rate:.1%} | {r.censored_rate:.1%} |')
report+=['','Every eligible starting date is followed only to available data end or the existing horizon/three-payout limit. Late starts have less follow-up. Windows overlap and are not independent. Censored balances and later payouts are unvalued, so these means are not comparable lifetime EV estimates or forecasts.', '',
 'Frozen simplified firm presets, 3 MNQ using NQ prices as proxy. Costs and payout assumptions unchanged. Extra-slippage prop stress adds costs to saved fills. No rolling purchases, budget depletion, portfolio correlation, taxes or actual execution validation. Timestamp semantics and roll construction remain unresolved.', '',
 'Validation: simulator synthetic checks and replay reconciliation passed; no earlier stop missed; every entry reconciles to the assumed next-bar open plus slippage. Positive OOS results alone do not establish business readiness.']
(out/'REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print(prop.to_string(index=False))
