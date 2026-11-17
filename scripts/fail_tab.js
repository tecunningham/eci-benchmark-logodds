// ---- fourth tab: what frontier models still fail at (content: data/failures.json, curated by scripts/failures_curate.py) ----
// Spliced into scripts/page_template.html by build_page.py. All text comes from the JSON and is inserted as text, never as HTML.
const wEl=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e};
const wLink=(url,txt)=>{if(!/^https?:\/\//.test(url||''))return document.createTextNode(txt||'');const a=wEl('a',null,txt||url);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a};
const wHost=u=>(u||'').replace(/^https?:\/\/(www\.)?/,'').split('/')[0];
// best score of any model on a benchmark, as Epoch normalises scores for ECI
const wMax=n=>{const d=B.find(x=>x.name===n);if(!d||!d.p.length)return null;const q=d.p.reduce((a,c)=>c[2]>a[2]?c:a);return{s:q[2],m:M[q[0]].m}};
const wMaxTxt=b=>{const v=(b.eci_names||[]).map(n=>({n,x:wMax(n)})).filter(o=>o.x);if(!v.length)return'';
 return' (max '+v.map(o=>(o.x.s*100).toFixed(0)+'%'+(v.length>1?' '+short(o.n).replace('FrontierMath ',''):'')).join(', ')+')'};
function buildFail(){
 const root=document.getElementById('wbody');document.getElementById('lede').textContent='';
 if(!FAILS||!FAILS.benchmarks||!FAILS.benchmarks.length){root.textContent='No failure notes have been gathered yet.';return}
 const kids=[],card=b=>{
  const c=wEl('section','wb');c.id='w-'+b.id;
  const h=wEl('h2',null,b.title);h.append(wEl('span','wmax',wMaxTxt(b)));
  h.title=(b.eci_names||[]).map(n=>{const x=wMax(n);return x?short(n)+': best score '+(x.s*100).toFixed(0)+'% ('+x.m+')':''}).filter(Boolean).join('; ');
  const wp=wEl('p','wwhat',b.what||'');if(b.human)wp.append(' ',wEl('b',null,'Humans: '),b.human);c.append(h,wp);
  if(b.note)c.append(wEl('p','wnote',b.note));
  if(b.examples&&b.examples.length){const ul=wEl('ul','wex');b.examples.forEach(x=>{const li=wEl('li');
    li.append(wEl('span','wtask',x.task));
    if(x.fail){li.append(wEl('br'),wEl('b','wfail',x.fail+'. '));if(x.model)li.append(wEl('span','wmodel',x.model+'. '));if(x.detail)li.append(x.detail+' ')}
    else li.append(' ');
    li.append(wLink(x.url,'['+wHost(x.url)+']'));ul.append(li)});
   c.append(wEl('h3',null,b.examples.some(x=>x.fail)?'Examples':'Sample tasks (no model attempts are public)'),ul)}
  if(b.modes&&b.modes.length){const ul=wEl('ul','wmodes');b.modes.forEach(f=>{const li=wEl('li');li.append(wEl('b',null,f.label+'. '),f.desc+' ',wEl('span','wmodel',(f.about||'')+(f.date?', '+f.date:'')+' '),wLink(f.url,'['+wHost(f.url)+']'));ul.append(li)});
   c.append(wEl('h3',null,'Failure types reported'),ul)}
  return c};
 const rec=FAILS.benchmarks.filter(b=>b.modes&&b.modes.length),old=FAILS.benchmarks.filter(b=>!(b.modes&&b.modes.length));
 const jump=wEl('p','wjump');FAILS.benchmarks.forEach((b,i)=>{if(i)jump.append(' · ');const a=wEl('a',null,b.title+wMaxTxt(b));a.href='#w-'+b.id;a.onclick=e=>{e.preventDefault();document.getElementById('w-'+b.id).scrollIntoView({behavior:'smooth'})};jump.append(a)});
 kids.push(jump,wEl('h2','wgroup','Documented failures of current frontier models'),...rec.map(card));
 if(old.length)kids.push(wEl('h2','wgroup','No recent evidence on how models fail'),...old.map(card));
 const refs=wEl('div','wrefs');refs.append(wEl('h3',null,'References'));
 FAILS.benchmarks.forEach(b=>{if(!b.links||!b.links.length)return;const p=wEl('p');p.append(wEl('b',null,b.title+': '));b.links.forEach((l,i)=>{if(i)p.append(' · ');p.append(wLink(l.url,l.title))});refs.append(p)});
 kids.push(refs);root.replaceChildren(...kids);
 document.getElementById('wnotes').textContent='Compiled '+(FAILS.retrieved||'')+' from each benchmark’s documentation and public write-ups. Only evidence from the last six months is used. “Max” is the best score of any model, as Epoch normalises scores for ECI (0% = random guessing, 100% = the highest attainable score), so it can differ from the raw scores quoted in an example; hover a heading for the model. Fuller notes with verbatim quotes are in data/failures_full.json in the repository.';
}
