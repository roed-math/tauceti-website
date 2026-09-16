(function () {
'use strict';
const offlineDocument='<!doctype html>\n'+document.documentElement.outerHTML;
const DATA=JSON.parse(document.getElementById('atlas-data').textContent);
const $=id=>document.getElementById(id);
const maps=new Map(DATA.roadmaps.map(r=>[r.id,r]));
const stages=new Map(DATA.stages.map(s=>[s.id,s]));
const presentation=TauPresentation.create(DATA);
const references=TauReferences.create(DATA);
const {stageTitle,stageSummary,isMathematicalStage,landmarkTitle}=presentation;
const mathStages=r=>r.stages.filter(id=>isMathematicalStage(id)&&!stages.get(id)?.expansion);
const allGroups=[...DATA.groups,...(DATA.opportunities?.groups||[])];
const groups=new Map(allGroups.map(g=>[g.id,g]));
const opportunities=new Map((DATA.opportunities?.areas||[]).map(a=>[a.id,a]));
const external=new Map((DATA.external||[]).map(x=>[x.id,x]));
const documents=new Map((DATA.documents||[]).map(d=>[d.id,d]));
const landmarkList=TauLandmarks.build(DATA).filter(item=>isMathematicalStage(item.stageId)&&!stages.get(item.stageId)?.expansion&&!DATA.landmarkHidden?.[item.id]);
const landmarks=new Map(landmarkList.map(item=>[item.id,item]));
const stageLandmarks=new Map();
for(const item of landmarkList){if(!stageLandmarks.has(item.stageId))stageLandmarks.set(item.stageId,[]);stageLandmarks.get(item.stageId).push(item);}
const witnesses=new Map(),relatedByPair=new Map();
for(const edge of DATA.stageEdges){const a=stages.get(edge.source),b=stages.get(edge.target);if(a&&b&&a.owner!==b.owner){const key=a.owner+'\n'+b.owner;if(!witnesses.has(key))witnesses.set(key,[]);witnesses.get(key).push(edge);}}
for(const link of DATA.roadmapLinks||[]){if(!maps.has(link.source)||!maps.has(link.target)||link.source===link.target)continue;const key=link.source+'\n'+link.target;if(!relatedByPair.has(key))relatedByPair.set(key,{source:link.source,target:link.target,kind:'reference',citations:[]});relatedByPair.get(key).citations.push(link);}
const relatedEdges=[...relatedByPair.values()];
const contextEdges=[...opportunities.values()].flatMap(a=>a.relatedRoadmaps.map(id=>({source:a.id,target:id,kind:'reference'})));
const progress=new TauProgress(DATA,DATA.progress||{});
const routeDefaults={view:'all',id:null,layer:null,selected:null,tab:'overview',outside:false,origin:'all',activity:'all',references:false,unmapped:true};
const PIN_KEY='tauceti-atlas-pins-v1';
let pins=new Set();
try { const saved=JSON.parse(localStorage.getItem(PIN_KEY)||'[]');if(Array.isArray(saved))pins=new Set(saved.filter(id=>maps.has(id))); } catch {}
let state={...routeDefaults},currentDoc=null,toastTimer;
let inspectedId=null;
const stageChildren=new Map(),childRoadmaps=new Map(),stageRefinements=new Map();
for(const s of DATA.stages)if(s.parentStageId){const target=s.expansion?stageRefinements:stageChildren;if(!target.has(s.parentStageId))target.set(s.parentStageId,[]);target.get(s.parentStageId).push(s.id);}
for(const r of DATA.roadmaps)if(r.parentRoadmapId){if(!childRoadmaps.has(r.parentRoadmapId))childRoadmaps.set(r.parentRoadmapId,[]);childRoadmaps.get(r.parentRoadmapId).push(r.id);}
const mapSearch=new Map(DATA.roadmaps.map(r=>[r.id,(shortTitle(r.title)+' '+r.title+' '+r.id+' '+r.summary+' '+r.readme).toLowerCase()]));
const stageSearch=new Map(DATA.stages.map(s=>[s.id,(stageTitle(s.id)+' '+stageSummary(s.id)+' '+s.key+' '+s.id+' '+s.description).toLowerCase()]));
const labels={planned:'Not started',in_progress:'In progress',complete:'Complete',unknown:''};
function plainExcerpt(text){return String(text||'').replace(/\$\$?([^$]+)\$\$?/g,(m,tex)=>tex.replace(/\\[a-zA-Z]+\s*/g,w=>({'\\mathbb ':'','\\operatorname ':'','\\mathrm ':'','\\to ':'→ ','\\times ':'× ','\\cdot ':'· ','\\otimes ':'⊗ ','\\oplus ':'⊕ ','\\infty ':'∞ ','\\le ':'≤ ','\\ge ':'≥ ','\\ne ':'≠ '}[w]??w.replace(/^\\/,''))).replace(/[{}]/g,'')).replace(/[*_`>#]+/g,'').replace(/\[([^\]]+)\]\([^)]*\)/g,'$1').replace(/\s+/g,' ').trim().slice(0,220);}
function el(tag,className,text){const n=document.createElement(tag);if(className)n.className=className;if(text!==undefined)n.textContent=text;return n;}
function btn(text,action,className=''){const n=el('button',className,text);n.type='button';n.addEventListener('click',action);return n;}
function clear(n){n.replaceChildren();return n;}
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3000);}
function shortTitle(s){const title=String(s||'').replace(/^Roadmap:\s*/i,'');return ({
 'Foundations, existing libraries, and proof integrity':'Mathematical foundations',
 'Reusable infrastructure for potential automorphy over CM fields':'Potential automorphy over CM fields',
 'Reusable infrastructure for torsion in arithmetic cohomology':'Torsion in arithmetic cohomology'
})[title]||title;}
function groupOf(r){return groups.get(r.group)||{label:r.group,color:'#8698a5'};}
function inCollection(r){return r&&(state.origin==='all'||(r.origin||'campaign')===state.origin);}
function permitted(r){if(!inCollection(r))return false;if(state.activity==='all')return true;if(state.activity==='pinned')return pins.has(r.id);const p=progress.roadmap(r.id);return (p[state.activity]||0)>0;}
function visibleOpportunities(){return state.unmapped&&state.origin==='all'&&['all','unmapped'].includes(state.activity)?[...opportunities.values()]:[];}
function summarize(rs){return progress.aggregate(rs.flatMap(r=>progress.roadmapLeaves(r.id)));}
function revealRoadmap(id){const r=maps.get(id);navigate({view:'roadmap',id,layer:null,selected:id,tab:'overview',activity:'all',origin:inCollection(r)?state.origin:'all'});}
function togglePin(id){if(pins.has(id))pins.delete(id);else pins.add(id);try{localStorage.setItem(PIN_KEY,JSON.stringify([...pins]));}catch{toast('Pins are kept for this session; browser storage is unavailable');}renderPins();renderInspector();if(state.activity==='pinned'){buildUniverse(true);graph.zoomToView(viewTarget(),false);}}
function renderPins(){const box=clear($('pinned-list'));if(!pins.size)return;box.append(el('div','pinned-heading','Pinned'));for(const id of pins){const r=maps.get(id);const b=btn('☆ '+shortTitle(r.title),()=>revealRoadmap(id),'pin-item');b.title=r.title;box.append(b);}}
const statusMetrics=[['complete','Complete','Recorded or locally marked'],['active','In progress','Work under way'],['planned','Planned','Explicitly not started'],['unknown','No status data','No recorded layer status']];
function collectionName(){return state.origin==='tauceti'?'Tau Ceti repository':state.origin==='campaign'?'Number theory campaign':'Combined collections';}
function renderStats(){let rs=DATA.roadmaps.filter(inCollection),scope=collectionName();if(state.view==='group'){rs=rs.filter(r=>r.group===state.id);scope=groups.get(state.id).label;}else if(['roadmap','collection'].includes(state.view)){rs=state.view==='roadmap'?[maps.get(state.id)]:(childRoadmaps.get(state.id)||[]).map(id=>maps.get(id));scope=shortTitle(maps.get(state.id).title);}else if(state.view==='neighbors'){const r=maps.get(state.id),ids=new Set([r.id,...r.prerequisites,...r.consumers]);rs=DATA.roadmaps.filter(r=>ids.has(r.id));scope='Connections of '+shortTitle(r.title);}const p=summarize(rs);
 $('stats-scope').textContent=`${scope} · ${rs.length} roadmaps · ${p.total.toLocaleString()} tracked leaf layers`;
 clear($('stats-summary'));for(const [key,label,note]of statusMetrics){const cell=el('div','metric '+key);cell.dataset.status=key;cell.append(el('strong','',p[key].toLocaleString()),el('span','',label),el('small','',note));$('stats-summary').append(cell);}
 const tc=rs.filter(r=>r.origin==='tauceti').length,campaign=rs.length-tc;$('stats-sources').textContent=`${tc} Tau Ceti roadmaps · ${campaign} campaign roadmaps · ${Object.keys(progress.export().stages).length} local layer updates`;
 const areas=clear($('area-progress'));for(const g of allGroups){const members=rs.filter(r=>r.group===g.id);if(!members.length)continue;const a=summarize(members),button=btn('',()=>{$('stats-dialog').close();navigate({view:'group',id:g.id,selected:null,activity:'all'});},'area-stat');button.dataset.group=g.id;const label=el('div','area-stat-label');label.append(el('span','area-name',g.label),el('span','area-count',`${a.complete} / ${a.total} complete`));const bar=el('div','area-bar');for(const [key]of statusMetrics){const segment=el('span',key);segment.style.width=(a.total?a[key]/a.total*100:0)+'%';bar.append(segment);}button.append(label,bar,el('span','area-stat-detail',`${members.length} roadmaps · ${a.active} active · ${a.planned} planned · ${a.unknown} without status data`));areas.append(button);}
}
function color(value){return TauGraph.progressColor(value)||'#899ba4';}
function stageProgress(p){return p.status==='unknown'?null:p.percent||0;}
function hasProgressData(p){return (p.complete||0)+(p.active||0)+(p.planned||0)>0;}
function aggregateProgress(p){return hasProgressData(p)?p.percent||0:null;}
function aggregateProgressLabel(p,suffix='layers'){return hasProgressData(p)?Math.round(p.percent||0)+'% '+suffix:'';}
function statString(p){return `${p.complete||0} / ${p.total||0} layers complete`;}
// Mathlib sits at the centre by default; #layout=areas opens the older area map, and the choice is kept in every link.
const LAYOUT=/(^|[#&])layout=areas(&|$)/.test(location.hash)?'areas':'radial';
// Where a roadmap sits: its distance from Mathlib (0-10) and why, from the classification of its references.
function placeNote(box,id){const place=DATA.roadmapClassification?.roadmaps?.[id],measured=DATA.roadmapDistances?.roadmaps?.[id];if(!place&&!measured)return;
 const fmt=v=>Number(v).toFixed(1).replace(/\.0$/,''),lines=[];
 if(measured){const range=measured.basis==='pairwise'&&Number.isFinite(measured.low)?` (${fmt(measured.low)} to ${fmt(measured.high)})`:'';
  const basis=measured.basis==='pairwise'?`from ${measured.pairwise?.judgements??0} pairwise judgements, starting from its classification score of ${fmt(measured.classification)}`:measured.basis==='children'?'the mean of its child roadmaps':measured.basis==='declarations'?'from its reviewed declaration count':'from the reference classification; pairwise judgements are pending';
  lines.push(`Distance from Mathlib ${fmt(measured.distance)} of 10${range}, ${basis}.`);
  const st=measured.structure,plural=(n,w)=>`${fmt(n)} ${w}${Number(n)===1?'':'s'}`;
  if(st)lines.push(!st.missingLayers?'Every layer it needs is recorded as built.':`Still to build: ${plural(st.missingLayers,'layer')}, ${st.suppliers?`in this roadmap and ${plural(st.suppliers,'supplier roadmap')}`:'all in this roadmap'}; the longest chain of them is ${plural(st.depth,'layer')}.`);
  const dl=st?.declarationLevel;if(dl)lines.push(`Decomposed so far: ${dl.declarations} declarations on ${dl.layersCovered} of ${dl.layers} layers, citing ${dl.sourcePages} source pages${dl.reviewed?'':' (unreviewed)'}.`);}
 else lines.push(`Distance from Mathlib ${place.distance} of 10.`);
 if(place){lines.push(`Subject class ${place.primaryMsc||'unknown'}.${place.rationale?' '+place.rationale:''}`);}
 const box2=el('div','place-note');lines.forEach(t=>box2.append(el('p','detail-note',t)));box.append(box2);}
function routeHash(s){const q=new URLSearchParams();q.set('view',s.view);if(s.id)q.set('id',s.id);if(s.layer)q.set('layer',s.layer);if(s.selected)q.set('selected',s.selected);if(s.tab!=='overview')q.set('tab',s.tab);if(s.outside)q.set('outside','1');if(s.origin!=='all')q.set('origin',s.origin);if(s.activity!=='all')q.set('activity',s.activity);if(s.references)q.set('references','1');if(!s.unmapped)q.set('unmapped','0');if(LAYOUT==='areas')q.set('layout','areas');return '#'+q.toString();}
function readRoute(){const q=new URLSearchParams(location.hash.slice(1));const next={...routeDefaults,view:q.get('view')||'all',id:q.get('id'),layer:q.get('layer'),selected:q.get('selected'),tab:q.get('tab')||'overview',outside:q.get('outside')==='1',origin:q.get('origin')||'all',activity:q.get('activity')||'all',references:q.get('references')==='1',unmapped:q.get('unmapped')!=='0'};if(next.view==='neighbors')next.view='roadmap';if(!['subjects','all','group','roadmap','collection'].includes(next.view))next.view='all';if(!['all','tauceti','campaign'].includes(next.origin))next.origin='all';if(!['all','active','complete','planned','unknown','pinned','unmapped'].includes(next.activity))next.activity='all';if(next.id&&!maps.has(next.id)&&!groups.has(next.id))next.id=null;if(!next.id&&!['subjects','all'].includes(next.view))next.view='all';if(next.view==='group'&&!groups.has(next.id))next.view='all';if(['roadmap','collection'].includes(next.view)&&!maps.has(next.id))next.view='all';if(next.selected&&!maps.has(next.selected)&&!groups.has(next.selected)&&!stages.has(next.selected)&&!external.has(next.selected)&&!landmarks.has(next.selected)&&!opportunities.has(next.selected))next.selected=null;if(next.layer&&(next.view!=='roadmap'||stages.get(next.layer)?.owner!==next.id||!isMathematicalStage(next.layer)||stages.get(next.layer)?.expansion))next.layer=null;if(next.view==='roadmap'&&landmarks.has(next.selected)&&landmarks.get(next.selected).roadmapId===next.id)next.layer=landmarks.get(next.selected).stageId;if(next.view==='roadmap'&&stages.get(next.selected)?.expansion&&stages.get(next.selected).owner===next.id)next.layer=stages.get(next.selected).parentStageId;return next;}
function navigate(change,replace=false){document.body.classList.remove('catalogue-open');$('catalogue-button').setAttribute('aria-expanded','false');state={...state,...change};if(state.view==='neighbors')state.view='roadmap';if(state.view!=='roadmap'||state.layer&&(stages.get(state.layer)?.owner!==state.id||!isMathematicalStage(state.layer)))state.layer=null;const hash=routeHash(state);if(location.hash!==hash){try{history[replace?'replaceState':'pushState'](null,'',hash);}catch{location.hash=hash;}}render();}
function select(id){state.selected=id;state.tab='overview';try{history.replaceState(null,'',routeHash(state));}catch{}renderInspector();graph.select(id);renderCatalogue();}
function openItem(id){
 if(groups.has(id)){navigate({view:'group',id,layer:null,selected:id,tab:'overview'});return;}
 if(maps.has(id)){const r=maps.get(id);navigate({view:r.stages.length?'roadmap':'collection',id,layer:null,selected:id,tab:'overview'});return;}
 if(stages.has(id))openStage(id);else if(landmarks.has(id))openLandmark(id);else if(opportunities.has(id))navigate({view:'group',id:opportunities.get(id).group,layer:null,selected:id,tab:'overview'});
}
function openStage(id){
 const s=stages.get(id);if(!s){select(id);return;}
 // A source refinement is a planet of its parent layer.
 if(s.expansion){navigate({view:'roadmap',id:s.owner,layer:s.parentStageId,selected:id,tab:'overview'});return;}
 if(!isMathematicalStage(id)){navigate({view:'roadmap',id:s.owner,layer:null,selected:id,tab:'overview'});return;}
 navigate({view:'roadmap',id:s.owner,layer:id,selected:id,tab:'overview'});
}
function openLandmark(id){const item=landmarks.get(id);if(!item)return;navigate({view:'roadmap',id:item.roadmapId,layer:item.stageId,selected:id,tab:'overview'});}
function ascend(){
 if(state.layer){navigate({view:'roadmap',id:state.id,layer:null,selected:state.id,tab:'overview'});return;}
 if(['roadmap','collection'].includes(state.view)){const r=maps.get(state.id),parent=r?.parentRoadmapId;if(parent&&maps.has(parent)){navigate({view:'collection',id:parent,layer:null,selected:parent,tab:'overview'});return;}navigate({view:'group',id:r?r.group:null,layer:null,selected:null,tab:'overview'});return;}
 navigate({view:'all',id:null,layer:null,selected:null,tab:'overview'});
}
let universe=null,universeKey='',suppressFocus=false,lastCameraTarget='';
function universeInput(){
 const roadmaps=DATA.roadmaps.filter(permitted),gaps=visibleOpportunities(),ids=new Set(roadmaps.map(r=>r.id));
 const constellations=[],starMap=new Map(),planetMap=new Map(),starEdges=[];
 for(const r of roadmaps){const p=progress.roadmap(r.id),starIds=mathStages(r);
  constellations.push({id:r.id,galaxyId:r.group,label:shortTitle(r.title),starIds,distance:DATA.roadmapDistances?.roadmaps?.[r.id]?.distance??DATA.roadmapClassification?.roadmaps?.[r.id]?.distance??null,origin:r.origin||'campaign',progress:aggregateProgress(p),progressLabel:aggregateProgressLabel(p),parentRoadmapId:r.parentRoadmapId||null});
  for(const id of starIds){const sp=progress.stage(id),parent=stages.get(id)?.parentStageId;starMap.set(id,{label:stageTitle(id),progress:stageProgress(sp),progressLabel:labels[sp.status]||'',top:!parent||!starIds.includes(parent)});
   const planets=(stageLandmarks.get(id)||[]).map(item=>({id:item.id,label:landmarkTitle(item),kind:['definition','theorem'].includes(item.kind)?item.kind:'construction',refinement:false,summary:plainExcerpt(TauPresentation.landmarkDescription(item)),moons:[]}));
   for(const rid of stageRefinements.get(id)||[]){const x=stages.get(rid).expansion,kind=x.kind;planets.push({id:rid,label:stageTitle(rid),kind:['definition','construction','theorem','lemma','comparison','application'].includes(kind)?kind:'construction',refinement:true,summary:plainExcerpt(x.statement),
    moons:[...(x.hypotheses||[]).map(t=>({kind:'hypothesis',text:t})),...(x.proofSteps||[]).map((t,i)=>({kind:'step',text:t,index:i+1})),...(x.acceptance||[]).map(t=>({kind:'check',text:t}))]});}
   // Extracted targets that share one source passage keep their names but not a repeated excerpt.
   const seen=new Map();planets.forEach(x=>seen.set(x.summary,(seen.get(x.summary)||0)+1));planets.forEach(x=>{if(!x.refinement&&seen.get(x.summary)>1)x.summary='';});
   const kinds=new Set(planets.filter(x=>!x.refinement).map(x=>x.kind));planets.forEach(x=>{x.showKind=x.refinement||kinds.size>1;});
   planetMap.set(id,planets);}
 }
 for(const area of gaps)constellations.push({id:area.id,galaxyId:area.group,label:area.title,starIds:[],unmapped:true,progress:null,progressLabel:'No dedicated roadmap'});
 for(const e of DATA.stageEdges)if(starMap.has(e.source)&&starMap.has(e.target))starEdges.push({source:e.source,target:e.target});
 const planetEdges=DATA.stageEdges.filter(e=>stages.get(e.source)?.expansion&&stages.get(e.target)?.expansion&&stages.get(e.source).parentStageId===stages.get(e.target).parentStageId).map(e=>({source:e.source,target:e.target}));
 const constellationEdges=DATA.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>({source:e.source,target:e.target,count:e.stageCount||1}));
 const present=id=>ids.has(id)||gaps.some(a=>a.id===id);
 const groupsWithProgress=allGroups.map(g=>{const p=summarize(roadmaps.filter(r=>r.group===g.id));return {...g,progress:aggregateProgress(p),progressLabel:aggregateProgressLabel(p,'layers complete')};});
 return {layout:LAYOUT,groups:groupsWithProgress,constellations,stars:starMap,planets:planetMap,starEdges,planetEdges,constellationEdges,relatedEdges:[...relatedEdges,...contextEdges].filter(e=>present(e.source)&&present(e.target))};
}
function buildUniverse(force){
 const key=[state.origin,state.activity,state.unmapped,[...pins].join(',')].join('|');
 if(!force&&universe&&universeKey===key)return false;
 const box=$('graph').getBoundingClientRect();
 universe=TauUniverse.build(universeInput(),{width:box.width||800,height:box.height||600});universeKey=key;
 graph.setUniverse(universe,{selectedId:state.selected,showReferences:state.references,keepCamera:!!force});
 $('graph-empty').hidden=universe.constellations.length>0;
 return true;
}
const graph=new TauGraph($('graph'),{
 onSelect:node=>{if(!node)return;const id=node.id;
  if(node.level==='galaxy'){navigate({view:'group',id,layer:null,selected:id,tab:'overview'});return;}
  if(node.level==='constellation'){if(node.unmapped)navigate({view:'group',id:opportunities.get(id)?.group||state.id,layer:null,selected:id,tab:'overview'});else openItem(id);return;}
  if(node.level==='star'){openStage(id);return;}
  if(landmarks.has(id))openLandmark(id);else openStage(id);
 },
 onClear:()=>{if(state.selected){state.selected=null;try{history.replaceState(null,'',routeHash(state));}catch{}renderInspector();renderCatalogue();}},
 onFocus:focus=>{
  // The camera moved by hand: keep the address bar, breadcrumbs and context
  // in step with what is in front of the reader, without travelling.
  if(suppressFocus)return;
  const next={...state};
  if(focus.level==='all'){next.view=state.view==='subjects'?'subjects':'all';next.id=null;next.layer=null;}
  else if(focus.level==='galaxy'){next.view='group';next.id=focus.id;next.layer=null;}
  else if(focus.level==='constellation'){if(!maps.has(focus.id)){next.view='group';next.id=focus.galaxyId;next.layer=null;}else{next.view=maps.get(focus.id).stages.length?'roadmap':'collection';next.id=focus.id;next.layer=null;}}
  else if(focus.level==='star'){next.view='roadmap';next.id=focus.constellationId;next.layer=focus.id;}
  if(next.view===state.view&&next.id===state.id&&next.layer===state.layer)return;
  // A hand-moved camera that is not at the full view has no target yet, so
  // returning to the whole atlas still travels there.
  state=next;lastCameraTarget=focus.level==='all'&&!graph.atOverview()?'free':JSON.stringify(viewTarget());try{history.replaceState(null,'',routeHash(state));}catch{}
  document.body.classList.toggle('is-system-view',!!state.layer);renderBreadcrumbs();renderContext();renderCatalogue();renderStats();
 },
 onAspectChange:()=>{if(universe){buildUniverse(true);graph.zoomToView(viewTarget(),false);}}
});
function viewTarget(){
 if(state.view==='roadmap'&&state.layer)return {layer:state.layer};
 if(['roadmap','group'].includes(state.view)&&state.id)return {id:state.id};
 if(state.view==='collection'&&state.id)return {ids:childRoadmaps.get(state.id)||[]};
 return {};
}
function syncGraph(animate){
 const rebuilt=buildUniverse(false),target=viewTarget(),key=JSON.stringify(target);
 if(rebuilt||key!==lastCameraTarget){lastCameraTarget=key;suppressFocus=true;graph.zoomToView(target,animate&&!rebuilt);clearTimeout(syncGraph.timer);syncGraph.timer=setTimeout(()=>{suppressFocus=false;graph.lastFocus=graph.focus();},animate&&!rebuilt?340:80);}
 graph.select(state.selected);graph.setReferences(state.references);
 renderContext();
}
function renderContext(){
 const actions=clear($('view-actions')),title=$('view-title');
 const name=state.layer?stageTitle(state.layer):state.view==='group'?groups.get(state.id)?.label:['roadmap','collection'].includes(state.view)&&maps.has(state.id)?shortTitle(maps.get(state.id).title):state.view==='subjects'?'Subjects':'All roadmaps';
 title.textContent=name||'Tau Ceti Atlas';document.title=(name&&name!=='All roadmaps'?name+' · ':'')+'Tau Ceti Atlas';
 if(!['all','subjects'].includes(state.view)){const nav=el('nav','cosmic-navigation');nav.setAttribute('aria-label','Zoom navigation');nav.append(btn(state.layer?'← Roadmap':state.view==='group'?'← Atlas':'← Area',ascend,'cosmic-back'));actions.append(nav);}
 if(['roadmap','collection'].includes(state.view)&&maps.has(state.id)&&!state.layer)actions.append(btn('Full roadmap',()=>openReader(state.id),'secondary'));
 const label=el('label','toggle links-toggle'),input=document.createElement('input');input.type='checkbox';input.checked=state.references;input.addEventListener('change',()=>navigate({references:input.checked},true));label.append(input,document.createTextNode('Show related-plan links'));actions.append(label);
 if(state.layer){$('edge-legend').innerHTML='<span class="kind-legend"><span><i class="definition"></i>Definition or construction</span><span><i class="result"></i>Result</span><span><i class="theorem"></i>Named theorem</span></span>';}else $('edge-legend').textContent=state.layer?'':state.view==='roadmap'?'Select a star to see its prerequisites and consumers':'Select an object to see its links';
 $('graph-hint').textContent=state.layer?'Click a planet to read it · zoom out to return':'Scroll or pinch to zoom · drag to pan · click to open';
}

function renderBreadcrumbs(){
 const box=clear($('breadcrumbs'));box.append(btn('Atlas',()=>navigate({view:'all',id:null,layer:null,selected:null})));
 if(state.id){box.append(el('span','','›'));
  if(maps.has(state.id)){const r=maps.get(state.id),g=groupOf(r);box.append(btn(g.label,()=>navigate({view:'group',id:r.group,layer:null,selected:null})),el('span','','›'),btn(shortTitle(r.title),()=>openItem(r.id),state.layer?'':'current'));
   if(state.layer)box.append(el('span','','›'),el('span','current',stageTitle(state.layer)));
  }else if(groups.has(state.id))box.append(btn(groups.get(state.id).label,()=>{},'current'));
 }else if(state.view==='all')box.append(el('span','','›'),el('span','current','All roadmaps'));
}
function renderCatalogue(){const box=clear($('catalogue'));const query=$('search').value.trim().toLowerCase();const rs=DATA.roadmaps.filter(permitted);if(query){const pattern=new RegExp('(^|[^\\p{L}\\p{N}])'+query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'u'),rank=title=>{const t=title.toLowerCase();return t.startsWith(query)?0:pattern.test(t)?1:t.includes(query)?2:3;};const mapHits=rs.filter(r=>mapSearch.get(r.id).includes(query)).sort((a,b)=>rank(a.title)-rank(b.title)||a.title.length-b.title.length);const stageHits=DATA.stages.filter(s=>isMathematicalStage(s.id)&&permitted(maps.get(s.owner))&&stageSearch.get(s.id).includes(query)).sort((a,b)=>rank(stageTitle(a.id))-rank(stageTitle(b.id)));box.append(el('div','catalogue-heading',`${mapHits.length} roadmaps · ${stageHits.length} stages`));for(const r of mapHits.slice(0,35)){const b=btn('',()=>openItem(r.id),'search-hit');b.append(el('strong','',shortTitle(r.title)),el('small','',groupOf(r).label));box.append(b);}for(const s of stageHits.slice(0,60)){const b=btn('',()=>openStage(s.id),'search-hit');b.append(el('strong','',stageTitle(s.id)),el('small','',s.key+' · '+shortTitle(maps.get(s.owner).title)));box.append(b);}const gapHits=visibleOpportunities().filter(a=>(a.title+' '+a.summary).toLowerCase().includes(query));for(const area of gapHits){const b=btn('',()=>navigate({view:'group',id:area.group,selected:area.id}),'search-hit');b.append(el('strong','',area.title),el('small','','No dedicated roadmap'));box.append(b);}if(!mapHits.length&&!stageHits.length&&!gapHits.length)box.append(el('p','search-empty','No matching roadmap or stage. Try a broader mathematical term.'));return;}
 const gaps=visibleOpportunities();if(gaps.length){const d=el('details','unmapped-index'),head=el('summary','','Unmapped areas · '+gaps.length);d.append(head);for(const area of gaps)d.append(btn(area.title,()=>navigate({view:'group',id:area.group,selected:area.id}),'catalogue-item'));box.append(d);}box.append(el('div','catalogue-heading','Browse the collection'));for(const g of allGroups){const members=rs.filter(r=>r.group===g.id);if(!members.length)continue;const d=document.createElement('details');d.open=state.view==='group'&&state.id===g.id||!!state.selected&&maps.has(state.selected)&&maps.get(state.selected).group===g.id;const summary=document.createElement('summary'),dot=el('span','dot');dot.style.background=g.color;summary.append(dot,el('span','label',g.label),el('small','',members.length));d.append(summary);for(const r of members){const b=btn(shortTitle(r.title),()=>openItem(r.id),'catalogue-item'+(state.selected===r.id?' active':''));b.title=r.title;d.append(b);}box.append(d);}}
function detailHeader(box,title,subtitle,accent){const strip=el('div','detail-color');strip.style.background=accent;box.append(strip,el('h2','detail-title',shortTitle(title)));if(subtitle)box.append(el('p','detail-subtitle',subtitle));}
function stats(box,items){const row=el('div','detail-stats');for(const [value,label]of items){const cell=el('div');cell.append(el('strong','',String(value)),el('span','',label));row.append(cell);}box.append(row);}
function section(box,title){box.append(el('h3','section-label',title));}
function item(box,id,action){const s=stages.get(id),r=maps.get(id),x=external.get(id);const title=s?stageTitle(s.id):r?shortTitle(r.title):x?.title||id;const b=btn('',action||(()=>s?openStage(id):r?openItem(id):select(id)),'item-link');b.dataset.itemId=id;const label=el('span');label.append(document.createTextNode(title));b.append(label,el('span','arrow','↗'));box.append(b);return b;}
function tabs(box){const nav=el('div','detail-tabs');for(const [id,title]of [['overview','Overview'],['stages','Layers'],['links','Links']])nav.append(btn(title,()=>{state.tab=id;renderInspector();},state.tab===id?'active':''));box.append(nav);}
function progressSummary(box,r){const p=progress.roadmap(r.id);if(hasProgressData(p)){const wrap=el('div','progress-summary'),top=el('div','progress-caption');top.append(el('strong','',`${Math.round(p.percent||0)}%`),el('span','',statString(p)));const bar=el('div','progress-track'),fill=el('div');fill.style.width=(p.percent||0)+'%';fill.style.background=color(p.percent||0);bar.append(fill);wrap.append(top,bar,el('p','detail-note',`${p.active||0} in progress. Progress counts all tracked leaf layers${p.unknown?', including '+p.unknown+' without status data':''}.`));box.append(wrap);}if(r.lifecycle==='completed')box.append(el('span','status-chip','Archived as complete by Tau Ceti maintainers'));}
function stageTree(box,r){
 const visible=mathStages(r),ids=new Set(visible),roots=visible.filter(id=>!ids.has(stages.get(id)?.parentStageId));
 function walk(id,parent,depth){
  const s=stages.get(id);if(!s||depth>12)return;
  const p=progress.stage(id),b=item(parent,id);if(labels[p.status]){const mark=el('span','stage-state-dot');mark.style.background=color(stageProgress(p));mark.title=labels[p.status];b.prepend(mark);}
  const children=(stageChildren.get(id)||[]).filter(isMathematicalStage);
  if(children.length){const d=el('details'),summary=el('summary','',`${children.length} further topics`),content=el('div','substage');d.append(summary,content);children.forEach(c=>walk(c,content,depth+1));parent.append(d);}
 }
 const tree=el('div','stage-tree');roots.forEach(id=>walk(id,tree,0));box.append(tree);
 const tasks=r.stages.filter(id=>!isMathematicalStage(id));
 if(tasks.length){const details=el('details','source-layer');details.append(el('summary','',`Project tasks (${tasks.length})`),el('p','detail-note','These tasks are included in tracked progress. The star map shows the mathematical topics.'));tasks.forEach(id=>item(details,id));box.append(details);}
 if(!r.stages.length)for(const id of childRoadmaps.get(r.id)||[])item(box,id,()=>openItem(id));
}
function connectionCard(box,source,target){
 const pairs=witnesses.get(source+'\n'+target)||[],other=source===state.selected?target:source;
 const card=el('details','connection-card'),summary=el('summary');
 summary.append(el('span','',shortTitle(maps.get(other).title)),el('small','',pairs.length?`${pairs.length} layer connections`:'Declared prerequisite'));
 card.append(summary);
 if(pairs.length){card.append(el('p','detail-note','These recorded layer requirements establish the direction of the link.'));
  for(const edge of pairs){const row=el('div','connection-witness');row.append(btn(stageTitle(edge.source),()=>openStage(edge.source)),el('span','', '→'),btn(stageTitle(edge.target),()=>openStage(edge.target)));card.append(row);}
 }else card.append(el('p','detail-note','The roadmap declares this dependency, but no individual layer pair is recorded.'));
 card.append(btn('Open roadmap galaxy',()=>openItem(other),'secondary'));box.append(card);
}
function renderConnections(box,r){
 box.append(btn('Show links on the map',()=>navigate({view:'roadmap',id:r.id,layer:null,selected:r.id,tab:'links'}),'secondary'));
 section(box,'Prerequisite roadmaps');const incoming=DATA.edges.filter(e=>e.target===r.id);
 if(!incoming.length)box.append(el('p','detail-note','No roadmap prerequisites are recorded in this snapshot.'));
 incoming.forEach(e=>connectionCard(box,e.source,e.target));
 section(box,'Roadmaps using this');DATA.edges.filter(e=>e.source===r.id).forEach(e=>connectionCard(box,e.source,e.target));
 const refs=relatedEdges.filter(e=>e.source===r.id||e.target===r.id),seen=new Set();
 if(refs.length){section(box,'Related reading');box.append(el('p','detail-note','Links in the source documents provide context; they do not establish prerequisites.'));
  for(const ref of refs){const other=ref.source===r.id?ref.target:ref.source;if(seen.has(other))continue;seen.add(other);const card=el('details','connection-card'),summary=el('summary','',shortTitle(maps.get(other).title));card.append(summary);
   for(const citation of ref.citations.slice(0,4))card.append(el('p','detail-note',`${citation.label} · source line ${citation.sourceLine}`));
   card.append(btn('Read linked roadmap',()=>openReader(other),'secondary'));box.append(card);}}
}
function landmarkLink(box,landmark){const button=btn('',()=>openLandmark(landmark.id),'item-link');button.append(el('span','landmark-kind',landmark.kind),el('span','',landmarkTitle(landmark)));box.append(button);}
function openReference(entry,roadmap){
 const owner=DATA.roadmaps.find(r=>r.sourcePath===entry.sourcePath)||DATA.documents?.find(d=>d.sourcePath===entry.sourcePath)||roadmap;
 openReader(owner.id);
 const searchable=text=>text.normalize('NFKC').replace(/[^\p{L}\p{N}]+/gu,'').toLowerCase();
 const needle=searchable(TauMarkdown.render(entry.text,{basePath:entry.sourcePath}).textContent).slice(0,160);
 const candidates=[...$('reader-body').querySelectorAll('p,li,tr,blockquote')].filter(node=>needle&&searchable(node.textContent).includes(needle));
 candidates.sort((a,b)=>a.textContent.length-b.textContent.length)[0]?.scrollIntoView({block:'center'});
}
function renderPlanetReferences(box,landmark,roadmap){
 const entries=references.forLandmark(landmark),panel=el('section','planet-references');
 section(panel,'References');
 const scopes=[['direct','For this topic'],['layer','For this layer'],['roadmap','Roadmap reading']];
 let count=0;
 for(const [key,title]of scopes){
  if(!entries[key].length)continue;
  const group=el('div','reference-group');group.dataset.referenceScope=key;group.append(el('h4','reference-scope',title));
  for(const entry of entries[key]){
   const citation=el('article','planet-reference'),body=el('div','md-content reference-text');
   body.append(TauMarkdown.render(entry.text,{basePath:entry.sourcePath}));
   citation.append(body);
   if(entry.works?.length){const works=el('ul','reference-works');for(const work of entry.works){const row=el('li'),link=el(work.url?'a':'span','',work.title);if(work.url){link.href=work.url;link.target='_blank';link.rel='noopener noreferrer';}if(work.authors)row.append(document.createTextNode((Array.isArray(work.authors)?work.authors.join(', '):work.authors)+' — '));row.append(link);works.append(row);}citation.append(works);}
   citation.append(btn('View citation in roadmap',()=>openReference(entry,roadmap),'reference-source'));group.append(citation);count++;
  }
  panel.append(group);
 }
 if(!count)panel.append(el('p','detail-note','No bibliography is listed for this topic in the embedded roadmap.'));
 box.append(panel);
}
function renderInspector(){const id=state.selected,changed=inspectedId!==id,box=clear($('inspector-content'));inspectedId=id;if(changed)box.scrollTop=0;$('inspector').hidden=!id;document.body.classList.toggle('has-selection',!!id);if(!id)return;
 if(opportunities.has(id)){const area=opportunities.get(id);$('selection-kind').textContent='Unmapped area';detailHeader(box,area.title,groups.get(area.group).label,'#91aabd');box.append(el('span','status-chip','No dedicated roadmap'),el('p','detail-summary',area.summary),el('p','detail-note',area.reason));section(box,'Nearby mathematical developments');area.relatedRoadmaps.forEach(r=>item(box,r,()=>openItem(r)));box.append(el('p','detail-note','These links provide mathematical context. This proposed area has no layers or completion percentage.'));return;}
 if(groups.has(id)){const g=groups.get(id),members=DATA.roadmaps.filter(r=>r.group===id&&permitted(r));$('selection-kind').textContent='Subject';detailHeader(box,g.label,`${members.length} roadmaps`,g.color);const region=DATA.regions?.groups?.[id]||g;box.append(el('p','detail-summary',region.description||`Explore the mathematics of ${g.label.toLowerCase()}.`));if(Number.isFinite(g.distance))box.append(el('p','detail-note',`Mean distance from Mathlib ${g.distance.toFixed(1)} of 10, over its roadmaps. Its direction on the map follows the subjects it is most related to.`));if(region.topics?.length){const topics=el('ul','region-topics');region.topics.forEach(topic=>topics.append(el('li','',topic)));box.append(topics);}const bridges=(region.bridgeGroups||[]).filter(gid=>groups.has(gid));if(bridges.length){section(box,'Connected areas');for(const gid of bridges)box.append(btn(groups.get(gid).label,()=>openItem(gid),'topic-link'));}box.append(btn('Open roadmaps →',()=>openItem(id),'primary'));section(box,'In this subject');members.forEach(r=>item(box,r.id,()=>openItem(r.id)));const gaps=visibleOpportunities().filter(a=>a.group===id);if(gaps.length){section(box,'Areas needing a roadmap');gaps.forEach(a=>box.append(btn(a.title,()=>select(a.id),'item-link')));}return;}
 if(maps.has(id)){const r=maps.get(id),p=progress.roadmap(id);$('selection-kind').textContent=(r.origin||'campaign')==='tauceti'?'Tau Ceti roadmap':'Campaign roadmap';detailHeader(box,r.title,groupOf(r).label,color(aggregateProgress(p)));const pin=btn(pins.has(id)?'★ Pinned':'☆ Pin roadmap',()=>togglePin(id),'pin-button');pin.setAttribute('aria-pressed',String(pins.has(id)));box.append(pin);progressSummary(box,r);const row=el('div','button-row');row.append(btn(r.stages.length?'Open stage layers →':'Open sub-roadmaps →',()=>openItem(id),'primary'),btn('Read full roadmap',()=>openReader(id),'secondary'));box.append(row);tabs(box);
 if(state.tab==='overview'){box.append(el('p','detail-summary',r.summary));placeNote(box,id);const expansion=(DATA.decompositions||[]).find(x=>x.roadmapId===id);if(expansion){section(box,'Source expansion');const covered=expansion.coverage.filter(c=>c.status!=='not_read').length;box.append(el('p','detail-note',`${expansion.nodes} reviewed refinements from ${expansion.sources.length} primary source${expansion.sources.length===1?'':'s'}; ${covered} of ${expansion.coverage.length} layers read (${expansion.status.replace('_',' ')}). Review: ${expansion.review.status}${expansion.review.reviewer?' by '+expansion.review.reviewer:''}. ${expansion.gaps.length} recorded gap${expansion.gaps.length===1?'':'s'}.`));}const tags=DATA.regions?.roadmapTags?.[id];if(tags?.length){const row=el('div','related-subjects');for(const tag of tags){const gid=typeof tag==='string'?tag:tag.group;if(groups.has(gid))row.append(btn(groups.get(gid).label,()=>openItem(gid),'topic-link'));}box.append(row);}stats(box,[[mathStages(r).length,'topics'],[r.prerequisites.length,'prerequisites'],[r.consumers.length,'consumers']]);if(r.parentRoadmapId)item(box,r.parentRoadmapId,()=>openItem(r.parentRoadmapId));if(r.statusMarkdown){section(box,'Recorded project status');box.append(el('p','detail-note','Imported from the local Tau Ceti roadmap checkout. Reports are snapshots; local changes are kept separately.'+(p.snapshotDate?' Reported '+p.snapshotDate+'.':'')),btn('Read status report',()=>openReader(id,'status'),'secondary'));}if(r.progressMarkdown)box.append(btn('Read progress log',()=>openReader(id,'progress'),'quiet'));section(box,'Starting points');mathStages(r).slice(0,4).forEach(s=>item(box,s));if((childRoadmaps.get(id)||[]).length){section(box,'Sub-roadmaps');childRoadmaps.get(id).forEach(child=>item(box,child,()=>openItem(child)));}}
 if(state.tab==='stages'){box.append(el('p','detail-note','Open a layer to read its target and update its local progress. Sub-layers can be expanded independently.'));stageTree(box,r);}
 if(state.tab==='links')renderConnections(box,r);

 return;}
 if(landmarks.has(id)){const landmark=landmarks.get(id),stage=stages.get(landmark.stageId),r=maps.get(landmark.roadmapId);$('selection-kind').textContent=landmark.kind.charAt(0).toUpperCase()+landmark.kind.slice(1)+' · planet';detailHeader(box,landmarkTitle(landmark),shortTitle(r.title),'#a8c8df');box.append(el('span','landmark-kind',landmark.kind));const text=el('div','md-content landmark-description');text.append(TauMarkdown.render(TauPresentation.landmarkDescription(landmark),{basePath:landmark.sourcePath}));box.append(text);renderPlanetReferences(box,landmark,r);section(box,'In this layer');box.append(btn(stageTitle(stage.id),()=>openStage(stage.id),'item-link'),el('p','detail-note','This is a target named in the roadmap. Progress is recorded for its parent layer.'),btn('Read full roadmap',()=>openReader(r.id),'secondary'));return;}
 if(stages.has(id)&&stages.get(id).expansion){renderRefinement(box,stages.get(id));return;}
 if(stages.has(id)){
  const s=stages.get(id),r=maps.get(s.owner),p=progress.stage(id),mathematical=isMathematicalStage(id);
  $('selection-kind').textContent=mathematical?'Layer':'Project task';
  detailHeader(box,stageTitle(id),'',color(stageProgress(p)));box.append(btn(shortTitle(r.title),()=>openItem(r.id),'inline-owner'));
  const summary=stageSummary(id);if(summary){const md=el('div','md-content stage-description');md.append(TauMarkdown.render(summary,{basePath:s.sourcePath}));box.append(md);}
  const targets=stageLandmarks.get(id)||[];
  if(targets.length){section(box,'Definitions and results');targets.forEach(target=>landmarkLink(box,target));}
  const refinements=(stageRefinements.get(id)||[]);
  if(refinements.length){section(box,'Source decomposition');box.append(el('p','detail-note','Constructions and results read from the primary sources by the expansion programme. They refine this layer and orbit it as planets; progress stays recorded on the layer.'));refinements.forEach(x=>{const b=item(box,x);b.prepend(el('span','landmark-kind',stages.get(x).expansion.kind+(stages.get(x).expansion.reviewed?'':' · added during review')));});}
  const children=(stageChildren.get(id)||[]).filter(isMathematicalStage);
  if(children.length){section(box,'Further topics');children.forEach(x=>item(box,x));}
  const requirements=s.requires.filter(isMathematicalStage),consumers=s.consumers.filter(isMathematicalStage);
  if(requirements.length){section(box,'Builds on');requirements.forEach(x=>item(box,x));}
  if(consumers.length){section(box,'Used in');consumers.forEach(x=>item(box,x));}
  if(labels[p.status])box.append(el('p','status-chip',`${p.manual?'Your local status':'Recorded status'}: ${labels[p.status]}`));renderProgressControls(box,s,p);
  const source=el('details','source-layer');source.append(el('summary','','Source layer and work plan'));
  const md=el('div','md-content source-stage-description');md.append(TauMarkdown.render(s.description,{basePath:s.sourcePath}));source.append(md);box.append(source,btn('Read full roadmap',()=>openReader(r.id),'secondary'));return;
 }
 const x=external.get(id);$('selection-kind').textContent='External prerequisite';detailHeader(box,x?.title||id,'Integration contract','#89959d');box.append(el('p','detail-summary',x?.action||'This prerequisite is outside the currently embedded roadmaps. Its exact statement and implementation must be checked in the supplying library.'));if(x?.integration_owner&&stages.has(x.integration_owner))item(box,x.integration_owner);if(x?.consumers?.length){section(box,'Consumers');x.consumers.forEach(c=>item(box,c));}}
function renderRefinement(box,s){
 const r=maps.get(s.owner),x=s.expansion,parent=stages.get(s.parentStageId),expansion=(DATA.decompositions||[]).find(d=>d.roadmapId===s.owner);
 $('selection-kind').textContent=x.kind.charAt(0).toUpperCase()+x.kind.slice(1)+' · source refinement';
 detailHeader(box,stageTitle(s.id),shortTitle(r.title),'#8fa8d0');
 if(!x.reviewed)box.append(el('span','status-chip','Added during review; not yet independently checked'));
 box.append(el('p','detail-summary',x.statement));
 const md=el('div','md-content stage-description');md.append(TauMarkdown.render(s.description.replace(/^### .*\n\n[^\n]*\n\n/,''),{basePath:s.sourcePath}));box.append(md);
 section(box,'Refines');if(parent)item(box,parent.id);
 const requirements=s.requires.filter(id=>stages.has(id)),consumers=s.consumers.filter(id=>stages.has(id));
 if(requirements.length){section(box,'Builds on');requirements.forEach(id=>item(box,id));}
 if(consumers.length){section(box,'Used in');consumers.forEach(id=>item(box,id));}
 if(expansion){section(box,'Sources read');const list=el('ul','reference-works');for(const source of x.sources){const work=expansion.sources.find(w=>w.id===source.sourceId);const row=el('li');const link=el(work?.url?'a':'span','',work?work.title:source.sourceId);if(work?.url){link.href=work.url;link.target='_blank';link.rel='noopener noreferrer';}row.append(document.createTextNode((work?.authors?work.authors+' — ':'')));row.append(link,document.createTextNode(' · '+source.locator));list.append(row);}box.append(list);}
 box.append(el('p','detail-note','Implementation status: unchecked. This refinement is planning detail from the cited proof; it does not change the recorded progress of its layer and does not claim a formalised result.'),btn('Read full roadmap',()=>openReader(r.id),'secondary'));
}
function renderProgressControls(box,s,p){const card=el('div','progress-controls');card.append(el('h3','section-label','Track this layer'));const selectEl=el('select');selectEl.setAttribute('aria-label','Layer status');for(const [value,title]of Object.entries(labels)){const o=el('option','',title);o.value=value;if(value==='unknown')o.setAttribute('aria-label','No recorded status');selectEl.append(o);}selectEl.value=p.status||'unknown';const note=el('textarea');note.rows=2;note.maxLength=4000;note.placeholder='Evidence, PR link or a note (optional)';note.setAttribute('aria-label','Progress note');note.value=p.note||'';const count=descendants(s.id).length;if(count)card.append(el('p','detail-note',`Updating this layer also updates its ${count} sub-layers.`));card.append(selectEl,note);const row=el('div','button-row');row.append(btn('Save status',()=>{progress.setStage(s.id,selectEl.value,note.value);toast('Progress saved locally');},'primary'));if(p.manual)row.append(btn('Use recorded status',()=>{progress.resetStage(s.id);toast('Restored recorded status');},'quiet'));card.append(row);if(p.basis&&!['unknown','unreported'].includes(p.basis))card.append(el('p','detail-note','Source: '+String(p.basis).replace(/_/g,' ')+(p.snapshotDate?' · '+p.snapshotDate:'')));if(p.evidence?.length){const d=el('details','progress-evidence');d.append(el('summary','','Recorded evidence'));for(const evidence of p.evidence){d.append(el('p','detail-note',typeof evidence==='string'?evidence:evidence.quote||evidence.path||JSON.stringify(evidence)));}card.append(d);}box.append(card);}
function descendants(id){const result=[];const visit=n=>{for(const c of stageChildren.get(n)||[]){if(result.includes(c))continue;result.push(c);visit(c);}};visit(id);return result;}
function render(){document.body.classList.toggle('is-system-view',!!state.layer);document.querySelector('[data-view="subjects"] small').textContent=allGroups.filter(g=>DATA.roadmaps.some(r=>r.group===g.id&&permitted(r))||visibleOpportunities().some(a=>a.group===g.id)).length;document.querySelectorAll('[data-view]').forEach(n=>n.classList.toggle('active',n.dataset.view===state.view||(state.view!=='subjects'&&n.dataset.view==='all')));$('source-filter').value=state.origin;$('activity-filter').value=state.activity;renderBreadcrumbs();renderInspector();renderCatalogue();renderPins();renderStats();syncGraph(true);}
function showDocument(doc){currentDoc=doc;$('reader-title').textContent=shortTitle(doc.title);const body=clear($('reader-body'));if(doc.summary){const synopsis=el('aside','reader-summary');synopsis.append(el('p','',doc.summary));body.append(synopsis);}body.append(TauMarkdown.render(doc.text,{basePath:doc.path}));$('open-source').href=fileURL(doc.path);clear($('reader-toc'));body.querySelectorAll('h2,h3').forEach(h=>{$('reader-toc').append(btn(h.dataset.tocLabel||h.textContent,()=>h.scrollIntoView({behavior:'smooth',block:'start'})));});if(!$('reader').open)$('reader').showModal();body.scrollTop=0;}
function openReader(id,kind='readme'){const r=maps.get(id);if(!r){const doc=documents.get(id);if(doc)showDocument({...doc,path:doc.sourcePath});return;}let text=r.readme,title=r.title,path=r.sourcePath;if(kind==='status'){text=r.statusMarkdown;title=r.title+' — status';path=r.sourcePath.replace(/README\.md$/,'STATUS.md');}if(kind==='progress'){text=r.progressMarkdown;title=r.title+' — progress log';path=r.sourcePath.replace(/README\.md$/,'PROGRESS.md');}if(text)showDocument({id,kind,text,title,path,summary:kind==='readme'?r.summary:null});}

function fileURL(path){if(!path)return'#';try{if(/^(https?:|file:)/.test(path))return new URL(path).href;if(path.startsWith('/'))return new URL(path,'file:///').href;return new URL(path,location.href).href;}catch{return'#';}}
function download(name,text,type='application/json'){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function handleDocLink(event){const a=event.target.closest('[data-doc-link]');if(!a)return;event.preventDefault();const raw=a.dataset.docLink,base=a.dataset.basePath||currentDoc?.path||'';if(raw.startsWith('#')){const id=decodeURIComponent(raw.slice(1));const target=$('reader-body').querySelector('#'+CSS.escape(id))||$('inspector-content').querySelector('#'+CSS.escape(id));if(target)target.scrollIntoView({behavior:'smooth'});return;}let url;try{url=new URL(raw,fileURL(base));}catch{return;}const path=decodeURIComponent(url.pathname),r=DATA.roadmaps.find(x=>fileURL(x.sourcePath)===url.href.split('#')[0]||fileURL(x.sourcePath.replace(/README\.md$/,'STATUS.md'))===url.href.split('#')[0]||fileURL(x.sourcePath.replace(/README\.md$/,'PROGRESS.md'))===url.href.split('#')[0]);const doc=[...documents.values()].find(d=>fileURL(d.sourcePath)===url.href.split('#')[0]);if(r||doc){if(r)openReader(r.id,path.endsWith('STATUS.md')?'status':path.endsWith('PROGRESS.md')?'progress':'readme');else openReader(doc.id);if(url.hash)setTimeout(()=>{const target=$('reader-body').querySelector('#'+CSS.escape(decodeURIComponent(url.hash.slice(1))));target?.scrollIntoView();},50);return;}if(['file:','http:','https:'].includes(url.protocol))window.open(url.href,'_blank','noopener');}
document.addEventListener('click',handleDocLink);
$('search').addEventListener('input',renderCatalogue);
document.querySelectorAll('[data-view]').forEach(n=>n.addEventListener('click',()=>navigate({view:n.dataset.view,id:null,selected:null,tab:'overview'})));
$('source-filter').addEventListener('change',e=>navigate({origin:e.target.value,view:'all',id:null,selected:null,activity:'all'}));

$('activity-filter').addEventListener('change',e=>navigate({activity:e.target.value,view:'all',id:null,selected:null,...(e.target.value==='unmapped'?{unmapped:true,origin:'all'}:{})}));
$('catalogue-button').addEventListener('click',()=>{const open=document.body.classList.toggle('catalogue-open');$('catalogue-button').setAttribute('aria-expanded',String(open));if(open)$('search').focus();});
$('stats-button').addEventListener('click',()=>{renderStats();$('stats-dialog').showModal();});$('close-stats').addEventListener('click',()=>$('stats-dialog').close());
$('download-offline').addEventListener('click',()=>download('TauCeti_Atlas.html',offlineDocument,'text/html'));
$('close-inspector').addEventListener('click',()=>{state.selected=null;try{history.replaceState(null,'',routeHash(state));}catch{}renderInspector();renderCatalogue();graph.select(null);});
$('zoom-in').addEventListener('click',()=>graph.zoomIn());$('zoom-out').addEventListener('click',()=>graph.zoomOut());$('fit-graph').addEventListener('click',()=>graph.zoomToView(viewTarget(),true));
$('export-graph').addEventListener('click',()=>download('TauCeti-'+state.view+'.svg',graph.exportSVG(),'image/svg+xml'));
$('copy-link').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);toast('View link copied');}catch{toast('Bookmark this page to save the current view');}});
$('help-button').addEventListener('click',()=>$('help').showModal());$('close-help').addEventListener('click',()=>$('help').close());$('start-exploring').addEventListener('click',()=>$('help').close());$('close-reader').addEventListener('click',()=>$('reader').close());
$('download-readme').addEventListener('click',()=>{if(currentDoc)download(currentDoc.id.replace(/[^a-z0-9_-]/gi,'_')+'.md',currentDoc.text,'text/markdown');});
$('progress-button').addEventListener('click',()=>{$('storage-status').textContent=progress.persistent?'Changes save in this browser. Export a backup before moving or replacing the HTML file.':'Browser storage is unavailable. Export your progress before closing this page.';$('progress-dialog').showModal();});
$('close-progress').addEventListener('click',()=>$('progress-dialog').close());
$('export-progress').addEventListener('click',()=>download('TauCeti-progress-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(progress.export(),null,2)));
$('import-progress').addEventListener('click',()=>$('progress-file').click());
$('progress-file').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>5000000)throw new Error('Progress file is too large.');const count=progress.import(JSON.parse(await file.text()));toast('Imported progress'+(typeof count==='number'?` for ${count} layers`:''));$('progress-dialog').close();}catch(error){toast('Could not import: '+error.message);}e.target.value='';});
window.addEventListener('popstate',()=>{state=readRoute();render();});window.addEventListener('hashchange',()=>{state=readRoute();render();});
document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault();if(matchMedia('(max-width:600px)').matches){document.body.classList.add('catalogue-open');$('catalogue-button').setAttribute('aria-expanded','true');}$('search').focus();}if(event.key==='Escape'&&!document.querySelector('dialog[open]')&&state.selected){state.selected=null;renderInspector();graph.select(null);}});
progress.subscribe(()=>{renderInspector();renderCatalogue();renderStats();if(state.activity!=='all'){buildUniverse(true);graph.zoomToView(viewTarget(),false);return;}const update={};for(const g of universe.galaxies){const p=summarize(DATA.roadmaps.filter(r=>r.group===g.id&&permitted(r)));update[g.id]={progress:aggregateProgress(p),progressLabel:aggregateProgressLabel(p,'layers complete')};}for(const c of universe.constellations)if(maps.has(c.id)){const p=progress.roadmap(c.id);update[c.id]={progress:aggregateProgress(p),progressLabel:aggregateProgressLabel(p)};}for(const s of universe.stars){const p=progress.stage(s.id);update[s.id]={progress:stageProgress(p),progressLabel:labels[p.status]||''};}graph.setProgress(update);});
$('roadmap-total').textContent=DATA.roadmaps.length.toLocaleString();$('stage-total').textContent=DATA.stages.length.toLocaleString();document.querySelector('[data-view="subjects"] small').textContent=allGroups.length;document.querySelector('[data-view="all"] small').textContent=DATA.roadmaps.length;
state=readRoute();render();window.TauExplorer={data:DATA,graph,progress,navigate,openItem,openStage,openReader,openLandmark,ascend,getState:()=>({...state}),getUniverse:()=>universe,getGraph:()=>({nodes:universe.constellations.map(c=>({id:c.id,type:c.unmapped?'unmapped':'roadmap',unmapped:!!c.unmapped,group:groups.get(c.galaxyId)?.label,progress:c.progress,progressLabel:c.progressLabel})),edges:universe.constellationEdges.map(e=>({source:e.source,target:e.target,kind:'stage_supported',stageCount:e.count}))}),landmarks:landmarkList,presentation,references,stageTitle,stageSummary,isMathematicalStage,landmarkTitle,version:'2026-09-15-universe'};
})();
