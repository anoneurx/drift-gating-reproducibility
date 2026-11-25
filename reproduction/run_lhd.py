import glob, os, subprocess
import numpy as np
WARM=50000
OUT='phase4_lhd'
os.makedirs(OUT,exist_ok=True)
# synthetic
if not os.path.exists(f'{OUT}/synth_lhd.csv'):
    subprocess.run(['./sim_full','--seed','5001','--ncand','5','--kfrac','0','--z','1.28','--edelay','10','--methods','LHD','--out',f'{OUT}/synth_lhd.csv','--det',f'{OUT}/synth_lhd_det.csv'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
# real traces
traces=sorted(glob.glob('public_split/*.bin'))+sorted(glob.glob('../traces_real/*.bin'))
for p in traces:
    b=open(p,'rb').read(); ids=np.frombuffer(b,dtype=np.uint32)
    w=len(np.unique(ids)); npv=int(ids.max())+1
    for frac in [0.01,0.05,0.10]:
        C=max(1,int(round(frac*w)))
        base=os.path.basename(p).replace('.bin','')
        tag=f'{base}_C{C}_lhd'
        out=f'{OUT}/{tag}.csv'
        if os.path.exists(out) and os.path.getsize(out)>0: continue
        subprocess.run(['./sim_full','--trace',p,'--C',str(C),'--warm',str(WARM),'--np',str(npv),'--ncand','5','--kfrac','0','--z','1.28','--edelay','10','--methods','LHD','--out',out,'--det',out.replace('.csv','_det.csv')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('done',base,flush=True)
print('all done')
