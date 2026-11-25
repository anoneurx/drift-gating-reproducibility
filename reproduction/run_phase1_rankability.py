#!/usr/bin/env python3
"""Phase 1 rankability grid. Pre-specified in PROTOCOL.md (2026-11-23).
Runs synthetic and FIU train/test grids with eval diagnostics.
"""
import csv, os, subprocess, itertools
from statistics import mean
from concurrent.futures import ProcessPoolExecutor, as_completed

SIM='./sim_full'
OUTDIR='phase1_rankability'
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(OUTDIR+'/diag', exist_ok=True)

SYNTH_C=[500,1000,2000,4000]
FIU_C=[1000,2000,5000,10000,20000]
PS=[0.05,0.1,0.2,0.4]
FS=[0.0,0.25,0.5,0.75]

FIU_TRAIN=['--trace','public_split/fiu_homes-110108-112108.oracleGeneral.train.bin','--trace','public_split/fiu_ikki-110108-112108.oracleGeneral.train.bin','--trace','public_split/fiu_madmax-110108-112108.oracleGeneral.train.bin','--trace','public_split/fiu_online.cs.fiu.edu-110108-113008.oracleGeneral.train.bin','--trace','public_split/fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral.train.bin','--trace','public_split/fiu_webresearch-030409-033109.oracleGeneral.train.bin']
FIU_TEST=['--trace','public_split/fiu_homes-110108-112108.oracleGeneral.test.bin','--trace','public_split/fiu_ikki-110108-112108.oracleGeneral.test.bin','--trace','public_split/fiu_madmax-110108-112108.oracleGeneral.test.bin','--trace','public_split/fiu_online.cs.fiu.edu-110108-113008.oracleGeneral.test.bin','--trace','public_split/fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral.test.bin','--trace','public_split/fiu_webresearch-030409-033109.oracleGeneral.test.bin']
FIU_BASE=['--np','1048576','--warm','50000','--kfrac','0','--z','1.28','--edelay','10','--da-only','--s3frac','0.05','--twoqkin','125','--lprthr','0.1','--lecarlr','0.6','--lirsfrac','0.05','--ncand','5']


def run_one(job):
    kind,C,p,f,split=job
    W=2*C
    tag=f'{kind}_C{C}_p{p:g}_f{f:g}_{split}'
    out=f'{OUTDIR}/{tag}.csv'
    det=f'{OUTDIR}/{tag}_det.csv'
    diag=f'{OUTDIR}/diag/{tag}_eval.csv'
    if os.path.exists(out) and os.path.exists(diag):
        return summarize(tag,kind,C,p,f,W,split,out,det,diag)
    if kind=='synth':
        seed='100' if split=='train' else '5001'
        cmd=[SIM,'--seed',seed,'--ncand','5','--kfrac','0','--z','1.28','--edelay','10','--da-only','--C',str(C),'--W',str(W),'--p',str(p),'--cs-cap-f',str(f),'--eval-diag',diag,'--out',out,'--det',det]
    else:
        traces=FIU_TRAIN if split=='train' else FIU_TEST
        cmd=[SIM]+FIU_BASE+['--C',str(C),'--W',str(W),'--p',str(p),'--cs-cap-f',str(f),'--eval-diag',diag]+traces+['--out',out,'--det',det]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return summarize(tag,kind,C,p,f,W,split,out,det,diag)


def summarize(tag,kind,C,p,f,W,split,out,det,diag):
    rows=list(csv.DictReader(open(out)))
    da=[r for r in rows if r['method'].startswith('DA')]
    if kind=='synth':
        da=[r for r in da if r['scenario']!='stable']
    miss=mean(float(r['miss_ratio']) for r in da)
    sw=mean(float(r['switches']) for r in da)
    ev=mean(float(r['shadow_evals']) for r in da)
    # diag
    rank_frac=0.0; n_eval=0; mean_Cs=0.0; mean_Dw=0.0; mean_ratio=0.0
    if os.path.exists(diag):
        dr=list(csv.DictReader(open(diag)))
        n_eval=len(dr)
        if n_eval:
            rank_frac=mean(int(r['rankable']) for r in dr)
            mean_Cs=mean(float(r['Cs']) for r in dr)
            mean_Dw=mean(float(r['Dw']) for r in dr)
            mean_ratio=mean(float(r['Cs'])/float(r['Dw']) if float(r['Dw'])>0 else 0 for r in dr)
    return {'tag':tag,'kind':kind,'C':C,'p':p,'f':f,'W':W,'split':split,'miss':miss,'switches':sw,'shadow_evals':ev,'n_eval':n_eval,'rankable_frac':rank_frac,'mean_Cs':mean_Cs,'mean_Dw':mean_Dw,'mean_Cs_over_Dw':mean_ratio}


def main():
    jobs=[]
    for C,p,f in itertools.product(SYNTH_C,PS,FS):
        jobs.append(('synth',C,p,f,'train'))
        jobs.append(('synth',C,p,f,'test'))
    for C,p,f in itertools.product(FIU_C,PS,FS):
        jobs.append(('fiu',C,p,f,'train'))
        jobs.append(('fiu',C,p,f,'test'))
    print(f'total jobs {len(jobs)}')
    results=[]
    with ProcessPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(run_one,j):j for j in jobs}
        for fut in as_completed(futs):
            r=fut.result(); results.append(r)
            print(f"done {r['tag']} miss={r['miss']:.6f} rank={r['rankable_frac']:.3f}", flush=True)
    keys=['tag','kind','C','p','f','W','split','miss','switches','shadow_evals','n_eval','rankable_frac','mean_Cs','mean_Dw','mean_Cs_over_Dw']
    for split in ['train','test']:
        for kind in ['synth','fiu']:
            out=f'{OUTDIR}/{kind}_{split}_summary.csv'
            rs=[r for r in results if r['split']==split and r['kind']==kind]
            rs.sort(key=lambda r:(r['C'],r['f'],r['p']))
            with open(out,'w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(rs)
    with open(f'{OUTDIR}/all_summary.csv','w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(sorted(results,key=lambda r:(r['kind'],r['split'],r['C'],r['f'],r['p'])))
    print('done')

if __name__=='__main__':
    main()
