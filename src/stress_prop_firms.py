"""Current-rule-inspired Topstep / Tradeify Flex cash EV stress study.
Rule snapshot 2026-09-17. No 2025 market data. See generated limitations.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

SOURCES={
 'topstep_pricing':'https://help.topstep.com/en/articles/14289835-topstep-pricing-and-payment-questions',
 'topstep_consistency':'https://help.topstep.com/en/articles/8284208-consistency-at-topstep',
 'topstep_payout':'https://help.topstep.com/en/articles/8284233-topstep-payout-policy',
 'topstep_drawdown':'https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit',
 'tradeify_pricing':'https://help.tradeify.co/en/articles/14369021-tradeify-pricing-reference',
 'tradeify_eval':'https://help.tradeify.co/en/articles/12853921-select-evaluation-accounts',
 'tradeify_payout':'https://help.tradeify.co/en/articles/12853966-select-flex-and-select-daily-payout-policies'}


def plans():
    result=[]
    for i,size in enumerate([50,100,150]):
        for path in ['standard','no_activation']:
            result.append(dict(name=f'Topstep_{size}K_{path}',firm='Topstep',size=size,
                fee=([49,99,199] if path=='standard' else [95,149,229])[i],
                activation=149 if path=='standard' else 0,monthly=True,
                target=[3000,6000,9000][i],dd=[2000,3000,4500][i],cap_floor=0,
                consistency=.55,min_eval_days=2,payout_cap=[2000,3000,5000][i],
                win_threshold=150,min_payout=125,withdraw_fee=30))
        result.append(dict(name=f'Tradeify_{size}K_Select_Flex',firm='Tradeify',size=size,
            fee=[165,265,369][i],activation=0,monthly=False,target=[3000,6000,9000][i],
            dd=[2000,3000,4500][i],cap_floor=100,consistency=.4,min_eval_days=3,
            payout_cap=[2500,3500,4500][i],win_threshold=[150,200,250][i],min_payout=250,withdraw_fee=0))
    return result


def tape():
    a=pd.read_csv('outputs/momentum_risk_audit/minute_equity.csv')
    a['date']=pd.to_datetime(a.time,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    s=pd.read_csv('outputs/intraday_candidates/sessions.csv')
    dates=pd.to_datetime(s.loc[s.eligible,'date']).tolist()
    groups={k:g for k,g in a.groupby('date',sort=False)}
    daily=[]; previous=0.
    for date in dates:
        g=groups.get(str(date.date()))
        if g is None:
            daily.append((np.zeros(1),0.,np.zeros(1),False)); continue
        counts=g.kind.isin(['entry_fill','exit_fill']).cumsum().to_numpy()
        low=g.equity_low.to_numpy()-previous
        end=float(g.equity_close.iloc[-1])-previous
        previous=float(g.equity_close.iloc[-1])
        daily.append((low,end,counts,True))
    assert abs(sum(d[1] for d in daily)-84720)<1e-6
    return dates,daily


def scale_tape(daily,instrument,contracts,scenario):
    exposure=contracts*(.1 if instrument=='MNQ' else 1)
    commission=contracts*(1.82 if instrument=='MNQ' else 5.76)
    extra_tick=1 if scenario=='double_slippage' else 0
    result=[]
    for low,end,counts,traded in daily:
        # Undo original $2.50 commission/fill, scale price P&L, then charge proper
        # per-contract costs and additional adverse slippage at each fill.
        correction=(2.5*exposure-commission/2-extra_tick*5*exposure)
        l=low*exposure+counts*correction
        e=end*exposure+counts[-1]*correction
        result.append((float(l.min()),float(e),traded))
    return result


def simulate(path,p,scenario):
    fee_multiplier=1.25 if scenario=='fees_plus25' else 1.
    fees=p['fee']*fee_multiplier; cash=0.; balance=peak=best=0.
    phase='eval'; phase_age=0; traded_days=wins=payouts=0; cycle=0.; passed=False
    floor_forced=False; rebill=pd.Timestamp('2023-01-01')+pd.DateOffset(months=1)
    begin=None; reason='eval_horizon'; blocked_until=None; pass_age=None
    for elapsed,(date,low,pnl,traded) in enumerate(path):
        phase_age+=1
        if begin is None:
            begin=date; rebill=begin+pd.DateOffset(months=1)
        if phase=='eval' and p['monthly']:
            while date>=rebill:
                fees+=p['fee']*fee_multiplier; rebill+=pd.DateOffset(months=1)
        if phase=='funded' and blocked_until is not None and date<=blocked_until:
            if phase_age>=120: reason='funded_horizon'; break
            continue
        floor=p['cap_floor'] if floor_forced else min(peak-p['dd'],p['cap_floor'])
        if balance+low<=floor:
            reason=phase+'_drawdown'; break
        balance+=pnl; peak=max(peak,balance); best=max(best,pnl)
        traded_days+=int(traded)
        if phase=='eval':
            if balance>=p['target'] and traded_days>=p['min_eval_days'] and best<=p['consistency']*balance:
                passed=True; pass_age=elapsed+1; fees+=p['activation']*fee_multiplier
                phase='funded'; phase_age=0; balance=peak=best=cycle=0.; wins=traded_days=0
                reason='funded_horizon'
            elif phase_age>=120: reason='eval_horizon'; break
        else:
            cycle+=pnl; wins+=int(pnl>=p['win_threshold'])
            amount=min(balance*.5,p['payout_cap'])
            if wins>=5 and (payouts==0 or cycle>0) and amount>=p['min_payout']:
                balance-=amount; cash+=.9*amount-p['withdraw_fee']; payouts+=1
                floor_forced=True; wins=0; cycle=0.; best=0.
                # Conservative truncation before uncertain live-account transition.
                if payouts>=3: reason='three_payout_censor'; break
                blocked_until=date+pd.Timedelta(days=5 if scenario=='payout_delay5' else 1)
                if balance<=p['cap_floor']: reason='funded_post_payout_breach'; break
            if phase_age>=120: reason='funded_horizon'; break
    return dict(passed=passed,pass_days=pass_age,fees=fees,receipts=cash,net=cash-fees,
                payouts=payouts,outcome=reason,days=elapsed+1)


def checks():
    p=plans()[0].copy(); p.update(target=100,dd=100,min_eval_days=2,consistency=.55,fee=10,activation=20,win_threshold=10,min_payout=1,payout_cap=100,withdraw_fee=0)
    dates=pd.date_range('2023-01-01',periods=10)
    a=simulate([(dates[0],-101,500,True)],p,'base')
    assert not a['passed'] and a['net']==-10
    a=simulate([(dates[0],0,60,True),(dates[1],0,60,True)]+[(d,0,20,True) for d in dates[2:7]],p,'base')
    assert a['passed'] and a['fees']==30 and a['payouts']==1 and a['receipts']==45
    assert abs(scale_tape([(np.array([-2.5,95.]),95.,np.array([1,2]),True)],'MNQ',1,'base')[0][1]-8.18)<1e-8


def main(input_tape=None, out_dir='outputs/prop_firm_stress', strategy_label='Original momentum'):
    checks(); dates,raw=tape() if input_tape is None else input_tape
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'plans.json').write_text(json.dumps(plans(),indent=2));(out/'sources.json').write_text(json.dumps(SOURCES,indent=2))
    horizon=240; sequences=[]
    for start in range(len(dates)-horizon+1):
        sequences.append(('historical',start,list(range(start,start+horizon)),dates[start:start+horizon]))
    for seed in [42,123]:
        rng=np.random.default_rng(seed)
        for n in range(250):
            indexes=[]
            while len(indexes)<horizon:
                s=int(rng.integers(0,len(dates)-10+1)); indexes.extend(range(s,s+10))
            sequences.append((f'bootstrap_{seed}',n,indexes[:horizon],list(pd.bdate_range('2023-01-02',periods=horizon))))
    rows=[]
    for instrument,quantity in [('MNQ',1),('MNQ',2),('MNQ',3),('MNQ',5),('MNQ',10),('NQ',1)]:
        for scenario in ['base','double_slippage','fees_plus25','payout_delay5']:
            scaled=scale_tape(raw,instrument,quantity,scenario)
            for p in plans():
                results=[]
                for method,n,indexes,clock in sequences:
                    path=[(date,*scaled[idx]) for date,idx in zip(clock,indexes)]
                    result=simulate(path,p,scenario)
                    results.append(dict(method=method,run=n,**result))
                f=pd.DataFrame(results)
                # Full records retained for baseline only; stress summaries are sufficient.
                if scenario=='base': f.to_csv(out/f"{p['name']}_{quantity}{instrument}.csv",index=False)
                for method,g in f.groupby('method'):
                    funded=g[g.passed]
                    rows.append(dict(plan=p['name'],position=f'{quantity} {instrument}',scenario=scenario,method=method,
                        simulations=len(g),pass_rate=g.passed.mean(),payout_rate=(g.payouts>0).mean(),
                        funded_payout_rate=(funded.payouts>0).mean(),ev=g.net.mean(),expected_fees=g.fees.mean(),
                        expected_receipts=g.receipts.mean(),profit_probability=(g.net>0).mean(),median_cash=g.net.median(),
                        cash_p05=g.net.quantile(.05),cash_p95=g.net.quantile(.95),
                        median_pass_sessions=funded.pass_days.median(),
                        pass_within5=(g.passed & g.pass_days.le(5)).mean(),
                        pass_within10=(g.passed & g.pass_days.le(10)).mean(),
                        pass_within20=(g.passed & g.pass_days.le(20)).mean(),
                        eval_breach_rate=g.outcome.eq('eval_drawdown').mean(),
                        funded_breach_rate=g.outcome.isin(['funded_drawdown','funded_post_payout_breach']).mean(),
                        funded_net_before_activation=(funded.receipts-p['activation']).mean(),
                        censored_rate=g.outcome.isin(['eval_horizon','funded_horizon','three_payout_censor']).mean()))
        print('Completed',quantity,instrument,flush=True)
    summary=pd.DataFrame(rows);summary.to_csv(out/'summary.csv',index=False)
    report='''# Topstep / Tradeify scenario study

Rule snapshot: 2026-09-17. Nine rule-inspired plans: Topstep Standard and No Activation pricing with XFA Standard payout, plus Tradeify Select Flex, each 50/100/150K. No DLL add-ons. Not exact firm replication or a purchasing recommendation.

Each run buys one evaluation and, if passed, activates one funded account. No resets, rebuy cycles or multiple simultaneous accounts. Stop after 120 evaluation sessions, 120 funded sessions or three payouts. Horizons are analyst limits, NOT firm deadlines; residual balances and future payouts are unvalued. Three-payout censoring avoids extrapolating uncertain live transitions.

477 eligible sessions from the selected 2023/24 momentum backtest. 238 overlapping historical starts and 500 ten-session block-bootstrap paths (250 each seeds 42 and 123). These are correlated resamples of a small selected history, NOT independent evidence or out-of-sample forecasts. 2025 remains untested.

EOD trailing floors are checked against minute equity lows throughout each session; floor locks at $0 for Topstep and +$100 for Tradeify, including after first payout. Evaluation targets 3000/6000/9000, drawdown 2000/3000/4500. Consistency 55% Topstep, 40% Tradeify. Five qualifying profit days per payout, positive cycle profit after first payout. Withdraw up to half balance subject to size cap; 90% receipt. Tradeify qualifying days 150/200/250; Topstep 150. Request at first eligibility, skip next calendar day as conservative processing treatment. Topstep $30 withdrawal fee modeled; Tradeify $0 assumed. Calendar monthly Topstep billing; synthetic bootstrap uses a weekday calendar without holidays. Current rules applied counterfactually to older returns, not historical account performance.

NQ price paths proxy MNQ execution; this is NOT observed MNQ data. Costs replace original $5 round trip with $5.76/NQ or $1.82/MNQ. These are Tradeify published rates applied as a common conservative modeling assumption also to Topstep, not verified Topstep commissions. Slippage starts at one tick each side; separate stress doubles it. Other standalone stresses add 25% to evaluation/activation fees or pause five calendar days after payouts. No combined stress, taxes, FX, payment rejection, slippage jumps at breach, inactivity rules or discretionary risk interventions. Sizes stay at/below one mini equivalent.

The underlying dataset has unresolved timestamp/rollover conventions; excluded sessions remain excluded. No assumption that payout qualification guarantees receipt: model assumes payment succeeds. Funded EV columns are conditional on passing within the horizon and include three-payout truncation. Censored outcomes must not be treated as terminal failures. No unsupported claim of lifetime EV.

Sources and numerical presets are in sources.json and plans.json. Full baseline attempts are saved per plan/size; summary.csv includes all stress results. Fees and rules can change; verify checkout before use.
'''
    report=report.replace('477 eligible sessions',f'{len(dates)} eligible sessions').replace('238 overlapping historical starts',f'{max(0,len(dates)-horizon+1)} overlapping historical starts')
    best=summary[(summary.scenario=='base')&(summary.method=='historical')].sort_values('ev',ascending=False).head(12)
    report+=f'\nStrategy: {strategy_label}. Numerical plan presets reused for a controlled comparison; not independently refreshed in this run.\n'
    report+='\n## Interpretation\n\nHistorical starts require 240 future eligible sessions and therefore are concentrated in the earlier portion of the sample; bootstrap paths draw from the full sample including later profitable periods. Blocks also disrupt longer market regimes and transitions. Do not average these methods into a forecast or select a plan from the most favorable seeded result. Pass-within-5/10/20 rates count all purchased evaluations, not just successful ones. Pass time is measured in eligible sessions.\n\n'
    report+='\n## Highest historical cash EV scenarios (selection-biased; not recommendations)\n\n| Plan | Position | Pass | Payout | Cash EV | Median cash |\n|---|---|---:|---:|---:|---:|\n'
    for r in best.itertuples(): report+=f'| {r.plan} | {r.position} | {r.pass_rate:.1%} | {r.payout_rate:.1%} | ${r.ev:.2f} | ${r.median_cash:.2f} |\n'
    (out/'REPORT.md').write_text(report,encoding='utf-8')
    print(best[['plan','position','pass_rate','payout_rate','ev','median_cash']].to_string(index=False))


if __name__=='__main__': main()
