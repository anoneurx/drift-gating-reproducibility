import subprocess, csv, os
from statistics import mean
SIM='./sim_full'
traces=['--trace','public_split/fiu_homes-110108-112108.oracleGeneral.test.bin','--trace','public_split/fiu_ikki-110108-112108.oracleGeneral.test.bin','--trace','public_split/fiu_madmax-110108-112108.oracleGeneral.test.bin','--trace','public_split/fiu_online.cs.fiu.edu-110108-113008.oracleGeneral.test.bin','--trace','public_split/fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral.test.bin','--trace','public_split/fiu_webresearch-030409-033109.oracleGeneral.test.bin']
base=['--np','1048576','--warm','50000','--kfrac','0','--z','1.28','--edelay','10','--da-only','--s3frac','0.05','--twoqkin','125','--lprthr','0.1','--lecarlr','0.6','--lirsfrac','0.05','--ncand','5']
os.makedirs('rankability_real',exist_ok=True)
rows=[]
for C in [500,1000,2000,5000,10000,20000]:
    for p in [0.05,0.1,0.2,0.4]:
        tag=f'fiu_C{C}_p{p}'
        out=f'rankability_real/{tag}.csv'; det=f'rankability_real/{tag}_det.csv'
        cmd=[SIM]+base+['--C',str(C),'--p',str(p)]+traces+['--out',out,'--det',det]
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        rs=list(csv.DictReader(open(out)))
        da=[r for r in rs if r['method'].startswith('DA')]
        miss=mean(float(r['miss_ratio']) for r in da)
        sw=sum(int(r['switches']) for r in da)
        ev=sum(int(r['shadow_evals']) for r in da)
        rows.append((C,p,miss,sw,ev))
        print(C,p,miss,sw,ev,flush=True)
with open('rankability_real/fiu_sweep.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['C','p','mean_miss','total_switches','total_shadow_evals']); w.writerows(rows)
print('done')
