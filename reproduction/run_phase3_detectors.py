import subprocess, csv, os, itertools
from statistics import mean
SIM='./sim_full'
OUT='phase3_detectors'
os.makedirs(OUT,exist_ok=True)
BASE=['--ncand','5','--kfrac','0','--z','1.28','--edelay','10','--da-only']
def run(tag,args,seed):
    out=f'{OUT}/{tag}_seed{seed}.csv'; det=f'{OUT}/{tag}_seed{seed}_det.csv'
    if not (os.path.exists(out) and os.path.exists(det)):
        cmd=[SIM,'--seed',str(seed)]+BASE+args+['--out',out,'--det',det]
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    rows=list(csv.DictReader(open(out)))
    ns=[r for r in rows if r['scenario']!='stable']
    dets=list(csv.DictReader(open(det)))
    nsd=[r for r in dets if r['scenario']!='stable']
    detected=sum(int(r['detected']) for r in nsd)
    total=sum(int(r['n_bounds']) for r in nsd)
    spurious=sum(int(r['spurious']) for r in nsd)
    return tag,seed,mean(float(r['miss_ratio']) for r in ns),mean(float(r['shadow_evals']) for r in ns),mean(float(r['switches']) for r in ns),detected,total,spurious
jobs=[]
for d,l in itertools.product([0.001,0.005,0.01,0.02],[1,2,5,10,20]):
    tag=f'ph_d{d}_l{l}'; jobs.append((tag,['--trigger','ph','--ph-delta',str(d),'--ph-lambda',str(l)],100))
for d in [0.002,0.01,0.05,0.1]:
    tag=f'adwin_d{d}'; jobs.append((tag,['--trigger','adwin','--adwin-delta',str(d)],100))
res=[]
for j in jobs:
    r=run(*j); res.append(r); print(r,flush=True)
res.sort()
with open(f'{OUT}/train_summary.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['tag','seed','miss','shadow_evals','switches','detected','total','spurious'])
    for r in res: w.writerow(r)
print('done')
