"""Prop lifecycle simulator using saved momentum minute equity, 2023/24 only.
One paid evaluation followed by at most one funded account. No automatic retries.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def floor_value(peak, plan):
    if plan['drawdown_mode']=='static':
        return -plan['drawdown_allowance']
    return min(peak-plan['drawdown_allowance'],plan['trailing_floor_cap'])


def simulate(days, order, p):
    fees=float(p['evaluation_fee']); received=0.; balance=0.; peak=0.
    phase='evaluation'; age=0; funded_days=0; qualifying=0; count=0; best_day=0.
    passed=False; outcome='evaluation_timeout'; pass_day=None
    for position, index in enumerate(order):
        age+=1
        if age>1 and (age-1)%p['rebill_every_trading_days']==0:
            fees+=p['evaluation_fee'] if phase=='evaluation' else p['funded_recurring_fee']
        low,close,traded=days[index]
        # Historical daily equity paths are relative to start-of-day balance.
        start=balance
        floor=floor_value(peak,p)
        values=start+low*p['nq_contracts']
        drawdown_hits=np.flatnonzero(values<=floor)
        daily_hits=np.flatnonzero(values<=start-p['daily_loss_limit'])
        if len(drawdown_hits) or len(daily_hits):
            first_dd=drawdown_hits[0] if len(drawdown_hits) else np.inf
            first_daily=daily_hits[0] if len(daily_hits) else np.inf
            cause='drawdown' if first_dd<=first_daily else 'daily_loss'
            outcome=phase+'_'+cause
            if phase=='funded': funded_days=age
            break
        pnl=close*p['nq_contracts']; balance+=pnl
        peak=max(peak,balance)
        best_day=max(best_day,pnl)
        # EOD trailing threshold updates after trading and never lowers after payout.
        if balance<=floor_value(peak,p):
            outcome=phase+'_eod_drawdown'; break
        if phase=='evaluation':
            qualifying+=int(traded)
            consistent=p['consistency_limit'] is None or best_day<=p['consistency_limit']*balance
            if balance>=p['evaluation_target'] and qualifying>=p['minimum_evaluation_days'] and consistent:
                passed=True; pass_day=position+1; fees+=p['activation_fee']
                phase='funded'; balance=peak=0.; age=qualifying=0; best_day=0.
                outcome='funded_horizon'; continue
            if age>=p['evaluation_horizon_days']:
                outcome='evaluation_timeout'; break
        else:
            funded_days=age
            qualifying+=int(pnl>=p['qualifying_day_profit'])
            available=min(p['maximum_payout'],balance-p['payout_buffer'])
            consistent=p['consistency_limit'] is None or best_day<=p['consistency_limit']*balance
            if qualifying>=p['payout_qualifying_days'] and available>=p['minimum_payout'] and consistent:
                # Entire request debits account; trader receives only their share.
                balance-=available; received+=available*p['trader_share']; count+=1
                qualifying=0; best_day=0.
                if balance<=floor_value(peak,p):
                    outcome='funded_post_payout_breach'; break
            if age>=p['funded_horizon_days']:
                outcome='funded_horizon'; break
    return dict(passed=passed,pass_day=pass_day,payout_count=count,payout_received=received,
                fees=fees,net_cash=received-fees,outcome=outcome,funded_days=funded_days,
                residual_account_balance=balance)


def load_days():
    a=pd.read_csv('outputs/momentum_risk_audit/minute_equity.csv')
    a['date']=pd.to_datetime(a.time,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    s=pd.read_csv('outputs/intraday_candidates/sessions.csv')
    dates=s.loc[s.eligible,'date'].tolist()
    assert all(x<'2025-01-01' for x in dates)
    groups={k:g for k,g in a.groupby('date',sort=False)}
    previous=0.; days=[]
    for date in dates:
        if date in groups:
            g=groups[date]
            lows=g.equity_low.to_numpy()-previous
            finish=float(g.equity_close.iloc[-1])-previous
            previous=float(g.equity_close.iloc[-1])
            days.append((lows,finish,True))
        else:
            days.append((np.array([0.]),0.,False))
    assert abs(sum(x[1] for x in days)-84720)<1e-6
    return dates,days


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan',default='prop_plan.json')
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--simulations',type=int,default=2000)
    args=ap.parse_args()
    p=json.loads(Path(args.plan).read_text())
    assert p['drawdown_mode'] in ['static','end_of_day_trailing']
    assert isinstance(p['nq_contracts'],int) and p['nq_contracts']>=1
    assert p['rebill_every_trading_days']>0 and 0<p['trader_share']<=1
    dates,days=load_days(); horizon=p['evaluation_horizon_days']+p['funded_horizon_days']
    assert horizon<=len(days)
    out=Path('outputs/prop_simulator'); out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for start in range(len(days)-horizon+1):
        rows.append(dict(method='historical_window',start=dates[start],**simulate(days,range(start,start+horizon),p)))
    rng=np.random.default_rng(args.seed)
    # Moving blocks preserve ten consecutive eligible daily paths; boundaries remain synthetic.
    for iteration in range(args.simulations):
        order=[]
        while len(order)<horizon:
            start=int(rng.integers(0,len(days)-10+1)); order.extend(range(start,start+10))
        rows.append(dict(method='block_bootstrap',start=iteration,**simulate(days,order[:horizon],p)))
    frame=pd.DataFrame(rows); frame.to_csv(out/'attempts.csv',index=False)
    summaries=[]
    for method,g in frame.groupby('method'):
        funded=g[g.passed]
        summaries.append(dict(method=method,attempts=len(g),pass_rate=g.passed.mean(),
            any_payout_rate=(g.payout_count>0).mean(),funded_any_payout_rate=(funded.payout_count>0).mean(),
            expected_fees=g.fees.mean(),expected_receipts=g.payout_received.mean(),ev_per_attempt=g.net_cash.mean(),
            probability_net_profit=(g.net_cash>0).mean(),cash_p05=g.net_cash.quantile(.05),cash_median=g.net_cash.median(),
            cash_p95=g.net_cash.quantile(.95),funded_gross_receipts=funded.payout_received.mean(),
            mean_days_to_pass=funded.pass_day.mean(),funded_alive_at_horizon=(funded.outcome=='funded_horizon').mean()))
    summary=pd.DataFrame(summaries); summary.to_csv(out/'summary.csv',index=False)
    frame.groupby(['method','outcome']).size().rename('count').to_csv(out/'outcomes.csv')
    (out/'plan.json').write_text(json.dumps(p,indent=2))
    report='# Hypothetical prop-firm simulation\n\nNOT a named firm or a forecast. Unchanged momentum strategy, one NQ by default. 2023/2024 only; no 2025.\n\n'
    report+='Each attempt pays evaluation fees, may pass, then enters one funded account on the next eligible day. Evaluation max 60 eligible days; funded max 60. No retries. Rebilling every 20 eligible trading days is a hypothetical approximation, not calendar billing. One flat evaluation fee includes all contracts. Drawdown is end-of-day trailing, locked at starting balance; daily loss counts unrealized lows and is a hard breach. Pass evaluated at day end. Withdrawals debit full requested amount; cash receipts use the trader share.\n\n'
    report+='Open equity comes from minute lows, including entry-side commission; closing fees/slippage follow original fills. Intraday barrier crossings terminate the account. No borrowed account balance is paid to the trader, and terminal balances have zero realized cash value in this horizon. Living funded accounts are right-censored, so this is horizon cash EV, not lifetime EV.\n\n'
    report+='Historical windows overlap. Bootstrap uses 10-day moving blocks (seed '+str(args.seed)+'); simulations are resamples of the same 477 eligible sessions, not independent market evidence. Excluded sessions, unknown timestamp labels and rollover construction remain limitations. Strategy was chosen after inspecting 2023/24. No payout denial/counterparty risk, tax, market impact, calendar holidays, latency, hard position stop or consistency rule unless supplied.\n\n'
    report+='| Method | Attempts | Pass | Any payout | EV/attempt | Expected fees | Expected receipts |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for r in summary.itertuples():
        report+=f'| {r.method} | {r.attempts} | {r.pass_rate:.1%} | {r.any_payout_rate:.1%} | ${r.ev_per_attempt:.2f} | ${r.expected_fees:.2f} | ${r.expected_receipts:.2f} |\n'
    (out/'REPORT.md').write_text(report,encoding='utf-8')
    print(summary.to_string(index=False)); print(frame.groupby(['method','outcome']).size().to_string())


if __name__=='__main__':
    main()
