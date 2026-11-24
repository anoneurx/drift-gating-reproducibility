import csv, glob, os, subprocess, struct
from statistics import mean
import numpy as np
SIM='./sim_full'
OUT='phase4_baselines'
os.makedirs(OUT,exist_ok=True)
WARM=50000  # pre-specified fixed warmup for 300k-500k real traces

def wss(path):
    b=open(path,'rb').read(); ids=np.frombuffer(b,dtype=np.uint32); return len(np.unique(ids))

def caps(w):
    return [max(1,int(round(0.01*w))), max(1,int(round(0.05*w))), max(1,int(round(0.10*w)))]

def run_one(trace, C, npv, tag, extra, methods=None, daonly=False):
    out=f'{OUT}/{tag}.csv'; det=f'{OUT}/{tag}_det.csv'
    if os.path.exists(out) and os.path.exists(det):
        # sanity: non-empty
        try:
            if os.path.getsize(out)>0 and os.path.getsize(det)>0: return out,det
        except: pass
    for f in [out,det]:
        try: os.remove(f)
        except: pass
    cmd=[SIM,'--trace',trace,'--C',str(C),'--warm',str(WARM),'--np',str(npv),'--ncand','5','--kfrac','0','--z','1.28','--edelay','10']
    if methods: cmd+=['--methods',methods]
    if daonly: cmd+=['--da-only']
    cmd+=extra+['--out',out,'--det',det]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return out,det

traces=[]
for p in sorted(glob.glob('public_split/*.bin')):
    traces.append(('fiu',p))
for p in sorted(glob.glob('../traces_real/*.bin')):
    traces.append(('prog',p))
# also include traces_real if run from reproduction
for p in sorted(glob.glob('traces_real/*.bin')):
    traces.append(('prog2',p))

# dedupe by abspath
seen=set(); uniq=[]
for kind,p in traces:
    ap=os.path.abspath(p)
    if ap in seen: continue
    seen.add(ap); uniq.append(( 'prog' if 'traces_real' in p else 'fiu', ap))

rows=[]
for kind,p in uniq:
    base=os.path.basename(p).replace('.bin','')
    b=open(p,"rb").read(); ids=np.frombuffer(b,dtype=np.uint32)
    w=len(np.unique(ids)); npv=int(ids.max())+1
    for C in caps(w):
        captag=f'C{C}'
        tag=f'{base}_{captag}_base'
        run_one(p,C,npv,tag,[],methods='LRU,ARC,S3-FIFO,SIEVE,W-TinyLFU,ContShadow')
        tag=f'{base}_{captag}_ph'
        run_one(p,C,npv,tag,['--trigger','ph','--ph-delta','0.001','--ph-lambda','2'],daonly=True)
        tag=f'{base}_{captag}_adwin'
        run_one(p,C,npv,tag,['--trigger','adwin','--adwin-delta','0.05'],daonly=True)
        print('done',base,C,flush=True)
print('all done')
