// Epoch's ECI fit (same model, objective and anchors as scripts/eci_fit.py), for refits in the browser.
// Levenberg-Marquardt; the Hessian's model block is diagonal (each score touches one model), so each
// step solves only the small benchmark block via a Schur complement.
//
// input: {nm, rows:[[model, bench, score]...], benches:[included bench ids], anchor, anchorDisc,
//         cap0[nm], dif0[], dis0[] (warm start, indexed by bench id), lowModel, highModel, low, high, reg, clip}
// output: {eci[nm] (NaN for models with no scores left), slope{bench: logits per ECI point}, iters, cost}
function fitECI(I){
  const sig=z=>1/(1+Math.exp(-z));
  const used=new Map(),bpos=new Map();
  const rows=I.rows.filter(r=>I.benches.includes(r[1]));
  rows.forEach(r=>{if(!used.has(r[0]))used.set(r[0],used.size)});
  if(!used.has(I.lowModel)||!used.has(I.highModel))throw new Error('both anchor models need at least one score');
  I.benches.forEach((b,k)=>bpos.set(b,k));
  const nm=used.size,nb=I.benches.length,q=2*nb-1;   // bench params: dif[0..nb), free dis (all but anchor)
  const ak=bpos.get(I.anchor);
  const zcol=k=>k===ak?-1:nb+(k<ak?k:k-1);
  const n=rows.length,mi=new Int32Array(n),bk=new Int32Array(n),y=new Float64Array(n);
  rows.forEach((r,i)=>{mi[i]=used.get(r[0]);bk[i]=bpos.get(r[1]);y[i]=Math.min(Math.max(r[2],I.clip),1-I.clip)});
  let cap=new Float64Array(nm),dif=new Float64Array(nb),dis=new Float64Array(nb);
  used.forEach((j,m)=>cap[j]=I.cap0[m]);
  I.benches.forEach((b,k)=>{dif[k]=I.dif0[b];dis[k]=I.dis0[b]});
  dis[ak]=I.anchorDisc;
  const lam=I.reg/(nm+q);
  const cost=(c,d,a)=>{let f=0;for(let i=0;i<n;i++){const r=sig(a[bk[i]]*(c[mi[i]]-d[bk[i]]))-y[i];f+=r*r}
    let p=0;for(let j=0;j<nm;j++)p+=c[j]*c[j];for(let k=0;k<nb;k++){p+=d[k]*d[k];if(k!==ak)p+=a[k]*a[k]}return f+lam*p};
  // per-model sparse coupling to bench params: model -> list of rows
  const byM=Array.from({length:nm},()=>[]);for(let i=0;i<n;i++)byM[mi[i]].push(i);
  let f=cost(cap,dif,dis),mu=1e-3,it=0;
  const Dm=new Float64Array(nm),gm=new Float64Array(nm),Hb=new Float64Array(q*q),gb=new Float64Array(q);
  const ja=new Float64Array(n),jd=new Float64Array(n),jz=new Float64Array(n),res=new Float64Array(n);
  for(;it<300;it++){
    Dm.fill(0);gm.fill(0);Hb.fill(0);gb.fill(0);
    for(let i=0;i<n;i++){const k=bk[i],a=dis[k],t=cap[mi[i]]-dif[k],s=sig(a*t),ds=s*(1-s);
      ja[i]=ds*a;jd[i]=-ds*a;jz[i]=k===ak?0:ds*t;res[i]=s-y[i];
      Dm[mi[i]]+=ja[i]*ja[i];gm[mi[i]]+=ja[i]*res[i];
      const z=zcol(k);Hb[k*q+k]+=jd[i]*jd[i];gb[k]+=jd[i]*res[i];
      if(z>=0){Hb[k*q+z]+=jd[i]*jz[i];Hb[z*q+k]+=jd[i]*jz[i];Hb[z*q+z]+=jz[i]*jz[i];gb[z]+=jz[i]*res[i]}}
    for(let j=0;j<nm;j++){Dm[j]+=lam;gm[j]+=lam*cap[j]}
    for(let k=0;k<nb;k++){Hb[k*q+k]+=lam;gb[k]+=lam*dif[k];const z=zcol(k);if(z>=0){Hb[z*q+z]+=lam;gb[z]+=lam*dis[k]}}
    let gain=0;
    while(mu<1e8){
      // Schur complement S = Hb' - B^T Dm'^-1 B, rhs = -gb + B^T Dm'^-1 gm
      const S=Float64Array.from(Hb);for(let c=0;c<q;c++)S[c*q+c]*=1+mu;
      const rhs=Float64Array.from(gb,v=>-v),Dd=new Float64Array(nm);
      for(let j=0;j<nm;j++){Dd[j]=Dm[j]*(1+mu);const R=byM[j],cols=[],vals=[];
        for(const i of R){const k=bk[i];cols.push(k);vals.push(ja[i]*jd[i]);const z=zcol(k);if(z>=0){cols.push(z);vals.push(ja[i]*jz[i])}}
        const w=1/Dd[j];
        for(let u=0;u<cols.length;u++){rhs[cols[u]]+=vals[u]*gm[j]*w;for(let v=0;v<cols.length;v++)S[cols[u]*q+cols[v]]-=vals[u]*vals[v]*w}}
      const db=chol(S,rhs,q);if(!db){mu*=4;continue}
      const nc=new Float64Array(nm),nd=new Float64Array(nb),na=Float64Array.from(dis);
      for(let j=0;j<nm;j++){let bd=0;for(const i of byM[j]){const k=bk[i];bd+=ja[i]*jd[i]*db[k];const z=zcol(k);if(z>=0)bd+=ja[i]*jz[i]*db[z]}
        nc[j]=Math.min(10,Math.max(-10,cap[j]+(-gm[j]-bd)/Dd[j]))}
      for(let k=0;k<nb;k++){nd[k]=Math.min(10,Math.max(-10,dif[k]+db[k]));const z=zcol(k);if(z>=0)na[k]=Math.min(10,Math.max(0.1,dis[k]+db[z]))}
      const fn=cost(nc,nd,na);
      if(fn<f){gain=f-fn;cap=nc;dif=nd;dis=na;f=fn;mu=Math.max(mu/3,1e-9);break}
      mu*=4;
    }
    if(gain<1e-12*f)break;
  }
  const cl=cap[used.get(I.lowModel)],ch=cap[used.get(I.highModel)];
  if(!(ch-cl>1e-12))throw new Error('anchor models do not define a scale');
  const b=(I.high-I.low)/(ch-cl),a0=I.low-b*cl;
  const eci=new Array(I.nm).fill(NaN);used.forEach((j,m)=>eci[m]=a0+b*cap[j]);
  const slope={};I.benches.forEach((bb,k)=>slope[bb]=dis[k]/b);
  return {eci,slope,iters:it,cost:f};
}
// Cholesky solve of symmetric positive-definite A x = r (A is q x q, row-major); null if not PD
function chol(A,r,q){
  const L=new Float64Array(q*q);
  for(let i=0;i<q;i++)for(let j=0;j<=i;j++){let s=A[i*q+j];for(let k=0;k<j;k++)s-=L[i*q+k]*L[j*q+k];
    if(i===j){if(!(s>0))return null;L[i*q+i]=Math.sqrt(s)}else L[i*q+j]=s/L[j*q+j]}
  const z=new Float64Array(q);for(let i=0;i<q;i++){let s=r[i];for(let k=0;k<i;k++)s-=L[i*q+k]*z[k];z[i]=s/L[i*q+i]}
  const x=new Float64Array(q);for(let i=q-1;i>=0;i--){let s=z[i];for(let k=i+1;k<q;k++)s-=L[k*q+i]*x[k];x[i]=s/L[i*q+i]}
  return x;
}
if(typeof module!=='undefined')module.exports={fitECI};
