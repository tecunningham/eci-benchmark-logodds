import json,matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np, pandas as pd
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.load(open(ROOT/'data'/'frontier_all.json'));B=D['b'];OUT=ROOT/'figures'/'eci_frontier_all.png'
import matplotlib.colors as mc
from matplotlib.lines import Line2D
def shade(h,t):
    c=np.array(mc.to_rgb(h)); return tuple(c+(1-c)*t if t>0 else c*(1+t))
for a in D['areas']:
    g=[d for d in B if d['area']==a]
    for k,d in enumerate(g): d['col']=shade(D['cols'][a],(k/(len(g)-1)-0.5)*0.36 if len(g)>1 else 0)
def short(n):
    for a,b in [('FrontierMath-Tiers-1-3-v2-Private','FrontierMath T1–3 v2'),('FrontierMath-Tier-4-v2-Private','FrontierMath T4 v2'),('FrontierMath-2025-02-28-Private','FrontierMath T1–3 (v1)'),('FrontierMath-Tier-4-2025-07-01-Private','FrontierMath T4 (v1)'),('OTIS Mock AIME 2024-2025','OTIS Mock AIME')]: n=n.replace(a,b)
    return n
cm=plt.get_cmap('turbo')
fig,ax=plt.subplots(figsize=(15,11),dpi=150)
fig.subplots_adjust(left=.06,right=.94,bottom=.06,top=.73)
X0,X1=pd.Timestamp('2023-02-15'),pd.Timestamp('2027-05-01'); ax.set_xlim(X0,X1); ax.set_ylim(-5,5)
items=[]
for i,d in enumerate(B):
    if not d['fr']: continue
    c=d['col']
    xs=[pd.Timestamp(p[0]) for p in d['fr']]; ys=[p[1] for p in d['fr']]
    ax.plot(xs,ys,'-o',color=c,lw=1.7,ms=3.6,mec='white',mew=.6)
    items.append(dict(t=short(d['name']),x=xs[-1],y=ys[-1],c=c))
pct=[.01,.05,.1,.25,.5,.75,.9,.95,.99]
ax.set_yticks([np.log(p/(1-p)) for p in pct]); ax.set_yticklabels([f"{p*100:g}%" for p in pct]); ax.grid(axis='y',alpha=.3)
for yr in [2024,2025,2026,2027]: ax.axvline(pd.Timestamp(f'{yr}-01-01'),color='#8a8f98',lw=1.4,alpha=.8,zorder=0)
import matplotlib.dates as mdates
ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(plt.NullFormatter()); ax.tick_params(axis='x',length=0)
for yr in [2023,2024,2025,2026]: ax.text(pd.Timestamp(f'{yr}-07-02'),-0.025,str(yr),transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=10)
ax.set_ylabel('Benchmark score of frontier-ECI models (log-odds scale)')
fig.canvas.draw(); bb=ax.get_window_extent()
lpp=10/bb.height; dpp=(X1-X0)/bb.width; g=9.5*fig.dpi/72*lpp*1.05; cw=7*0.6*fig.dpi/72
GUT=pd.Timestamp('2026-06-01'); GX=pd.Timestamp('2026-10-15')
gut=sorted([i for i in items if i['x']>=GUT],key=lambda i:i['y'])
for k,it in enumerate(gut): it['ly']=it['y'] if k==0 else max(it['y'],gut[k-1]['ly']+g)
for k in range(len(gut)-1,-1,-1):
    cap=4.9 if k==len(gut)-1 else gut[k+1]['ly']-g; gut[k]['ly']=min(gut[k]['ly'],cap)
for it in gut: it['lx']=GX
placed=[]
for it in sorted([i for i in items if i['x']<GUT],key=lambda i:(i['x'],-i['y'])):
    lx=it['x']+pd.Timedelta(days=7); w=dpp*(len(it['t'])*cw+8)
    for o in [0]+[s*k*g for k in range(1,15) for s in (1,-1)]:
        yy=it['y']+o
        if abs(yy)>4.9: continue
        if not any(lx<p[1] and lx+w>p[0] and abs(yy-p[2])<g for p in placed): break
    placed.append((lx,lx+w,yy)); it['lx'],it['ly']=lx,yy
for it in items:
    ax.annotate(it['t'],xy=(it['x'],it['y']),xytext=(it['lx'],it['ly']),fontsize=7,color=it['c'],va='center',ha='left',fontweight='bold',bbox=dict(boxstyle='square,pad=0.08',fc='white',ec='none',alpha=.8),
        arrowprops=dict(arrowstyle='-',lw=.5,color=it['c'],shrinkA=0,shrinkB=2) if (abs(it['ly']-it['y'])>1e-6 or it['lx']==GX) else None)
E=D['eci']; mg=10.5*fig.dpi/72*1.15
px=[(pd.Timestamp(e[0])-X0)/(X1-X0)*bb.width for e in E]; lxs=[]
for k,v in enumerate(px): lxs.append(v if k==0 else max(v,lxs[-1]+mg))
for k in range(len(lxs)-1,-1,-1):
    cap=bb.width-4 if k==len(lxs)-1 else lxs[k+1]-mg; lxs[k]=min(lxs[k],cap)
for e,v,l in zip(E,px,lxs):
    xd=pd.Timestamp(e[0]); ax.axvline(xd,color='k',lw=.7,ls=(0,(1,2.5)),alpha=.35,zorder=0)
    ax.annotate(f"{e[1]} ({e[2]:.1f})",xy=(xd,1),xycoords=('data','axes fraction'),xytext=(l-v,16),textcoords='offset pixels',rotation=90,ha='center',va='bottom',fontsize=7.5,
        arrowprops=dict(arrowstyle='-',lw=.5,color='gray',shrinkA=0,shrinkB=0))
ax.legend(handles=[Line2D([0],[0],color=D['cols'][a],lw=3,label=a) for a in D['areas']],loc='lower right',fontsize=8,frameon=True,framealpha=.9,title='Benchmark area',title_fontsize=8)
a2=ax.twinx(); x=[pd.Timestamp(e[0]) for e in E]+[pd.Timestamp('2026-10-06')]
y=[e[2] for e in E]; y=y+[y[-1]]
lo=[e[3] if e[3] is not None else e[2] for e in E]; hi=[e[4] if e[4] is not None else e[2] for e in E]
a2.fill_between(x,lo+[lo[-1]],hi+[hi[-1]],step='post',color='k',alpha=.1,lw=0)
import matplotlib.patheffects as pe
a2.step(x,y,where='post',color='k',lw=3,path_effects=[pe.Stroke(linewidth=7,foreground='white'),pe.Normal()]); a2.plot(x[:-1],y[:-1],'kD',ms=5,mec='white',mew=1)
span=10/0.106875; a2.set_ylim(140-span/2,140+span/2); a2.set_ylabel('Frontier ECI (black)')
fig.suptitle('Frontier ECI (black, right) and benchmark scores of the 22 models that set it from GPT-4 on (colour by area, left, log-odds)\nFrontier models named along the top with their ECI; right axis slope-matched to median benchmark; solid verticals = year starts, dotted = frontier model releases',fontsize=11,y=.99)
fig.text(0.01,0.005,'Data: Epoch AI processed_data_for_eci.csv + eci_scores.csv (benchmark_data.zip, 1 Oct 2026 snapshot); 0/1 scores pinned to 1%/99%; shaded = 90% CI. CC BY 4.0',fontsize=7.5,color='gray')
fig.savefig(OUT)
