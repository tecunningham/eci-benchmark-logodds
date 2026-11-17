// ECI-style fit with the modelling choices left open, for the "Try other fitting choices" tab.
//
//   score ~ G(slope_b * (capability_m - difficulty_b))
//
// Choices: the link G, the loss, how scores of 0/1 are clipped, the L2 penalty, one slope per benchmark or a
// common slope, and a minimum number of scores per model. Same Levenberg-Marquardt / Schur-complement scheme as
// eci_fit.js, generalised from least squares to Fisher scoring: each score contributes a half-gradient s and a
// half-curvature w on the link scale z, so least squares (s = r G', w = G'^2) is the special case.
//
// input: {nm, rows:[[model, bench, score]...], benches:[bench ids], anchor (bench id, optional), link, loss, clip, reg, common, minScores,
//         cap0[nm], dif0[], dis0[] (warm start, indexed by bench id), lowModel, highModel, low, high, ci}
// output: {eci[nm] (NaN where a model has no scores left), sd[nm] (approximate, if ci), slope{}, edi{}, sigma{} (beta loss),
//          pred(m, b) -> fitted score, inv(b, score) -> capability implied, n, nModels, nBench, iters, cost, rmse}
const FLEX_LINKS=(()=>{
 const erfc=x=>{const z=Math.abs(x),t=1/(1+0.5*z),r=t*Math.exp(-z*z-1.26551223+t*(1.00002368+t*(0.37409196+t*(0.09678418+t*(-0.18628806+t*(0.27886807+t*(-1.13520398+t*(1.48851587+t*(-0.82215223+t*0.17087277)))))))));return x>=0?r:2-r};
 const qnorm=p=>{   // Acklam's inverse normal CDF
  const a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00],
   b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01],
   c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00],
   d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00];
  if(p<0.02425){const q=Math.sqrt(-2*Math.log(p));return(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}
  if(p>1-0.02425){const q=Math.sqrt(-2*Math.log(1-p));return-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}
  const q=p-0.5,r=q*q;return(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)};
 const cl=z=>Math.max(-30,Math.min(30,z));
 return {
  logit:{label:'Logistic',g:z=>1/(1+Math.exp(-z)),dg:z=>{const s=1/(1+Math.exp(-z));return s*(1-s)},inv:p=>Math.log(p/(1-p))},
  probit:{label:'Probit (normal)',g:z=>0.5*erfc(-z/Math.SQRT2),dg:z=>Math.exp(-z*z/2)/Math.sqrt(2*Math.PI),inv:qnorm},
  cauchit:{label:'Cauchit (heavy tails)',g:z=>0.5+Math.atan(z)/Math.PI,dg:z=>1/(Math.PI*(1+z*z)),inv:p=>Math.tan(Math.PI*(p-0.5))},
  cloglog:{label:'Complementary log-log',g:z=>1-Math.exp(-Math.exp(cl(z))),dg:z=>{const e=Math.exp(cl(z));return e*Math.exp(-e)},inv:p=>Math.log(-Math.log(1-p))},
  loglog:{label:'Log-log',g:z=>Math.exp(-Math.exp(-cl(z))),dg:z=>{const e=Math.exp(-cl(z));return e*Math.exp(-e)},inv:p=>-Math.log(-Math.log(p))}
 };
})();
const flexMath=(()=>{
 const lgamma=x=>{let s=0;while(x<7){s-=Math.log(x);x++}const i=1/(x*x);return s+(x-0.5)*Math.log(x)-x+0.9189385332046727+(1/12-i*(1/360-i*(1/1260-i/1680)))/x};
 const digamma=x=>{let s=0;while(x<7){s-=1/x;x++}const i=1/(x*x);return s+Math.log(x)-0.5/x-i*(1/12-i*(1/120-i*(1/252-i/240)))};
 const trigamma=x=>{let s=0;while(x<7){s+=1/(x*x);x++}const i=1/(x*x);return s+1/x+i/2+(1/6-i*(1/30-i*(1/42-i/30)))/(x*x*x)};
 // Cholesky factor of symmetric positive-definite A (q x q, row-major); null if not PD
 const cholF=(A,q)=>{const L=new Float64Array(q*q);
  for(let i=0;i<q;i++)for(let j=0;j<=i;j++){let s=A[i*q+j];for(let k=0;k<j;k++)s-=L[i*q+k]*L[j*q+k];
   if(i===j){if(!(s>0))return null;L[i*q+i]=Math.sqrt(s)}else L[i*q+j]=s/L[j*q+j]}return L};
 const cholS=(L,r,q)=>{const z=new Float64Array(q);for(let i=0;i<q;i++){let s=r[i];for(let k=0;k<i;k++)s-=L[i*q+k]*z[k];z[i]=s/L[i*q+i]}
  const x=new Float64Array(q);for(let i=q-1;i>=0;i--){let s=z[i];for(let k=i+1;k<q;k++)s-=L[k*q+i]*x[k];x[i]=s/L[i*q+i]}return x};
 return {lgamma,digamma,trigamma,cholF,cholS};
})();
function flexFit(I){
 const {lgamma,digamma,trigamma,cholF,cholS}=flexMath;
 const L=FLEX_LINKS[I.link||'logit'],loss=I.loss||'ls',common=!!I.common,clip=I.clip??1e-3;
 const MU=1e-6,TAU_A=0.7,TAU_S=0.5,CD=30,AMIN=0.02,AMAX=30;
 const inB=new Set(I.benches);
 let rows=I.rows.filter(r=>inB.has(r[1]));
 if(I.minScores>1){const c=new Map();rows.forEach(r=>c.set(r[0],(c.get(r[0])||0)+1));rows=rows.filter(r=>c.get(r[0])>=I.minScores)}
 const used=new Map(),bpos=new Map(),cnt=new Map();
 rows.forEach(r=>{if(!used.has(r[0]))used.set(r[0],used.size);cnt.set(r[1],(cnt.get(r[1])||0)+1)});
 const benches=I.benches.filter(b=>cnt.has(b));
 if(benches.length<2)throw new Error('at least two benchmarks with scores are needed');
 if(!used.has(I.lowModel)||!used.has(I.highModel))throw new Error('both anchor models (Claude 3.5 Sonnet and GPT-5) need scores under these choices');
 benches.forEach((b,k)=>bpos.set(b,k));
 const nm=used.size,nb=benches.length;
 // the raw scale is fixed by pinning one benchmark's slope at its warm-start value: I.anchor if it is in the fit, else the most-scored one
 const ak=common?-1:bpos.has(I.anchor)?bpos.get(I.anchor):benches.reduce((a,b,k)=>cnt.get(b)>cnt.get(benches[a])?k:a,0);
 const q=common?nb:2*nb-1,zcol=k=>common||k===ak?-1:nb+(k<ak?k:k-1);
 const n=rows.length,mi=new Int32Array(n),bk=new Int32Array(n),y=new Float64Array(n),ty=new Float64Array(n),ly=new Float64Array(n);
 rows.forEach((r,i)=>{mi[i]=used.get(r[0]);bk[i]=bpos.get(r[1]);y[i]=Math.min(Math.max(r[2],clip),1-clip);ty[i]=L.inv(y[i]);ly[i]=Math.log(y[i]/(1-y[i]))});
 let cap=new Float64Array(nm),dif=new Float64Array(nb),dis=new Float64Array(nb);
 used.forEach((j,m)=>cap[j]=I.cap0[m]);
 benches.forEach((b,k)=>{dif[k]=I.dif0[b];dis[k]=common?1:I.dis0[b]});
 const lam=(I.reg??0.1)/(nm+q)+1e-9;            // the tiny floor keeps the location identified with no penalty
 const kap=new Float64Array(nb).fill(24);         // beta loss: concentration per benchmark (sigma = 0.1)
 let mLogA=0,lnMed=Math.log(0.1);
 const prior=loss==='beta'&&!common;              // beta loss: slopes shrunk towards their geometric mean, as Epoch's prior does
 const clampMu=m=>m<MU?MU:m>1-MU?1-MU:m;
 const rowCost=(z,i)=>{
  if(loss==='link'){const r=z-ty[i];return r*r}
  const m=L.g(z);
  if(loss==='ls'){const r=m-y[i];return r*r}
  const u=clampMu(m);
  if(loss==='ce')return-(y[i]*Math.log(u)+(1-y[i])*Math.log(1-u));
  const k=kap[bk[i]];return-(lgamma(k)-lgamma(u*k)-lgamma((1-u)*k)+(u*k-1)*Math.log(y[i])+((1-u)*k-1)*Math.log(1-y[i]))};
 const pen=(c,d,a)=>{let p=0;for(let j=0;j<nm;j++)p+=c[j]*c[j];for(let k=0;k<nb;k++){p+=d[k]*d[k];if(zcol(k)>=0)p+=a[k]*a[k]}p*=lam;
  if(prior)for(let k=0;k<nb;k++){const t=Math.log(a[k])-mLogA;p+=t*t/(2*TAU_A*TAU_A)}return p};
 const cost=(c,d,a)=>{let f=0;for(let i=0;i<n;i++)f+=rowCost(a[bk[i]]*(c[mi[i]]-d[bk[i]]),i);return f+pen(c,d,a)};
 const byM=Array.from({length:nm},()=>[]),byB=Array.from({length:nb},()=>[]);for(let i=0;i<n;i++){byM[mi[i]].push(i);byB[bk[i]].push(i)}
 const Dm=new Float64Array(nm),gm=new Float64Array(nm),Hb=new Float64Array(q*q),gb=new Float64Array(q);
 const ja=new Float64Array(n),jd=new Float64Array(n),jz=new Float64Array(n),res=new Float64Array(n);
 // gradient and Gauss-Newton / Fisher curvature at the current point
 function assemble(){
  Dm.fill(0);gm.fill(0);Hb.fill(0);gb.fill(0);
  for(let i=0;i<n;i++){const k=bk[i],a=dis[k],t=cap[mi[i]]-dif[k],z=a*t;let s,w;
   if(loss==='link'){s=z-ty[i];w=1}
   else{const m=L.g(z),dg=L.dg(z);
    if(loss==='ls'){s=(m-y[i])*dg;w=dg*dg}
    else{const u=clampMu(m);
     if(loss==='ce'){s=-0.5*(y[i]-u)/(u*(1-u))*dg;w=0.5*dg*dg/(u*(1-u))}
     else{const kk=kap[k];s=-0.5*kk*(ly[i]-digamma(u*kk)+digamma((1-u)*kk))*dg;w=0.5*kk*kk*(trigamma(u*kk)+trigamma((1-u)*kk))*dg*dg}}}
   const sw=Math.sqrt(w);ja[i]=sw*a;jd[i]=-sw*a;jz[i]=zcol(k)<0?0:sw*t;res[i]=sw>0?s/sw:0;
   Dm[mi[i]]+=ja[i]*ja[i];gm[mi[i]]+=ja[i]*res[i];
   const zc=zcol(k);Hb[k*q+k]+=jd[i]*jd[i];gb[k]+=jd[i]*res[i];
   if(zc>=0){Hb[k*q+zc]+=jd[i]*jz[i];Hb[zc*q+k]+=jd[i]*jz[i];Hb[zc*q+zc]+=jz[i]*jz[i];gb[zc]+=jz[i]*res[i]}}
  for(let j=0;j<nm;j++){Dm[j]+=lam;gm[j]+=lam*cap[j]}
  for(let k=0;k<nb;k++){Hb[k*q+k]+=lam;gb[k]+=lam*dif[k];const zc=zcol(k);if(zc>=0){Hb[zc*q+zc]+=lam;gb[zc]+=lam*dis[k];
   if(prior){const a=dis[k],t=Math.log(a)-mLogA;Hb[zc*q+zc]+=1/(2*TAU_A*TAU_A*a*a);gb[zc]+=t/(2*TAU_A*TAU_A*a)}}}
 }
 // Schur complement on the benchmark block: S = Hb(1+mu) - B^T Dm^-1 B
 function schur(mu){
  const S=Float64Array.from(Hb);for(let c=0;c<q;c++)S[c*q+c]*=1+mu;
  const rhs=Float64Array.from(gb,v=>-v),Dd=new Float64Array(nm);
  for(let j=0;j<nm;j++){Dd[j]=Dm[j]*(1+mu);const cols=[],vals=[];
   for(const i of byM[j]){const k=bk[i];cols.push(k);vals.push(ja[i]*jd[i]);const zc=zcol(k);if(zc>=0){cols.push(zc);vals.push(ja[i]*jz[i])}}
   const w=1/Dd[j];
   for(let u=0;u<cols.length;u++){rhs[cols[u]]+=vals[u]*gm[j]*w;for(let v=0;v<cols.length;v++)S[cols[u]*q+cols[v]]-=vals[u]*vals[v]*w}}
  return {S,rhs,Dd};
 }
 let f=cost(cap,dif,dis),mu=1e-3,iters=0;
 function lm(maxit){
  for(let it=0;it<maxit;it++,iters++){
   assemble();let gain=0;
   while(mu<1e10){
    const {S,rhs,Dd}=schur(mu),Lc=cholF(S,q);if(!Lc){mu*=4;continue}
    const db=cholS(Lc,rhs,q);
    const nc=new Float64Array(nm),nd=new Float64Array(nb),na=Float64Array.from(dis);
    for(let j=0;j<nm;j++){let bd=0;for(const i of byM[j]){const k=bk[i];bd+=ja[i]*jd[i]*db[k];const zc=zcol(k);if(zc>=0)bd+=ja[i]*jz[i]*db[zc]}
     nc[j]=Math.min(CD,Math.max(-CD,cap[j]+(-gm[j]-bd)/Dd[j]))}
    for(let k=0;k<nb;k++){nd[k]=Math.min(CD,Math.max(-CD,dif[k]+db[k]));const zc=zcol(k);if(zc>=0)na[k]=Math.min(AMAX,Math.max(AMIN,dis[k]+db[zc]))}
    const fn=cost(nc,nd,na);
    if(fn<f){gain=f-fn;cap=nc;dif=nd;dis=na;f=fn;mu=Math.max(mu/3,1e-9);break}
    mu*=4;
   }
   if(gain<1e-10*(Math.abs(f)+1))break;
  }
 }
 // beta loss: each benchmark's noise SD sigma (kappa = 1/(4 sigma^2) - 1) by a 1-D search, shrunk towards the typical sigma
 function updSigma(){
  const us=[];
  for(let k=0;k<nb;k++){const R=byB[k],mus=R.map(i=>clampMu(L.g(dis[k]*(cap[mi[i]]-dif[k]))));
   const nll=u=>{const kk=1/(4*Math.exp(2*u))-1;let s=0;R.forEach((i,j)=>{const m=mus[j];s-=lgamma(kk)-lgamma(m*kk)-lgamma((1-m)*kk)+(m*kk-1)*Math.log(y[i])+((1-m)*kk-1)*Math.log(1-y[i])});
    return s+(u-lnMed)*(u-lnMed)/(2*TAU_S*TAU_S)};
   let a=Math.log(0.005),b=Math.log(0.49);const g=0.6180339887;let c=b-g*(b-a),d=a+g*(b-a),fc=nll(c),fd=nll(d);
   for(let t=0;t<34;t++){if(fc<fd){b=d;d=c;fd=fc;c=b-g*(b-a);fc=nll(c)}else{a=c;c=d;fc=fd;d=a+g*(b-a);fd=nll(d)}}
   const u=(a+b)/2;us.push(u);kap[k]=1/(4*Math.exp(2*u))-1}
  lnMed=us.reduce((s,v)=>s+v,0)/nb;
 }
 const scale=()=>{const cl=cap[used.get(I.lowModel)],ch=cap[used.get(I.highModel)];if(!(ch-cl>1e-9))throw new Error('the anchor models do not define a scale under these choices');const b=(I.high-I.low)/(ch-cl);return{a0:I.low-b*cl,b}};
 if(loss==='beta'){
  let prev=null;
  for(let o=0;o<25;o++){
   if(prior)mLogA=dis.reduce((s,v)=>s+Math.log(v),0)/nb;
   updSigma();f=cost(cap,dif,dis);lm(o?25:60);
   const {a0,b}=scale(),e=Array.from(cap,v=>a0+b*v);
   if(prev&&e.every((v,j)=>Math.abs(v-prev[j])<0.01))break;prev=e}
 }else lm(400);
 const {a0,b}=scale();
 const eci=new Array(I.nm).fill(NaN),sd=new Array(I.nm).fill(NaN);used.forEach((j,m)=>eci[m]=a0+b*cap[j]);
 const slope={},edi={},sigma={};benches.forEach((bb,k)=>{slope[bb]=dis[k]/b;edi[bb]=a0+b*dif[k];if(loss==='beta')sigma[bb]=0.5/Math.sqrt(kap[k]+1)});
 let sse=0;for(let i=0;i<n;i++){const r=L.g(dis[bk[i]]*(cap[mi[i]]-dif[bk[i]]))-rows[i][2];sse+=r*r}
 // approximate standard errors: inverse curvature at the optimum (delta method through the 130/150 anchoring).
 // Least-squares losses scale it by the residual variance; cross-entropy by the Pearson dispersion; beta takes kappa as known.
 if(I.ci){
  assemble();const {S}=schur(0),Lc=cholF(S,q);
  if(Lc){
   let disp=0.5;const dof=Math.max(1,n-nm-q);
   if(loss==='ls'||loss==='link'){let s=0;for(let i=0;i<n;i++)s+=rowCost(dis[bk[i]]*(cap[mi[i]]-dif[bk[i]]),i);disp=s/dof}
   else if(loss==='ce'){let s=0;for(let i=0;i<n;i++){const u=clampMu(L.g(dis[bk[i]]*(cap[mi[i]]-dif[bk[i]])));s+=(y[i]-u)*(y[i]-u)/(u*(1-u))}disp=0.5*s/dof}
   // U_j = Dm^-1 B_j (sparse row); C[i][j] = delta_ij / Dm_i + U_i S^-1 U_j^T
   const Urow=j=>{const u=new Float64Array(q);for(const i of byM[j]){const k=bk[i];u[k]+=ja[i]*jd[i]/Dm[j];const zc=zcol(k);if(zc>=0)u[zc]+=ja[i]*jz[i]/Dm[j]}return u};
   const dot=(u,v)=>{let s=0;for(let c=0;c<q;c++)s+=u[c]*v[c];return s};
   const jl=used.get(I.lowModel),jh=used.get(I.highModel),ul=Urow(jl),uh=Urow(jh),vl=cholS(Lc,ul,q),vh=cholS(Lc,uh,q);
   const Cll=1/Dm[jl]+dot(ul,vl),Chh=1/Dm[jh]+dot(uh,vh),Clh=dot(ul,vh),dl=cap[jh]-cap[jl],kk=I.high-I.low;
   used.forEach((j,m)=>{if(j===jl||j===jh){sd[m]=0;return}
    const u=Urow(j),v=cholS(Lc,u,q),Cmm=1/Dm[j]+dot(u,v),Cml=dot(u,vl),Cmh=dot(u,vh);
    const g0=kk/dl,g1=kk*(cap[j]-cap[jh])/(dl*dl),g2=-kk*(cap[j]-cap[jl])/(dl*dl);
    const v2=g0*g0*Cmm+g1*g1*Cll+g2*g2*Chh+2*g0*g1*Cml+2*g0*g2*Cmh+2*g1*g2*Clh;sd[m]=Math.sqrt(Math.max(0,v2*disp))});
  }
 }
 return {eci,sd,slope,edi,sigma,iters,cost:f,n,nModels:nm,nBench:nb,rmse:Math.sqrt(sse/n),benches,
  pred:(m,bb)=>L.g(slope[bb]*(eci[m]-edi[bb])),curve:(bb,x)=>L.g(slope[bb]*(x-edi[bb])),
  inv:(bb,p)=>edi[bb]+L.inv(p)/slope[bb]};
}
if(typeof module!=='undefined')module.exports={flexFit,FLEX_LINKS};
