import glob, os, subprocess
import numpy as np
WARM=50000
OUT='phase4_external'
os.makedirs(OUT,exist_ok=True)
TR='/tmp/opencode/external_traces/converted'
for p in sorted(glob.glob(TR+'/*.bin')):
    base=os.path.basename(p)[:-4]
    b=open(p,'rb').read(); ids=np.frombuffer(b,dtype=np.uint32)
    w=len(np.unique(ids)); npv=int(ids.max())+1; nrefs=len(ids)
    for frac in [0.01,0.05,0.10]:
        C=max(1,int(round(frac*w)))
        out=f'{OUT}/{base}_C{C}.csv'
        if os.path.exists(out) and os.path.getsize(out)>0: continue
        cmd=['./sim_full','--trace',p,'--C',str(C),'--warm',str(WARM),'--np',str(npv),
             '--ncand','5','--kfrac','0','--z','1.28','--edelay','10',
             '--methods','LRU,ARC,S3-FIFO,SIEVE,W-TinyLFU,LHD,ContShadow',
             '--out',out,'--det',out.replace('.csv','_det.csv')]
        subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        print('done',base,C,'nrefs',nrefs,'wss',w,flush=True)
print('all done')
