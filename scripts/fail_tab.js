// ---- fourth tab: what frontier models still fail at (content: data/failures.json, gathered from public sources) ----
// Spliced into scripts/page_template.html by build_page.py. All text comes from the JSON and is inserted as text, never as HTML.
let wSel='';
const wEl=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e};
const wLink=(url,txt)=>{if(!/^https?:\/\//.test(url||''))return document.createTextNode(txt||'');const a=wEl('a',null,txt||url);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a};
// the best-scoring of the strongest models (by ECI) on a benchmark, from Epoch's normalised scores
function wScores(names){
 const out=[];names.forEach(n=>{const d=B.find(x=>x.name===n);if(!d)return;
  const top=d.p.map(q=>({m:M[q[0]],s:q[2]})).sort((a,b)=>b.m.pub-a.m.pub).slice(0,6);out.push({name:n,top,n:d.p.length})});return out}
function buildFail(){
 const root=document.getElementById('wbody'),nav=document.getElementById('wnav');
 document.getElementById('lede').textContent='';
 if(!FAILS||!FAILS.benchmarks||!FAILS.benchmarks.length){root.textContent='No failure notes have been gathered yet.';return}
 const L=FAILS.benchmarks;if(!L.some(b=>b.id===wSel))wSel=L[0].id;
 nav.replaceChildren(...L.map(b=>{const bt=wEl('button',null,b.title);bt.type='button';bt.setAttribute('aria-pressed',b.id===wSel);bt.onclick=()=>{wSel=b.id;buildFail();saveHash()};return bt}));
 const b=L.find(x=>x.id===wSel),kids=[];
 kids.push(wEl('h2',null,b.title),wEl('p','wwhat',b.what||''));
 // scores of the strongest models
 const sc=wScores(b.eci_names||[]);
 if(sc.length){const box=wEl('div','wscores');sc.forEach(g=>{const col=wEl('div');col.append(wEl('h3',null,short(g.name)+': the six strongest models with a score'));
   g.top.forEach(t=>{const r=wEl('div','wbar');r.append(wEl('span','wn',t.m.m),(()=>{const tr=wEl('span','wt'),f=wEl('i');f.style.width=(t.s*100).toFixed(1)+'%';tr.append(f);return tr})(),wEl('span','wv',(t.s*100).toFixed(0)+'%'));col.append(r)});
   box.append(col)});
  kids.push(box,wEl('p','wsmall','Scores as Epoch normalises them for ECI: 0% is random guessing and 100% is the highest score Epoch considers attainable, so they can differ from the raw scores a benchmark reports.'))}
 if(b.top_scores&&b.top_scores.length){const p=wEl('p','wsmall');p.append('As reported: ');b.top_scores.forEach((t,i)=>{if(i)p.append('; ');p.append((t.model||'')+' '+(t.score||'')+(t.set?' ('+t.set+')':''))});kids.push(p)}
 if(b.availability){const p=wEl('p','wavail');p.append(wEl('b',null,'What is public. '),b.availability);kids.push(p)}
 // failure modes
 if(b.failure_modes&&b.failure_modes.length){kids.push(wEl('h3',null,'How models fail'));const g=wEl('div','wgrid');
  b.failure_modes.forEach(f=>{const c=wEl('div','wcard');c.append(wEl('h4',null,f.label||''),wEl('p',null,f.description||''));
   if(f.quote)c.append(wEl('blockquote',null,'“'+f.quote+'”'));
   const s=wEl('p','wsrc');s.append(f.about_model?'About: '+f.about_model+'. ':'','Source: ',wLink(f.source_url,f.source_title||f.source_url||'source'),f.source_date?' ('+f.source_date+')':'');c.append(s);g.append(c)});kids.push(g)}
 else kids.push(wEl('h3',null,'How models fail'),wEl('p','wavail','Not enough is public to say how models fail on this benchmark.'));
 // examples
 if(b.examples&&b.examples.length){kids.push(wEl('h3',null,'Example tasks'));
  b.examples.forEach(x=>{const c=wEl('div','wcard wex');
   const t=wEl('p');t.append(wEl('b',null,x.task_verbatim?'Task (quoted). ':'Task (summarised). '),x.task||'');c.append(t);
   if(x.model||x.outcome){const o=wEl('p');o.append(wEl('b',null,(x.model||'Model')+': '),x.outcome||'');c.append(o)}
   if(x.model_answer)c.append(wEl('blockquote',null,x.model_answer));
   if(x.what_went_wrong){const w=wEl('p');w.append(wEl('b',null,'What went wrong. '),x.what_went_wrong);c.append(w)}
   else c.append(wEl('p','wsrc','No model attempt at this task is public.'));
   const s=wEl('p','wsrc');const u=x.source_url||x.task_url;if(u){s.append('Source: ',wLink(u,u.replace(/^https?:\/\/(www\.)?/,'').slice(0,70)))}c.append(s);kids.push(c)})}
 if(b.links&&b.links.length){const p=wEl('p','wsmall');p.append(wEl('b',null,'More: '));b.links.forEach((l,i)=>{if(i)p.append(' · ');p.append(wLink(l.url,l.title))});kids.push(p)}
 root.replaceChildren(...kids);
 document.getElementById('wnotes').textContent='These notes were compiled on '+(FAILS.retrieved||'')+' from each benchmark’s own documentation, papers and public write-ups. Quotes are verbatim from the linked source; summaries are marked as such. Many of these benchmarks keep their tasks and model transcripts private, so where no model output is public the entry gives sample tasks and the failure types its authors report, and says which models that evidence is about. Evidence about earlier models may not describe the latest ones.';
}
