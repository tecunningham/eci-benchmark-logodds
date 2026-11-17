// ---- fourth tab: what frontier models still fail at ----
// Content: data/failures.json (benchmark notes, curated by scripts/failures_curate.py) with data/failures_rows.json
// (two failure tasks per benchmark) merged in by build_page.py. All text is inserted as text, never as HTML.
// Spliced into scripts/page_template.html by build_page.py.
const wEl=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e};
const wLink=(url,txt)=>{if(!/^https?:\/\//.test(url||''))return document.createTextNode(txt||'');const a=wEl('a',null,txt||url);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a};
const wHost=u=>(u||'').replace(/^https?:\/\/(www\.)?/,'').split('/')[0];
const wImg=(im,cls)=>{if(!im||!/^figures\/failures\/[\w.-]+$/.test(im.file||''))return null;const i=wEl('img',cls);i.src=im.file;i.alt=im.caption||'';i.loading='lazy';return i};
// best score of any model on a benchmark, as Epoch normalises scores for ECI
const wMax=n=>{const d=B.find(x=>x.name===n);if(!d||!d.p.length)return null;const q=d.p.reduce((a,c)=>c[2]>a[2]?c:a);return{s:q[2],m:M[q[0]].m}};
const wMaxTxt=b=>{const v=(b.eci_names||[]).map(n=>({n,x:wMax(n)})).filter(o=>o.x);if(!v.length)return'';
 return' (max '+v.map(o=>(o.x.s*100).toFixed(0)+'%'+(v.length>1?' '+short(o.n).replace('FrontierMath ',''):'')).join(', ')+')'};
const wOpen=new Set();
function buildFail(){
 const root=document.getElementById('wbody');document.getElementById('lede').textContent='';
 if(!FAILS||!FAILS.benchmarks||!FAILS.benchmarks.length){root.textContent='No failure notes have been gathered yet.';return}
 const cell=(label,...kids)=>{const td=wEl('td');td.dataset.l=label;td.append(...kids.filter(Boolean));return td};
 const card=b=>{
  const c=wEl('section','wb');c.id='w-'+b.id;
  const h=wEl('h2',null,b.title);h.append(wEl('span','wmax',wMaxTxt(b)));
  h.title=(b.eci_names||[]).map(n=>{const x=wMax(n);return x?short(n)+': best score '+(x.s*100).toFixed(0)+'% ('+x.m+')':''}).filter(Boolean).join('; ');
  const wp=wEl('p','wwhat',b.what||'');if(b.human)wp.append(' ',wEl('b',null,'Humans: '),b.human);c.append(h,wp);
  const rows=b.rows||[];
  if(rows.length){
   const tb=wEl('table','wt'),hd=wEl('thead'),hr=wEl('tr');['Task','Reference answer','Agent answer'].forEach(t=>hr.append(wEl('th',null,t)));hd.append(hr);const body=wEl('tbody');tb.append(hd,body);
   rows.forEach((r,j)=>{const key=b.id+'/'+j,tr=wEl('tr','wrow'),dr=wEl('tr','wdet'),dd=wEl('td');dd.colSpan=3;dr.append(dd);
    const more=wEl('button','wmore','Details');more.type='button';
    tr.append(cell('Task',wEl('span',null,r.task||''),wImg(r.image,'wthumb'),more),
     cell('Reference answer',wEl('span',null,r.reference||'Not public.'),r.reference_baseline?wEl('span','wsub',r.reference_baseline):null),
     cell('Agent answer',wEl('span','wsub',(r.agent_model||'Model not named')+(r.agent_score?' · ':'')),r.agent_score?wEl('b','wscore',r.agent_score):null,
      r.failure?wEl('b','wfail',r.failure+'.'):wEl('span','wsub wblock','Cause of failure not documented.'),wEl('span',null,r.agent_answer||'')));
    // click-through detail
    const add=(t,v)=>{if(!v)return;const p=wEl('p');p.append(wEl('b',null,t+' '),v);dd.append(p)};
    add('Task in full.',r.task_detail);add('What went wrong.',r.detail);
    if(r.quote)dd.append(wEl('blockquote',null,'“'+r.quote+'”'));
    const big=wImg(r.image,'wbig');if(big){const f=wEl('figure');f.append(big,wEl('figcaption',null,(r.image.caption||'')+(r.image.credit?' ('+r.image.credit+')':'')));dd.append(f)}
    const src=wEl('p','wsub');if(r.date)src.append(r.date+' · ');if(r.source_url)src.append('Source: ',wLink(r.source_url,wHost(r.source_url)));if(r.task_url&&r.task_url!==r.source_url)src.append(' · Task: ',wLink(r.task_url,wHost(r.task_url)));dd.append(src);
    const set=o=>{dr.hidden=!o;tr.classList.toggle('open',o);more.textContent=o?'Hide details':'Details';more.setAttribute('aria-expanded',o)};
    set(wOpen.has(key));tr.onclick=e=>{if(e.target.closest('a'))return;const o=dr.hidden;o?wOpen.add(key):wOpen.delete(key);set(o)};
    body.append(tr,dr)});
   c.append(tb)}
  else c.append(wEl('p','wnote',b.no_rows_reason||b.note||'Not enough is public to show how current models fail on this benchmark.'));
  if(b.modes&&b.modes.length){const d=wEl('details','wmodes'),ul=wEl('ul');d.append(wEl('summary',null,'Failure types its authors report ('+b.modes.length+')'),ul);
   b.modes.forEach(f=>{const li=wEl('li');li.append(wEl('b',null,f.label+'. '),f.desc+' ',wEl('span','wsub',(f.about||'')+(f.date?', '+f.date:'')+' '),wLink(f.url,'['+wHost(f.url)+']'));ul.append(li)});c.append(d)}
  return c};
 const has=b=>(b.rows||[]).length>0,rec=FAILS.benchmarks.filter(has),old=FAILS.benchmarks.filter(b=>!has(b)),kids=[];
 const jump=wEl('p','wjump');rec.concat(old).forEach((b,i)=>{if(i)jump.append(' · ');const a=wEl('a',null,b.title+wMaxTxt(b));a.href='#w-'+b.id;a.onclick=e=>{e.preventDefault();document.getElementById('w-'+b.id).scrollIntoView({behavior:'smooth'})};jump.append(a)});
 kids.push(jump,...rec.map(card));
 if(old.length)kids.push(wEl('h2','wgroup','Not enough public evidence to show a current failure'),...old.map(card));
 const refs=wEl('div','wrefs');refs.append(wEl('h3',null,'References'));
 FAILS.benchmarks.forEach(b=>{if(!b.links||!b.links.length)return;const p=wEl('p');p.append(wEl('b',null,b.title+': '));b.links.forEach((l,i)=>{if(i)p.append(' · ');p.append(wLink(l.url,l.title))});refs.append(p)});
 kids.push(refs);root.replaceChildren(...kids);
 document.getElementById('wnotes').textContent='Compiled '+(FAILS.retrieved||'')+' from each benchmark’s documentation and public write-ups, using only evidence from the last six months. Two failed tasks are shown per benchmark where a specific attempt is documented; click a row for the full task and what went wrong. “Max” is the best score of any model, as Epoch normalises scores for ECI (0% = random guessing, 100% = the highest attainable score), so it can differ from the raw scores in a row; hover a heading for the model.';
}
