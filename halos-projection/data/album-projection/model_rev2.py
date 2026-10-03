import numpy as np, json
rng=np.random.default_rng(11)
N=40000; H=24
# recalibrated to artist.tools Spotify lifetime + breakout multiples
ARCH={'breakout':(np.log(550_000),0.32),'solid':(np.log(90_000),0.45),
      'modest':(np.log(27_000),0.55),'dud':(np.log(1_200),0.80)}
ORDER=['breakout','solid','modest','dud']
SCEN={'bear':[0.04,0.16,0.30,0.50],'base':[0.12,0.25,0.33,0.30],'bull':[0.28,0.27,0.30,0.15]}
def slow(): s=np.array([.02,.03,.035,.045,.06,.08,.10,.12,.13,.13,.12,.115]); return s/s.sum()
def fast(): s=np.array([.05,.10,.15,.15,.14,.11,.10,.08,.05,.03,.02,.02]); return s/s.sum()
OFFSET=[0,2,2,2,2]; CUT=[1.00,0.70,0.60,0.55,0.50]
XPLAT=1.05  # non-Spotify volume uplift
rps=np.maximum(0.00165*(1-0.015)**np.arange(H),0.00125)
def run(scen):
    p=SCEN[scen]; strm=np.zeros((N,H))
    for t in range(5):
        idx=rng.choice(4,size=N,p=p)
        mu=np.array([ARCH[ORDER[i]][0] for i in idx]); sg=np.array([ARCH[ORDER[i]][1] for i in idx])
        tot=rng.lognormal(mu,sg)*CUT[t]*XPLAT
        f=rng.random(N)<0.5
        sh=np.where(f[:,None],fast()[None,:],slow()[None,:])
        m=tot[:,None]*sh
        dec=rng.normal(-0.075,0.025,size=N)
        tail=m[:,-1:]*np.exp(np.cumsum(np.tile(dec[:,None],(1,12)),axis=1))
        full=np.concatenate([m,tail],axis=1); o=OFFSET[t]
        pad=np.zeros((N,H)); pad[:,o:]=full[:,:H-o]; strm+=pad
    return strm, strm*rps[None,:]
out={}
for s in ['bear','base','bull']:
    st,rv=run(s); r12=rv[:,:12].sum(1); r24=rv.sum(1); s12=st[:,:12].sum(1)
    out[s]=dict(med12=np.median(r12),mean12=r12.mean(),p10=np.percentile(r12,10),p90=np.percentile(r12,90),
      med24=np.median(r24),p90_24=np.percentile(r24,90),s12=np.median(s12),
      p1k=(r12>1000).mean(),p500=(r12<500).mean(),p2k=(r12>2000).mean(),
      monthly=np.median(rv,axis=0).tolist())
    o=out[s]
    print(f"{s:5} yr1 med ${o['med12']:>7,.0f}  p10 ${o['p10']:>6,.0f}  p90 ${o['p90']:>7,.0f} | yr2cum ${o['med24']:>7,.0f} | streams {o['s12']:>9,.0f} | P>1k {o['p1k']:.0%} P<500 {o['p500']:.0%}")
json.dump(out,open('/tmp/out2.json','w'))
print()
for s in ['bear','base','bull']:
    print(s,'cum',[round(x) for x in np.cumsum(out[s]['monthly'])])
