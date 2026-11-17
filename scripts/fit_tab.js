// ---- third tab: refit capability in the browser under other modelling choices (solver: scripts/flex_fit.js) ----
// Spliced into scripts/page_template.html by build_page.py, inside its main script, so it shares M, B, RAW, FIT, rows, css() etc.
const XCOL=['#1d64f2','#e8177d','#ff7a00','#00a86b','#8b3dff','#00b4d8'];
const XLINK={logit:'Logistic',probit:'Probit',cauchit:'Cauchit',cloglog:'Complementary log-log',loglog:'Log-log'};
const XLOSS={beta:'Beta likelihood',ls:'least squares on scores',ce:'cross-entropy',link:'least squares on the link scale'};
let XH=[],XCUR=null,xSeq=0,xBusy=false,xBench='';
const xOff=()=>B.filter(d=>!d.on).map(d=>d.k);
const xKey=()=>XK.map(k=>xc[k]).join('_')+'|'+xOff().join('.');
const xFrontier=e=>frontier(M.map((o,i)=>({d:o.d,m:o.m,e:e[i],i,shown:o.shown})).filter(o=>o.shown&&Number.isFinite(o.e)));
// growth of the frontier (straight lines between records, flat after the last) over the 12 months to the snapshot and the 12 before
function xGrowth(F){
 const t=F.map(o=>+new Date(o.d)),v=F.map(o=>o.e);
 const at=x=>{if(x<=t[0])return v[0];for(let i=1;i<t.length;i++)if(x<=t[i])return v[i-1]+(v[i]-v[i-1])*(x-t[i-1])/(t[i]-t[i-1]);return v[v.length-1]};
 const e=+new Date(RAW.snapshot),a=at(e-730*DAY),b=at(e-365*DAY),c=at(e);return{prev:b-a,last:c-b,ratio:(c-b)/(b-a)}}
const xRun=(use,cfg,ci)=>flexFit({nm:M.length,rows:use,benches:B.filter(d=>d.on).map(d=>d.k),anchor:WIN,link:cfg.link,loss:cfg.loss,common:cfg.slope==='common',
 clip:+cfg.clip,reg:+cfg.reg,minScores:+cfg.min,cap0:FIT.cap,dif0:FIT.dif,dis0:FIT.dis,lowModel:LOW,highModel:HIGH,low:FIT.low[1],high:FIT.high[1],ci});
function xLabel(h){const c=h.cfg,ex=[];
 if(c.slope==='common')ex.push('one common slope');if(c.clip!=='0.001')ex.push('0/100% held at '+(+c.clip*100)+'%');
 if(c.reg!=='0.1')ex.push(c.reg==='0'?'no penalty':'penalty '+c.reg);if(c.min!=='4')ex.push('models with '+c.min+'+ scores');
 if(h.off.length)ex.push(h.r.nBench+' of '+B.length+' benchmarks');
 return XLINK[c.link]+', '+XLOSS[c.loss]+(ex.length?' ('+ex.join('; ')+')':'')}
function xFit(){
 const t=performance.now(),r=xRun(rows,xc,true),F=xFrontier(r.eci);
 const dv=M.map((o,i)=>o.shown&&Number.isFinite(r.eci[i])?Math.abs(r.eci[i]-o.pub):NaN).filter(Number.isFinite).sort((a,b)=>a-b);
 const h={key:xKey(),cfg:{...xc},off:xOff(),r,F,g:xGrowth(F),ms:Math.round(performance.now()-t),med:dv[dv.length>>1],cv:null,id:++xSeq};
 XH=XH.filter(x=>x.key!==h.key);if(XH.length>=XCOL.length)XH.shift();
 h.col=XCOL.find(c=>!XH.some(x=>x.col===c));XH.push(h);XCUR=h}
// 5-fold hold-out: refit on four fifths of the scores, predict the rest (same folds for every choice)
function xCV(h){
 let s=0x9e3779b9;const rnd=()=>{s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
 const fold=rows.map(()=>Math.floor(rnd()*5));let sse=0,n=0;
 for(let f=0;f<5;f++){let r;try{r=xRun(rows.filter((_,i)=>fold[i]!==f),h.cfg,false)}catch(e){continue}
  rows.forEach((q,i)=>{if(fold[i]!==f||!Number.isFinite(r.eci[q[0]])||!(q[1] in r.slope))return;const d=r.pred(q[0],q[1])-q[2];sse+=d*d;n++})}
 h.cv=n?{rmse:Math.sqrt(sse/n),n}:null}
function xSelect(h){xc={...h.cfg};XK.forEach(k=>document.getElementById('x'+k).value=xc[k]);const off=new Set(h.off);B.forEach(d=>d.on=!off.has(d.k));changed()}
function buildFit(){
 const msg=document.getElementById('xmsg'),key=xKey();
 if(XCUR&&XCUR.key===key){drawFit();return}
 const hit=XH.find(x=>x.key===key);if(hit){XCUR=hit;drawFit();return}
 if(xBusy)return;xBusy=true;msg.className='';msg.textContent='Fitting…';
 setTimeout(()=>{xBusy=false;
  try{
   // first visit: also fit Epoch's earlier least-squares model, so there is something to compare with
   if(!XH.length&&(xc.loss!=='ls'||xc.link!=='logit')){const keep=xc;xc={...XDEF,loss:'ls'};try{xFit()}catch(e){}xc=keep}
   xFit();msg.className=''}
  catch(e){msg.className='err';msg.textContent='Can’t fit with these choices: '+e.message+(XCUR?' Showing the last fit that worked.':'')}
  if(xKey()!==key){buildFit();return}
  drawFit()},30)}
function drawFit(){
 const ink=css('--ink'),mut=css('--muted'),grid=css('--grid'),bg=css('--bg'),narrow=innerWidth<640,h=XCUR;
 document.getElementById('lede').textContent='';
 if(!h){document.getElementById('xtable').innerHTML='';return}
 const msg=document.getElementById('xmsg');
 if(msg.className!=='err')msg.textContent='Selected: '+xLabel(h)+'. Fitted in '+h.ms+' ms on '+h.r.n.toLocaleString()+' scores, '+h.r.nModels+' models and '+h.r.nBench+' benchmarks.';
 // comparison table
 const PF=frontier(M.filter(o=>o.shown).map(o=>({d:o.d,m:o.m,e:o.pub}))),pg=xGrowth(PF),f1=v=>Number.isFinite(v)?v.toFixed(1):'–',top=F=>F.length?F[F.length-1]:null;
 const row=(sw,name,rm,cv,g,tp,med,attr,x)=>'<tr'+attr+'><td>'+sw+'</td><td>'+name+'</td><td>'+rm+'</td><td>'+cv+'</td><td>'+f1(g.prev)+'</td><td>'+f1(g.last)+'</td><td>'+(Number.isFinite(g.ratio)?g.ratio.toFixed(2)+'×':'–')+'</td><td>'+(tp?tp.m.replace(/</g,'&lt;')+' '+tp.e.toFixed(1):'–')+'</td><td>'+med+'</td><td>'+x+'</td></tr>';
 document.getElementById('xtable').innerHTML='<thead><tr><th></th><th>Fit</th><th>In-sample RMSE<br>(score points)</th><th>Hold-out RMSE<br>(score points)</th><th>Frontier growth,<br>previous 12 months<br>(ECI points)</th><th>Frontier growth,<br>last 12 months<br>(ECI points)</th><th>Last ÷<br>previous</th><th>Top model</th><th>Median |change|<br>from published</th><th></th></tr></thead><tbody>'
  +row('<span class="sw" style="border-color:'+mut+';border-top-style:dashed"></span>','Epoch’s published ECI (Bayesian fit, posterior means)','–','–',pg,top(PF),'–','','')
  +XH.slice().reverse().map(x=>row('<span class="sw" style="border-color:'+x.col+'"></span>',xLabel(x),(x.r.rmse*100).toFixed(2),x.cv?(x.cv.rmse*100).toFixed(2):'–',x.g,top(x.F),x.med.toFixed(2),' data-x="'+x.id+'"'+(x===h?' class="cur"':''),'<button type="button" data-xrm="'+x.id+'" aria-label="Remove this fit">✕</button>')).join('')+'</tbody>';
 document.querySelectorAll('#xtable tr[data-x]').forEach(tr=>tr.onclick=e=>{const x=XH.find(v=>v.id===+tr.dataset.x);if(!x)return;
  if(e.target.dataset.xrm){XH=XH.filter(v=>v!==x);if(XCUR===x){XCUR=null;if(XH.length)xSelect(XH[XH.length-1]);else buildFit()}else drawFit();return}
  xSelect(x)});
 document.getElementById('xcv').disabled=!!h.cv;
 // frontier under each fit tried
 const lay=(yt,xt,extra)=>Object.assign({paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Public Sans, system-ui, sans-serif',color:ink,size:12},showlegend:false,hovermode:'closest',dragmode:narrow?false:'zoom',
  margin:{l:narrow?44:58,r:12,t:10,b:44},hoverlabel:{font:{family:'Public Sans, system-ui, sans-serif'}},
  xaxis:{title:xt?{text:xt,font:{color:mut,size:12}}:undefined,gridcolor:grid,zeroline:false,tickfont:{color:mut}},yaxis:{title:narrow?undefined:{text:yt,font:{color:mut,size:12}},gridcolor:grid,zeroline:false,tickfont:{color:mut}}},extra||{});
 const cfgP={responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d']};
 const tr=[];
 const sdOK=h.F.every(o=>Number.isFinite(h.r.sd[o.i]));
 if(sdOK){tr.push({x:h.F.map(o=>o.d),y:h.F.map(o=>o.e+1.645*h.r.sd[o.i]),type:'scatter',mode:'lines',line:{width:0},hoverinfo:'skip'});
  tr.push({x:h.F.map(o=>o.d),y:h.F.map(o=>o.e-1.645*h.r.sd[o.i]),type:'scatter',mode:'lines',line:{width:0},fill:'tonexty',fillcolor:css('--band'),hoverinfo:'skip'})}
 tr.push({x:PF.map(o=>o.d),y:PF.map(o=>o.e),customdata:PF.map(o=>o.m),type:'scatter',mode:'lines+markers',line:{color:mut,width:2.2,dash:'dash'},marker:{size:4,color:mut},hovertemplate:'<b>%{customdata}</b><br>Epoch’s published ECI %{y:.1f}<extra></extra>'});
 XH.forEach(x=>{const cur=x===h;tr.push({x:x.F.map(o=>o.d),y:x.F.map(o=>o.e),customdata:x.F.map(o=>[o.m,Number.isFinite(x.r.sd[o.i])&&x.r.sd[o.i]>0?' (approx. 90%: '+(o.e-1.645*x.r.sd[o.i]).toFixed(1)+' to '+(o.e+1.645*x.r.sd[o.i]).toFixed(1)+')':'']),type:'scatter',mode:'lines+markers',opacity:cur?1:0.6,
  line:{color:x.col,width:cur?3.4:1.6},marker:{size:cur?7:4,color:x.col,line:{color:bg,width:cur?1.2:0}},hovertemplate:'<b>%{customdata[0]}</b><br>'+esc(xLabel(x))+'<br>capability %{y:.1f}%{customdata[1]}<extra></extra>'})});
 Plotly.react('xplot',tr,lay('Frontier capability (ECI scale)','',{xaxis:{type:'date',range:[RAW.start,new Date(+new Date(RAW.snapshot)+40*DAY).toISOString().slice(0,10)],gridcolor:grid,zeroline:false,tickfont:{color:mut}},
  shapes:[FIT.low[1],FIT.high[1]].map(v=>({type:'line',xref:'paper',yref:'y',x0:0,x1:1,y0:v,y1:v,line:{color:ink,width:1,dash:'dot'},opacity:.6,layer:'below'}))}),cfgP);
 // change from published, by model
 const ms=M.map((o,i)=>i).filter(i=>M[i].shown&&Number.isFinite(h.r.eci[i]));
 Plotly.react('xdiff',[{x:ms.map(i=>M[i].pub),y:ms.map(i=>h.r.eci[i]-M[i].pub),customdata:ms.map(i=>[M[i].m,M[i].d,h.r.eci[i].toFixed(1)]),type:'scatter',mode:'markers',marker:{size:6,color:h.col,opacity:.7,line:{color:bg,width:.5}},
   hovertemplate:'<b>%{customdata[0]}</b> (%{customdata[1]})<br>published %{x:.1f} → this fit %{customdata[2]} (%{y:+.1f})<extra></extra>'}],
  (()=>{const near=ms.filter(i=>M[i].pub>=120),ys=near.map(i=>h.r.eci[i]-M[i].pub),lo=Math.min(0,...ys),hi=Math.max(0,...ys),pad=Math.max(0.5,(hi-lo)*0.08);
   return lay('This fit − published','Epoch’s published ECI',{xaxis:{range:[118,Math.max(...ms.map(i=>M[i].pub))+3],gridcolor:grid,zeroline:false,tickfont:{color:mut},title:{text:'Epoch’s published ECI (models below 120 are off the left edge; double-click to see all)',font:{color:mut,size:12}}},
    yaxis:{range:[lo-pad,hi+pad],gridcolor:grid,zeroline:false,tickfont:{color:mut},title:narrow?undefined:{text:'This fit − published',font:{color:mut,size:12}}},shapes:[{type:'line',xref:'paper',yref:'y',x0:0,x1:1,y0:0,y1:0,line:{color:ink,width:1.2}}]})})(),cfgP);
 // one benchmark: scores against capability under this fit, with its fitted curve
 const bs=document.getElementById('xbench');
 if(!bs.options.length){[...B].sort((a,b)=>a.name.localeCompare(b.name)).forEach(d=>{const o=document.createElement('option');o.value=d.k;o.textContent=d.name;bs.appendChild(o)});
  xBench=String((B.find(d=>d.name==='OTIS Mock AIME 2024-2025')||B[0]).k);bs.value=xBench;bs.onchange=()=>{xBench=bs.value;drawFit()}}
 const d=B[+xBench],inFit=d.k in h.r.slope,pts=d.p.filter(q=>Number.isFinite(h.r.eci[q[0]])),xs=pts.map(q=>h.r.eci[q[0]]);
 const x0=Math.min(...xs)-4,x1=Math.max(...xs)+4,gx=Array.from({length:81},(_,j)=>x0+(x1-x0)*j/80),ct=[];
 ct.push({x:gx,y:gx.map(x=>sig(CF.published.slope[d.k]*(x-CF.published.edi[d.k]))),type:'scatter',mode:'lines',line:{color:mut,width:1.6,dash:'dash'},hovertemplate:'Epoch’s published logistic: %{y:.0%} at %{x:.0f}<extra></extra>'});
 if(inFit)ct.push({x:gx,y:gx.map(x=>h.r.curve(d.k,x)),type:'scatter',mode:'lines',line:{color:h.col,width:2.6},hovertemplate:'This fit’s curve: %{y:.0%} at %{x:.0f}<extra></extra>'});
 ct.push({x:xs,y:pts.map(q=>q[2]),customdata:pts.map(q=>[M[q[0]].m,M[q[0]].d]),type:'scatter',mode:'markers',marker:{size:6,color:d.col,opacity:.75,line:{color:bg,width:.5}},hovertemplate:'<b>%{customdata[0]}</b> (%{customdata[1]})<br>'+esc(d.name)+' %{y:.1%} at capability %{x:.1f}<extra></extra>'});
 Plotly.react('xcurve',ct,lay('Score','Capability under this fit'+(inFit?'':' (benchmark not in this fit)'),{yaxis:{range:[-0.04,1.04],tickformat:'.0%',gridcolor:grid,zeroline:false,tickfont:{color:mut},title:narrow?undefined:{text:'Score',font:{color:mut,size:12}}}}),cfgP);
 document.getElementById('xintro').textContent='How much does ECI depend on how it is fitted? Choose a link function, a loss and a few other settings below, and capability is re-estimated in your browser from the same '+rows.length.toLocaleString()+' scores, on the same scale (Claude 3.5 Sonnet ≡ 130, GPT-5 ≡ 150). Each fit you try is added to the table and drawn on the chart, against Epoch’s published frontier (dashed). Click a row to return to that fit. Benchmarks can be dropped under “Benchmarks in the ECI fit” below.';
 document.getElementById('xnotes').innerHTML='<p><b>The model.</b> Every fit has the same form: a benchmark’s expected score is G(slope × (capability − difficulty)), with one capability per model and one difficulty per benchmark. The choices change G, what counts as a miss, and which scores go in. After fitting, capability is rescaled so Claude 3.5 Sonnet = 130 and GPT-5 = 150, which makes fits comparable below, between and near those two models; far above 150 the spacing depends on the curve’s shape, so that is where the choices matter most.</p>'
  +'<p><b>Link.</b> The logistic and probit are symmetric and differ little. The cauchit has heavy tails: scores approach 0% and 100% slowly, so extreme scores say less about capability. The two log-log links are asymmetric. With the complementary log-log, scores creep up from 0% and then close on 100% quickly; with the log-log they leave 0% quickly and approach 100% slowly, so a model needs much more capability to move from 90% to 99%.</p>'
  +'<p><b>Loss.</b> <i>Least squares on scores</i> is Epoch’s earlier method: every miss costs its square in score units, so a miss near 0% or 100% is cheap. <i>Beta likelihood</i> is Epoch’s current model: scores are Beta-distributed around the curve, with a noise level per benchmark that shrinks towards 0% and 100%, so misses near the ends cost more. Epoch samples the full posterior by MCMC and publishes posterior means; this page finds the single best-fitting point instead (alternating between the curve parameters and each benchmark’s noise level, with slopes and noise levels shrunk towards their typical value), which takes under a second and lands within about '+(XH.find(x=>x.cfg.loss==='beta'&&x.cfg.link==='logit'&&XK.every(k=>k==='loss'||x.cfg[k]===XDEF[k])&&!x.off.length)?.med.toFixed(1)??'0.3')+' points of the published ECI for the median model since GPT-4. <i>Cross-entropy</i> treats each score as a share of right answers, also weighting the ends more. <i>Least squares on the link scale</i> transforms each score through the inverse link (log-odds for the logistic) and fits a straight line there, so everything turns on how scores of 0% and 100% are held back from infinity.</p>'
  +'<p><b>Other settings.</b> The L2 penalty is the one in Epoch’s least-squares fit (0.1, spread over all parameters); it matters little except for models and benchmarks with few scores. A common slope makes every benchmark equally steep (a Rasch model). Requiring more scores per model drops sparsely tested models, which changes the frontier where a record was set on a handful of benchmarks.</p>'
  +'<p><b>Comparing fits.</b> In-sample RMSE is in score points for every loss, so it favours least squares on scores by construction. The hold-out check is fairer: it refits five times, each time leaving out a random fifth of the scores, and reports the error in predicting them (the same folds for every fit). Neither tells you much about the spacing of models above 150, because a held-out score near 100% barely moves whichever way the top is stretched.</p>'
  +'<p><b>Intervals.</b> The shaded band on the selected fit is an approximate 90% interval from the curvature of the loss at the best fit (a delta-method standard error, carried through the 130/150 rescaling), not a bootstrap or a posterior. It treats scores as independent and each benchmark’s noise level as known, so it is, if anything, too narrow. Epoch’s published intervals for the same models are a little wider.</p>'
  +'<p><b>Not here yet.</b> A fitted floor and ceiling per benchmark, free-form (nonparametric) curves, and a second capability dimension are on the <a href="npca.html">nonparametric page</a>, where the fits take minutes, not milliseconds. Nothing here is saved; the link records the choices, so a fit can be shared.</p>';
}
XK.forEach(k=>document.getElementById('x'+k).onchange=e=>{xc[k]=e.target.value;changed()});
document.getElementById('xclear').onclick=()=>{XH=XCUR?[XCUR]:[];drawFit()};
document.getElementById('xcv').onclick=()=>{const h=XCUR,b=document.getElementById('xcv'),msg=document.getElementById('xmsg');if(!h||h.cv)return;b.disabled=true;msg.className='';msg.textContent='Running the hold-out check (five refits)…';
 setTimeout(()=>{try{xCV(h)}catch(e){}drawFit()},30)};
