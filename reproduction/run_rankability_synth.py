import subprocess, csv, os
from statistics import mean
SIM='./sim_full'
base=['--seed','5001','--ncand','5','--kfrac','0','--z','1.28','--edelay','10','--da-only']
os.makedirs('rankability_real',exist_ok=True)
rows=[]
for C in [500,1000,2000,4000]:
    for p in [0.05,0.1,0.2,0.4]:
        tag=f'synth_C{C}_p{p}'
        out=f'rankability_real/{tag}.csv'; det=f'rankability_real/{tag}_det.csv'
        cmd=[SIM]+base+['--C',str(C),'--p',str(p),'--out',out,'--det',det]
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        rs=list(csv.DictReader(open(out)))
        ns=[r for r in rs if r['scenario']!='stable']
        miss=mean(float(r['miss_ratio']) for r in ns)
        sw=sum(int(r['switches']) for r in ns)
        ev=sum(int(r['shadow_evals']) for r in ns)
        rows.append((C,p,miss,sw,ev))
        print(C,p,miss,sw,ev,flush=True)
with open('rankability_real/synth_sweep.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['C','p','mean_miss','total_switches','total_shadow_evals']); w.writerows(rows)
print('done')
