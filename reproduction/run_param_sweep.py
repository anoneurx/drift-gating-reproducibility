import subprocess, csv, os
from statistics import mean
SIM='./sim_full'
base=['--seed','5001','--ncand','5','--kfrac','0','--z','1.28','--edelay','10','--da-only']
os.makedirs('param_sweep',exist_ok=True)
def run(tag, extra):
    out=f'param_sweep/{tag}.csv'; det=f'param_sweep/{tag}_det.csv'
    cmd=[SIM]+base+extra+['--out',out,'--det',det]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    rows=list(csv.DictReader(open(out)))
    ns=[r for r in rows if r['scenario']!='stable']
    det_rows=list(csv.DictReader(open(det)))
    nsd=[r for r in det_rows if r['scenario']!='stable']
    return tag, mean(float(r['miss_ratio']) for r in ns), mean(float(r['shadow_evals']) for r in ns), mean(float(r['switches']) for r in ns), sum(int(r['detected']) for r in nsd), sum(int(r['spurious']) for r in nsd)
jobs=[]
for d in [0.1,0.3,0.5,0.7,1.0]: jobs.append((f'delta_{d}',['--delta',str(d)]))
for h in [2,3,5,7,10]: jobs.append((f'h_{h}',['--h',str(h)]))
for W in [1000,2000,4000]: jobs.append((f'W_{W}',['--W',str(W)]))
for p in [0.05,0.1,0.2,0.4]: jobs.append((f'p_{p}',['--p',str(p)]))
seen=set(); uniq=[]
for t,e in jobs:
    k=tuple(e)
    if k in seen: continue
    seen.add(k); uniq.append((t,e))
results=[]
for t,e in uniq:
    r=run(t,e); results.append(r); print(r, flush=True)
results.sort()
with open('param_sweep/summary.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['tag','miss','shadow_evals','switches','detected','spurious'])
    for r in results: w.writerow(r)
print('done')
