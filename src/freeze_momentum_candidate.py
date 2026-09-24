"""Freeze candidate and inspect development-only timestamp clues; no OOS returns."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import pandas as pd
from test_stopped_strategies import RULES


def main():
    out=Path('outputs/momentum_freeze_v1')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():
        raise FileExistsError('Freeze already exists; preserve it and create a new version for changes.')
    files=['test_stopped_strategies.py','check_stopped_strategies.py',
           'simulate_stopped_prop.py','stress_prop_firms.py',
           'backtest_open_candle.py','outputs/stopped_prop/plans.json']
    hashes={}
    for name in files:
        payload=Path(name).read_bytes()
        hashes[name]=hashlib.sha256(payload).hexdigest()
        dest=out/'snapshot'/name; dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(payload)
    raw=pd.read_csv('Dataset_NQ_1min_2022_2025.csv',usecols=['timestamp ET','volume'])
    stamp=pd.to_datetime(raw['timestamp ET'],format='%m/%d/%Y %H:%M')
    mask=stamp.ge('2023-01-01') & stamp.lt('2025-01-01')
    d=raw.loc[mask].copy(); d['time']=stamp.loc[mask]
    d['clock']=d.time.dt.strftime('%H:%M')
    clocks=['09:29','09:30','09:31','09:32','16:59','17:00','17:01','17:59','18:00','18:01','18:02']
    byclock=d[d.clock.isin(clocks)].groupby('clock').volume.agg(['count','median','mean']).reindex(clocks).fillna(0)
    gaps=d.time.diff().dt.total_seconds().div(60)
    restarts=d.loc[gaps.ge(50)].clock.value_counts().head(8)
    evidence={'scope':'2023-2024 only; no OOS returns or prices inspected',
              'rows':len(d),'clock_counts_volume':byclock.to_dict(orient='index'),
              'restart_labels_after_50min_gap':restarts.to_dict(),
              'conclusion':'Clues only: cannot identify bar labels, timezone provenance or roll construction without provider metadata.'}
    (out/'timestamp_evidence.json').write_text(json.dumps(evidence,indent=2))
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),
       'status':'Candidate frozen; data-convention verification pending; OOS NOT run',
       'strategy':'momentum_stop', 'development_years':[2023,2024],
       'holdout':'2025-01-01 through 2025-12-11; final day subject to cash-session completeness',
       'primary_prop_comparison':{'position':'3 MNQ','plans':['Topstep_50K_standard','Tradeify_50K_Select_Flex'],
          'reason':'Preserve the position size used in the earlier baseline comparison; do not pick the best new grid result.'},
       'rules':RULES,'sha256':hashes,
       'oos_protocol':[
          'Confirm source timestamp convention, timezone, and continuous-contract roll construction before OOS execution.',
          'If timestamp interpretation requires correction, rerun development with the correction and preserve this superseded freeze.',
          'Use late-2024 history to warm up the 14-session bands, M5 ATR and prior close. No 2025 information may enter an earlier signal.',
          'Keep the 2xATR stop, half-hour signals, neutral/opposite reentry reset, one position, and 16:00 exit unchanged. No target.',
          'Report 2025 strategy returns once at fixed 1 NQ with base and doubled slippage, plus quarter diagnostics without retuning.',
          'For prop replay prioritize the frozen 3 MNQ pair. Predeclare chronological starts and report actual available follow-up; do not fabricate 240 future sessions or wrap the holdout.',
          'Report net cash, fees, payouts, pass times, breaches and censored/open accounts separately. Do not report censored accounts as failures or realized lifetime EV.',
          'Keep full-year strategy evidence separate from incomplete account-lifecycle evidence. Any changes after viewing 2025 retire it as an untouched holdout.'
       ]}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    report=['# Momentum candidate freeze v1','',manifest['status'],'',
      'The selected strategy is stopped momentum, not the failed pullback candidate. The snapshot preserves the existing research code and frozen prop presets; it is not yet an OOS runner.', '',
      '## Timestamp clues: development data only','',
      '| Source label | Rows | Median volume | Mean volume |','|---|---:|---:|---:|']
    for label,r in byclock.iterrows():
        report.append(f'| {label} | {int(r["count"])} | {r["median"]:.0f} | {r["mean"]:.0f} |')
    report+=['','Restarts after gaps of at least 50 minutes: '+str(restarts.to_dict()),'',
      'These patterns cannot prove bar-label convention. Required external evidence: vendor/platform and export settings, what a 09:31 row represents, timezone/DST treatment, and individual-contract versus adjusted continuous futures construction.', '',
      '## Frozen validation protocol','']
    report += [f'{i}. {s}' for i,s in enumerate(manifest['oos_protocol'],1)]
    report+=['','Primary prop size: 3 MNQ for Topstep 50K Standard and Tradeify 50K Select Flex, retaining the earlier comparator rather than selecting the highest EV grid result. NQ data remains a proxy for MNQ execution.','',
      'No 2025 strategy results were computed. Code snapshots and SHA-256 digests are stored with manifest.json.']
    (out/'REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    print(byclock.to_string());print('Restart labels:',restarts.to_dict())
    print('Saved',out/'manifest.json')


if __name__=='__main__':
    main()
