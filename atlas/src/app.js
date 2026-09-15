(function () {
'use strict';
const offlineDocument='<!doctype html>\n'+document.documentElement.outerHTML;
const DATA=JSON.parse(document.getElementById('atlas-data').textContent);
const $=id=>document.getElementById(id);
const maps=new Map(DATA.roadmaps.map(r=>[r.id,r]));
const stages=new Map(DATA.stages.map(s=>[s.id,s]));
const presentation=TauPresentation.create(DATA);
const {stageTitle,stageSummary,isMathematicalStage}=presentation;
const mathStages=r=>r.stages.filter(isMathematicalStage);
const allGroups=[...DATA.groups,...(DATA.opportunities?.groups||[])];
const groups=new Map(allGroups.map(g=>[g.id,g]));
const opportunities=new Map((DATA.opportunities?.areas||[]).map(a=>[a.id,a]));
const external=new Map((DATA.external||[]).map(x=>[x.id,x]));
const documents=new Map((DATA.documents||[]).map(d=>[d.id,d]));
const landmarkList=TauLandmarks.build(DATA).filter(item=>isMathematicalStage(item.stageId));
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
let state={...routeDefaults},currentDoc=null,graphModel={nodes:[],edges:[]},toastTimer,flightTimer;
const journeyHistory=[];
let inspectedId=null;
const stageChildren=new Map(),childRoadmaps=new Map();
for(const s of DATA.stages)if(s.parentStageId){if(!stageChildren.has(s.parentStageId))stageChildren.set(s.parentStageId,[]);stageChildren.get(s.parentStageId).push(s.id);}
for(const r of DATA.roadmaps)if(r.parentRoadmapId){if(!childRoadmaps.has(r.parentRoadmapId))childRoadmaps.set(r.parentRoadmapId,[]);childRoadmaps.get(r.parentRoadmapId).push(r.id);}
const mapSearch=new Map(DATA.roadmaps.map(r=>[r.id,(shortTitle(r.title)+' '+r.title+' '+r.id+' '+r.summary+' '+r.readme).toLowerCase()]));
const stageSearch=new Map(DATA.stages.map(s=>[s.id,(stageTitle(s.id)+' '+stageSummary(s.id)+' '+s.key+' '+s.id+' '+s.description).toLowerCase()]));
const labels={planned:'Not started',in_progress:'In progress',complete:'Complete',unknown:'Not assessed'};
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
function opportunityNode(area){return {id:area.id,label:area.title,type:'unmapped',unmapped:true,groupId:area.group,group:groups.get(area.group).label,progress:null,progressLabel:'No dedicated roadmap',color:'#9daebe',subtitle:'Unmapped area'};}
function summarize(rs){return progress.aggregate(rs.flatMap(r=>progress.roadmapLeaves(r.id)));}
function revealRoadmap(id){const r=maps.get(id);navigate({view:'group',id:r.group,selected:id,tab:'overview',activity:'all',origin:inCollection(r)?state.origin:'all'});graph.focus(id);}
function togglePin(id){if(pins.has(id))pins.delete(id);else pins.add(id);try{localStorage.setItem(PIN_KEY,JSON.stringify([...pins]));}catch{toast('Pins are kept for this session; browser storage is unavailable');}renderPins();renderInspector();if(state.activity==='pinned')buildGraph();}
function renderPins(){const box=clear($('pinned-list'));if(!pins.size)return;box.append(el('div','pinned-heading','Pinned for your next visit'));for(const id of pins){const r=maps.get(id);const b=btn('☆ '+shortTitle(r.title),()=>revealRoadmap(id),'pin-item');b.title=r.title;box.append(b);}}
const statusMetrics=[['complete','Complete','Recorded or locally marked'],['active','In progress','Work under way'],['planned','Planned','Explicitly not started'],['unknown','Unassessed','No recorded layer status']];
function collectionName(){return state.origin==='tauceti'?'Tau Ceti repository':state.origin==='campaign'?'Number theory campaign':'Combined collections';}
function renderStats(){let rs=DATA.roadmaps.filter(inCollection),scope=collectionName();if(state.view==='group'){rs=rs.filter(r=>r.group===state.id);scope=groups.get(state.id).label;}else if(['roadmap','collection'].includes(state.view)){rs=state.view==='roadmap'?[maps.get(state.id)]:(childRoadmaps.get(state.id)||[]).map(id=>maps.get(id));scope=shortTitle(maps.get(state.id).title);}else if(state.view==='neighbors'){const r=maps.get(state.id),ids=new Set([r.id,...r.prerequisites,...r.consumers]);rs=DATA.roadmaps.filter(r=>ids.has(r.id));scope='Connections of '+shortTitle(r.title);}const p=summarize(rs);clear($('landscape-stats'));for(const [key,label,note]of statusMetrics){const b=btn('',()=>$('stats-dialog').showModal());b.dataset.status=key;b.title=`${scope}: ${note.toLowerCase()}. Open the progress breakdown`;b.append(el('strong','',p[key].toLocaleString()),el('span','',label+' layers'));$('landscape-stats').append(b);}
 $('stats-scope').textContent=`${scope} · ${rs.length} roadmaps · ${p.total.toLocaleString()} tracked leaf layers`;
 clear($('stats-summary'));for(const [key,label,note]of statusMetrics){const cell=el('div','metric '+key);cell.dataset.status=key;cell.append(el('strong','',p[key].toLocaleString()),el('span','',label),el('small','',note));$('stats-summary').append(cell);}
 const tc=rs.filter(r=>r.origin==='tauceti').length,campaign=rs.length-tc;$('stats-sources').textContent=`${tc} Tau Ceti roadmaps · ${campaign} campaign roadmaps · ${Object.keys(progress.export().stages).length} local layer updates`;
 const areas=clear($('area-progress'));for(const g of allGroups){const members=rs.filter(r=>r.group===g.id);if(!members.length)continue;const a=summarize(members),button=btn('',()=>{$('stats-dialog').close();navigate({view:'group',id:g.id,selected:null,activity:'all'});},'area-stat');button.dataset.group=g.id;const label=el('div','area-stat-label');label.append(el('span','area-name',g.label),el('span','area-count',`${a.complete} / ${a.total} complete`));const bar=el('div','area-bar');for(const [key]of statusMetrics){const segment=el('span',key);segment.style.width=(a.total?a[key]/a.total*100:0)+'%';bar.append(segment);}button.append(label,bar,el('span','area-stat-detail',`${members.length} roadmaps · ${a.active} active · ${a.planned} planned · ${a.unknown} unassessed`));areas.append(button);}
}
function color(value){return TauGraph.progressColor(value)||'#899ba4';}
function statString(p){return `${p.complete||0} / ${p.total||0} layers complete`;}
function routeHash(s){const q=new URLSearchParams();q.set('view',s.view);if(s.id)q.set('id',s.id);if(s.layer)q.set('layer',s.layer);if(s.selected)q.set('selected',s.selected);if(s.tab!=='overview')q.set('tab',s.tab);if(s.outside)q.set('outside','1');if(s.origin!=='all')q.set('origin',s.origin);if(s.activity!=='all')q.set('activity',s.activity);if(s.references)q.set('references','1');if(!s.unmapped)q.set('unmapped','0');return '#'+q.toString();}
function readRoute(){const q=new URLSearchParams(location.hash.slice(1));const next={...routeDefaults,view:q.get('view')||'all',id:q.get('id'),layer:q.get('layer'),selected:q.get('selected'),tab:q.get('tab')||'overview',outside:q.get('outside')==='1',origin:q.get('origin')||'all',activity:q.get('activity')||'all',references:q.get('references')==='1',unmapped:q.get('unmapped')!=='0'};if(!['subjects','all','group','roadmap','collection','neighbors'].includes(next.view))next.view='subjects';if(!['all','tauceti','campaign'].includes(next.origin))next.origin='all';if(!['all','active','complete','planned','unknown','pinned','unmapped'].includes(next.activity))next.activity='all';if(next.id&&!maps.has(next.id)&&!groups.has(next.id))next.id=null;if(!next.id&&!['subjects','all'].includes(next.view))next.view='subjects';if(next.selected&&!maps.has(next.selected)&&!groups.has(next.selected)&&!stages.has(next.selected)&&!external.has(next.selected)&&!landmarks.has(next.selected)&&!opportunities.has(next.selected))next.selected=null;if(next.layer&&(next.view!=='roadmap'||stages.get(next.layer)?.owner!==next.id||!isMathematicalStage(next.layer)))next.layer=null;if(next.view==='roadmap'&&landmarks.has(next.selected)&&landmarks.get(next.selected).roadmapId===next.id)next.layer=landmarks.get(next.selected).stageId;return next;}
function navigate(change,replace=false){clearTimeout(flightTimer);document.querySelector('.graph-shell').classList.remove('is-entering');document.body.classList.remove('catalogue-open');$('catalogue-button').setAttribute('aria-expanded','false');state={...state,...change};if(state.view!=='roadmap'||state.layer&&(stages.get(state.layer)?.owner!==state.id||!isMathematicalStage(state.layer)))state.layer=null;const hash=routeHash(state);if(location.hash!==hash){try{history[replace?'replaceState':'pushState'](null,'',hash);}catch{location.hash=hash;}}render();}
function select(id){state.selected=id;state.tab='overview';try{history.replaceState(null,'',routeHash(state));}catch{}renderInspector();graph.select(id);renderCatalogue();}
function rememberJourney(node,camera) {
 if((maps.has(node.id)&&state.id!==node.id)||(stages.has(node.id)&&state.layer!==node.id)){
  journeyHistory.push({target:node.id,route:{...state},camera:camera||graph.captureCamera?.()});
  if(journeyHistory.length>20)journeyHistory.shift();
 }
}
function arrive() {
 const shell=document.querySelector('.graph-shell');
 shell.classList.remove('is-travelling','scene-arriving');
 void shell.offsetWidth;
 shell.classList.add('scene-arriving');
 clearTimeout(flightTimer);flightTimer=setTimeout(()=>shell.classList.remove('scene-arriving'),650);
}
function openItem(id,remember=true){
 if(groups.has(id)){navigate({view:'group',id,layer:null,selected:null,tab:'overview'});return;}
 if(maps.has(id)){if(remember)rememberJourney({id});const r=maps.get(id);navigate({view:r.stages.length?'roadmap':'collection',id,layer:null,selected:id,tab:'overview'});return;}
 if(stages.has(id))openStage(id,remember);else if(landmarks.has(id))openLandmark(id);else if(opportunities.has(id)){select(id);graph.focus(id);}
}
function openStage(id,remember=true){
 const s=stages.get(id);if(!s){select(id);return;}
 if(!isMathematicalStage(id)){navigate({view:'roadmap',id:s.owner,layer:null,selected:id,tab:'overview'});return;}
 if(remember)rememberJourney({id});
 navigate({view:'roadmap',id:s.owner,layer:id,selected:id,tab:'overview'});
}
function ascend(){
 if(!['roadmap','collection'].includes(state.view))return;
 const target=state.layer||state.id;
 let index=journeyHistory.length-1;while(index>=0&&journeyHistory[index].target!==target)index--;
 if(index>=0){const parent=journeyHistory[index];journeyHistory.splice(index);navigate(parent.route);if(parent.camera)graph.restoreCamera?.(parent.camera);}
 else if(state.layer)openItem(state.id,false);
 else if(maps.get(state.id)?.parentRoadmapId)openItem(maps.get(state.id).parentRoadmapId,false);
 else navigate({view:'all',id:null,layer:null,selected:null,tab:'overview'});
 arrive();
}
const graph=new TauGraph($('graph'),{
 onSelect:n=>{if(maps.has(n.id))enterGalaxy(n.id);else if(stages.has(n.id)&&!state.layer&&n.type==='stage')enterStar(n.id);else select(n.id);},
 onOpen:n=>openItem(n.id),
 onDive:n=>{openItem(n.id,false);arrive();},
 onAscend:ascend,
 onTravel:journey=>{if(journey.direction==='in'&&journey.node)rememberJourney(journey.node,journey.parentCamera);document.querySelector('.graph-shell').classList.add('is-travelling');},
 onSettled:()=>document.querySelector('.graph-shell').classList.remove('is-travelling'),
 onGroupSelect:label=>{const g=allGroups.find(g=>g.label===label);if(g)navigate({view:'group',id:g.id,layer:null,selected:null});}
});
function enterGalaxy(id){if(!maps.has(id))return;if(graphModel.nodes.some(n=>n.id===id)&&graph.dive)graph.dive(id);else openItem(id);}
function enterStar(id){if(!stages.has(id))return;if(graphModel.nodes.some(n=>n.id===id)&&graph.dive)graph.dive(id);else openStage(id);}
function openLandmark(id){const item=landmarks.get(id);if(!item)return;if(state.layer!==item.stageId)rememberJourney({id:item.stageId});navigate({view:'roadmap',id:item.roadmapId,layer:item.stageId,selected:id,tab:'overview'});}
function landmarkNode(item){return {id:item.id,label:item.title,type:'landmark',stageId:item.stageId,ownerStageId:item.stageId,landmarkKind:item.kind,group:stageTitle(item.stageId),subtitle:item.kind+' · mathematical target',progress:null,color:'#d9e8f5'};}
function roadmapNode(r){const p=progress.roadmap(r.id);return {id:r.id,label:shortTitle(r.title),type:'roadmap',groupId:r.group,group:groupOf(r).label,color:groupOf(r).color,subtitle:`${mathStages(r).length} topics · ${(r.origin||'campaign')==='tauceti'?'Tau Ceti':'Campaign'}`,progress:p.percent||0,progressLabel:p.total?Math.round(p.percent||0)+'% layers':'Not assessed'};}
function stageNode(s,type='stage'){const p=progress.stage(s.id);return {id:s.id,label:stageTitle(s.id),type,stageId:s.id,ownerStageId:s.id,groupId:maps.get(s.owner)?.group,group:maps.has(s.owner)?groupOf(maps.get(s.owner)).label:'Dependencies',subtitle:'Mathematical topic',progress:p.percent||0,progressLabel:labels[p.status]||'Not assessed',color:'#b67859'};}
function boundaryNode(id){if(stages.has(id)){const n=stageNode(stages.get(id),'external');n.subtitle=shortTitle(maps.get(stages.get(id).owner)?.title||stages.get(id).owner)+' · '+stages.get(id).key;return n;}const x=external.get(id);return{id,label:x?.title||id.replace(/^UPSTREAM:/,''),type:'external',group:'External suppliers',subtitle:'External prerequisite',progress:0,progressLabel:'Not assessed'};}
function buildGraph(){let nodes=[],edges=[];const roadmaps=DATA.roadmaps.filter(permitted);const title=$('view-title'),description=$('view-description'),eyebrow=$('view-eyebrow');clear($('view-actions'));
 if(state.view==='subjects'){
  for(const g of allGroups){const rs=roadmaps.filter(r=>r.group===g.id);const gaps=visibleOpportunities().filter(a=>a.group===g.id);if(!rs.length&&!gaps.length)continue;const p=summarize(rs);nodes.push({id:g.id,label:g.label,type:'group',group:g.label,color:g.color,subtitle:`${rs.length} roadmaps${gaps.length?' · '+gaps.length+' unmapped':''} · click to explore`,progress:p.total?p.percent:null,progressLabel:p.total?Math.round(p.percent||0)+'% layers complete':'No tracked layers'});}
  title.textContent='Explore by subject';eyebrow.textContent='THE MATHEMATICAL LANDSCAPE';description.textContent='Click a subject for its scope. Open it to explore the roadmaps and their layers.';
 }else if(['all','group','collection','neighbors'].includes(state.view)){
  let rs=roadmaps;
  if(state.view==='group')rs=rs.filter(r=>r.group===state.id);
  if(state.view==='collection')rs=(childRoadmaps.get(state.id)||[]).map(id=>maps.get(id)).filter(Boolean);
  if(state.view==='neighbors'){const r=maps.get(state.id),ids=new Set([r.id,...r.prerequisites,...r.consumers]);rs=DATA.roadmaps.filter(x=>ids.has(x.id));}
  const core=new Set(rs.map(r=>r.id));if(state.outside&&state.view==='group'){for(const e of DATA.edges)if(core.has(e.source)||core.has(e.target)){const id=core.has(e.source)?e.target:e.source;if(!rs.some(r=>r.id===id)&&maps.has(id))rs.push(maps.get(id));}}
  nodes=rs.map(roadmapNode);if(['all','group'].includes(state.view)){const gaps=visibleOpportunities().filter(a=>state.view!=='group'||a.group===state.id);nodes.push(...gaps.map(opportunityNode));}const ids=new Set(nodes.map(n=>n.id));edges=DATA.edges.filter(e=>ids.has(e.source)&&ids.has(e.target));
  title.textContent=state.view==='all'?'A universe of mathematics':state.view==='group'?groups.get(state.id).label:state.view==='collection'?shortTitle(maps.get(state.id).title):'Connections: '+shortTitle(maps.get(state.id).title);
  eyebrow.textContent=state.view==='all'?'THE TAU CETI SECTOR CHART':state.view==='neighbors'?'PREREQUISITES AND CONSUMERS':'ROADMAP GALAXIES';description.textContent='Explore named mathematical regions. Routes connect areas with shared prerequisites. Zoom closer to find a roadmap galaxy, then enter its mathematical stars.';
  if(state.view==='group')outsideControl('Show connected roadmaps');if(state.view==='collection')cosmicNavigation();
  const refs=[...relatedEdges,...contextEdges].filter(e=>ids.has(e.source)&&ids.has(e.target));if(state.references)edges=[...edges,...refs];referenceControl();
 }else if(state.view==='roadmap'&&state.layer){
  const s=stages.get(state.layer),r=maps.get(state.id),items=stageLandmarks.get(s.id)||[];
  nodes=[stageNode(s),...items.map(landmarkNode)];
  edges=items.map(item=>({source:s.id,target:item.id,kind:'contains'}));
  title.textContent=stageTitle(s.id);eyebrow.textContent='PLANETARY SYSTEM / '+shortTitle(r.title);
  description.textContent=items.length?'The star is this layer. Its planets are key definitions, results and constructions. Tap a planet to read the mathematics.':'This layer has no individually named mathematical targets extracted from its source. Open the star to read the full layer.';
  cosmicNavigation();$('view-actions').append(btn('Full roadmap',()=>openReader(r.id),'secondary'));
 }else if(state.view==='roadmap'){
  const r=maps.get(state.id),ids=new Set(mathStages(r));nodes=[...ids].map(id=>stages.get(id)).filter(Boolean).map(s=>stageNode(s));
  edges=DATA.stageEdges.filter(e=>ids.has(e.source)&&ids.has(e.target));
  if(state.outside){const additions=new Set();for(const e of DATA.stageEdges)if(ids.has(e.source)!==ids.has(e.target)&&isMathematicalStage(e.source)&&isMathematicalStage(e.target)){edges.push(e);additions.add(ids.has(e.source)?e.target:e.source);}for(const id of additions)nodes.push(boundaryNode(id));}
  title.textContent=shortTitle(r.title);eyebrow.textContent='INSIDE THE GALAXY / MATHEMATICAL TOPICS';description.textContent='Each star is a mathematical topic in this roadmap. Connections show which topics build on which. Keep zooming into a star to discover its orbiting definitions and theorems.';cosmicNavigation();outsideControl('Show outside dependencies');
  $('view-actions').append(btn('Full roadmap',()=>openReader(r.id),'secondary'));
 }
 $('graph-empty').hidden=nodes.length>0;$('edge-legend').textContent=state.layer?'Planets: mathematical targets · Orbits: membership in this layer':state.view==='roadmap'?'Stars: layers · Arrows: prerequisite → consumer':'Regions: mathematical areas · Routes: prerequisites · Dotted: related plans';
 graphModel={nodes,edges,relatedEdges:[...relatedEdges,...contextEdges]};graph.setData(graphModel,{layout:state.view==='subjects'?'groups':state.view==='roadmap'?(state.layer?'solar-system':'layer-constellations'):['all','group','collection'].includes(state.view)?'constellations':'clusters',selectedId:state.selected,canAscend:['roadmap','collection'].includes(state.view)});
 $('graph-counts').textContent=state.layer?`1 layer star · ${nodes.length-1} mathematical planets`:state.view==='roadmap'?`${mathStages(maps.get(state.id)).length} mathematical stars · ${edges.length} prerequisite links`:`${nodes.filter(n=>!n.unmapped).length.toLocaleString()} ${state.view==='subjects'?'subjects':'roadmaps'}${nodes.some(n=>n.unmapped)?' · '+nodes.filter(n=>n.unmapped).length+' unmapped areas':''} · ${edges.filter(e=>e.kind!=='reference').length.toLocaleString()} prerequisite links`;
 $('graph-hint').textContent=state.view==='subjects'?'Tap a subject to explore':state.layer?'Tap a planet to read · zoom out to return':'Scroll or pinch to travel · tap to enter · drag to pan';
}
function cosmicNavigation(){const nav=el('nav','cosmic-navigation');nav.setAttribute('aria-label','Zoom navigation');nav.append(btn(state.layer?'← Roadmap stars':'← Galaxy field',ascend,'cosmic-back'),el('span','cosmic-depth',state.layer?'03 · Planetary system':'02 · Layer stars'));$('view-actions').append(nav);}
function referenceControl(){const label=el('label','toggle'),input=document.createElement('input');input.type='checkbox';input.checked=state.references;input.addEventListener('change',()=>navigate({references:input.checked}));label.append(input,document.createTextNode('Show related-plan links'));$('view-actions').append(label);}
function outsideControl(label){const n=el('label','toggle'),input=document.createElement('input');input.type='checkbox';input.checked=state.outside;input.addEventListener('change',()=>navigate({outside:input.checked}));n.append(input,document.createTextNode(label));$('view-actions').append(n);}
function renderBreadcrumbs(){
 const box=clear($('breadcrumbs'));box.append(btn('All mathematics',()=>navigate({view:'all',id:null,layer:null,selected:null})));
 if(state.id){box.append(el('span','','›'));
  if(maps.has(state.id)){const r=maps.get(state.id),g=groupOf(r);box.append(btn(g.label,()=>navigate({view:'group',id:r.group,layer:null,selected:null})),el('span','','›'),btn(shortTitle(r.title),()=>openItem(r.id),state.layer?'':'current'));
   if(state.layer)box.append(el('span','','›'),el('span','current',stageTitle(state.layer)));
  }else if(groups.has(state.id))box.append(btn(groups.get(state.id).label,()=>{},'current'));
 }else if(state.view==='all')box.append(el('span','','›'),el('span','current','All roadmaps'));
}
function renderCatalogue(){const box=clear($('catalogue'));const query=$('search').value.trim().toLowerCase();const rs=DATA.roadmaps.filter(permitted);if(query){const mapHits=rs.filter(r=>mapSearch.get(r.id).includes(query));const stageHits=DATA.stages.filter(s=>isMathematicalStage(s.id)&&permitted(maps.get(s.owner))&&stageSearch.get(s.id).includes(query));box.append(el('div','catalogue-heading',`${mapHits.length} roadmaps · ${stageHits.length} stages`));for(const r of mapHits.slice(0,35)){const b=btn('',()=>{navigate({view:'group',id:r.group,selected:r.id,tab:'overview'});graph.focus(r.id);},'search-hit');b.append(el('strong','',shortTitle(r.title)),el('small','',groupOf(r).label));box.append(b);}for(const s of stageHits.slice(0,60)){const b=btn('',()=>openStage(s.id),'search-hit');b.append(el('strong','',stageTitle(s.id)),el('small','',s.key+' · '+shortTitle(maps.get(s.owner).title)));box.append(b);}const gapHits=visibleOpportunities().filter(a=>(a.title+' '+a.summary).toLowerCase().includes(query));for(const area of gapHits){const b=btn('',()=>navigate({view:'group',id:area.group,selected:area.id}),'search-hit');b.append(el('strong','',area.title),el('small','','No dedicated roadmap'));box.append(b);}if(!mapHits.length&&!stageHits.length&&!gapHits.length)box.append(el('p','search-empty','No matching roadmap or stage. Try a broader mathematical term.'));return;}
 const gaps=visibleOpportunities();if(gaps.length){const d=el('details','unmapped-index'),head=el('summary','','Unmapped areas · '+gaps.length);d.append(head);for(const area of gaps)d.append(btn(area.title,()=>navigate({view:'group',id:area.group,selected:area.id}),'catalogue-item'));box.append(d);}box.append(el('div','catalogue-heading','Browse the collection'));for(const g of allGroups){const members=rs.filter(r=>r.group===g.id);if(!members.length)continue;const d=document.createElement('details');d.open=state.view==='group'&&state.id===g.id||!!state.selected&&maps.has(state.selected)&&maps.get(state.selected).group===g.id;const summary=document.createElement('summary'),dot=el('span','dot');dot.style.background=g.color;summary.append(dot,el('span','label',g.label),el('small','',members.length));d.append(summary);for(const r of members){const b=btn(shortTitle(r.title),()=>navigate({view:'group',id:r.group,selected:r.id,tab:'overview'}),'catalogue-item'+(state.selected===r.id?' active':''));b.title=r.title;d.append(b);}box.append(d);}}
function detailHeader(box,title,subtitle,accent){const strip=el('div','detail-color');strip.style.background=accent;box.append(strip,el('h2','detail-title',shortTitle(title)));if(subtitle)box.append(el('p','detail-subtitle',subtitle));}
function stats(box,items){const row=el('div','detail-stats');for(const [value,label]of items){const cell=el('div');cell.append(el('strong','',String(value)),el('span','',label));row.append(cell);}box.append(row);}
function section(box,title){box.append(el('h3','section-label',title));}
function item(box,id,action){const s=stages.get(id),r=maps.get(id),x=external.get(id);const title=s?stageTitle(s.id):r?shortTitle(r.title):x?.title||id;const b=btn('',action||(()=>s?openStage(id):r?navigate({view:'group',id:r.group,selected:id,tab:'overview'}):select(id)),'item-link');b.dataset.itemId=id;const label=el('span');label.append(document.createTextNode(title));b.append(label,el('span','arrow','↗'));box.append(b);return b;}
function tabs(box){const nav=el('div','detail-tabs');for(const [id,title]of [['overview','Overview'],['stages','Layers'],['links','Links']])nav.append(btn(title,()=>{state.tab=id;renderInspector();},state.tab===id?'active':''));box.append(nav);}
function progressSummary(box,r){const p=progress.roadmap(r.id),wrap=el('div','progress-summary');const top=el('div','progress-caption');top.append(el('strong','',`${Math.round(p.percent||0)}%`),el('span','',statString(p)));const bar=el('div','progress-track'),fill=el('div');fill.style.width=(p.percent||0)+'%';fill.style.background=color(p.percent||0);bar.append(fill);wrap.append(top,bar,el('p','detail-note',`${p.active||0} in progress · ${p.unknown||0} not assessed. Progress counts tracked leaf layers.`));box.append(wrap);if(r.lifecycle==='completed')box.append(el('span','status-chip','Archived as complete by Tau Ceti maintainers'));}
function stageTree(box,r){
 const visible=mathStages(r),ids=new Set(visible),roots=visible.filter(id=>!ids.has(stages.get(id)?.parentStageId));
 function walk(id,parent,depth){
  const s=stages.get(id);if(!s||depth>12)return;
  const p=progress.stage(id),b=item(parent,id),mark=el('span','stage-state-dot');mark.style.background=color(p.percent||0);mark.title=labels[p.status];b.prepend(mark);
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
 box.append(btn('Show connection map',()=>navigate({view:'neighbors',id:r.id,selected:r.id,tab:'links'}),'secondary'));
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
function landmarkLink(box,landmark){const button=btn('',()=>openLandmark(landmark.id),'item-link');button.append(el('span','landmark-kind',landmark.kind),el('span','',landmark.title));box.append(button);}
function renderInspector(){const id=state.selected,changed=inspectedId!==id,box=clear($('inspector-content'));inspectedId=id;if(changed)box.scrollTop=0;$('inspector').hidden=!id;document.body.classList.toggle('has-selection',!!id);if(!id)return;
 if(opportunities.has(id)){const area=opportunities.get(id);$('selection-kind').textContent='UNMAPPED MATHEMATICS';detailHeader(box,area.title,groups.get(area.group).label,'#91aabd');box.append(el('span','status-chip','No dedicated roadmap'),el('p','detail-summary',area.summary),el('p','detail-note',area.reason));section(box,'Nearby mathematical developments');area.relatedRoadmaps.forEach(r=>item(box,r,()=>openItem(r)));box.append(el('p','detail-note','These links provide mathematical context. This proposed area has no layers or completion percentage.'));return;}
 if(groups.has(id)){const g=groups.get(id),members=DATA.roadmaps.filter(r=>r.group===id&&permitted(r));$('selection-kind').textContent='SUBJECT';detailHeader(box,g.label,`${members.length} roadmaps`,g.color);const region=DATA.regions?.groups?.[id]||g;box.append(el('p','detail-summary',region.description||`Explore the mathematics of ${g.label.toLowerCase()}.`));if(region.topics?.length){const topics=el('ul','region-topics');region.topics.forEach(topic=>topics.append(el('li','',topic)));box.append(topics);}const bridges=(region.bridgeGroups||[]).filter(gid=>groups.has(gid));if(bridges.length){section(box,'Connected areas');for(const gid of bridges)box.append(btn(groups.get(gid).label,()=>openItem(gid),'topic-link'));}box.append(btn('Open roadmaps →',()=>openItem(id),'primary'));section(box,'In this subject');members.forEach(r=>item(box,r.id,()=>openItem(r.id)));const gaps=visibleOpportunities().filter(a=>a.group===id);if(gaps.length){section(box,'Areas needing a roadmap');gaps.forEach(a=>box.append(btn(a.title,()=>select(a.id),'item-link')));}return;}
 if(maps.has(id)){const r=maps.get(id),p=progress.roadmap(id);$('selection-kind').textContent=(r.origin||'campaign')==='tauceti'?'TAU CETI ROADMAP':'CAMPAIGN ROADMAP';detailHeader(box,r.title,groupOf(r).label,color(p.percent||0));const pin=btn(pins.has(id)?'★ Pinned':'☆ Pin roadmap',()=>togglePin(id),'pin-button');pin.setAttribute('aria-pressed',String(pins.has(id)));box.append(pin);progressSummary(box,r);const row=el('div','button-row');row.append(btn(r.stages.length?'Open stage layers →':'Open sub-roadmaps →',()=>openItem(id),'primary'),btn('Read full roadmap',()=>openReader(id),'secondary'));box.append(row);tabs(box);
 if(state.tab==='overview'){box.append(el('p','detail-summary',r.summary));const tags=DATA.regions?.roadmapTags?.[id];if(tags?.length){const row=el('div','related-subjects');for(const tag of tags){const gid=typeof tag==='string'?tag:tag.group;if(groups.has(gid))row.append(btn(groups.get(gid).label,()=>openItem(gid),'topic-link'));}box.append(row);}stats(box,[[mathStages(r).length,'topics'],[r.prerequisites.length,'prerequisites'],[r.consumers.length,'consumers']]);if(r.parentRoadmapId)item(box,r.parentRoadmapId,()=>openItem(r.parentRoadmapId));if(r.statusMarkdown){section(box,'Recorded project status');box.append(el('p','detail-note','Imported from the local Tau Ceti roadmap checkout. Reports are snapshots; local changes are kept separately.'+(p.snapshotDate?' Reported '+p.snapshotDate+'.':'')),btn('Read status report',()=>openReader(id,'status'),'secondary'));}if(r.progressMarkdown)box.append(btn('Read progress log',()=>openReader(id,'progress'),'quiet'));section(box,'Starting points');mathStages(r).slice(0,4).forEach(s=>item(box,s));if((childRoadmaps.get(id)||[]).length){section(box,'Sub-roadmaps');childRoadmaps.get(id).forEach(child=>item(box,child,()=>openItem(child)));}}
 if(state.tab==='stages'){box.append(el('p','detail-note','Open a layer to read its target and update its local progress. Sub-layers can be expanded independently.'));stageTree(box,r);}
 if(state.tab==='links')renderConnections(box,r);

 return;}
 if(landmarks.has(id)){const landmark=landmarks.get(id),stage=stages.get(landmark.stageId),r=maps.get(landmark.roadmapId);$('selection-kind').textContent=landmark.kind.toUpperCase()+' / MATHEMATICAL PLANET';detailHeader(box,landmark.title,shortTitle(r.title),'#a8c8df');box.append(el('span','landmark-kind',landmark.kind));const text=el('div','md-content landmark-description');text.append(TauMarkdown.render(TauPresentation.landmarkDescription(landmark),{basePath:landmark.sourcePath}));box.append(text);section(box,'In this layer');box.append(btn(stageTitle(stage.id),()=>openStage(stage.id),'item-link'),el('p','detail-note','This is a target named in the roadmap. Progress is recorded for its parent layer.'),btn('Read full roadmap',()=>openReader(r.id),'secondary'));return;}
 if(stages.has(id)){
  const s=stages.get(id),r=maps.get(s.owner),p=progress.stage(id),mathematical=isMathematicalStage(id);
  $('selection-kind').textContent=mathematical?'MATHEMATICAL TOPIC':'PROJECT TASK';
  detailHeader(box,stageTitle(id),'',color(p.percent||0));box.append(btn(shortTitle(r.title),()=>openItem(r.id),'inline-owner'));
  const summary=stageSummary(id);if(summary){const md=el('div','md-content stage-description');md.append(TauMarkdown.render(summary,{basePath:s.sourcePath}));box.append(md);}
  const targets=stageLandmarks.get(id)||[];
  if(targets.length){section(box,'Definitions and results');targets.forEach(target=>landmarkLink(box,target));}
  const children=(stageChildren.get(id)||[]).filter(isMathematicalStage);
  if(children.length){section(box,'Further topics');children.forEach(x=>item(box,x));}
  const requirements=s.requires.filter(isMathematicalStage),consumers=s.consumers.filter(isMathematicalStage);
  if(requirements.length){section(box,'Builds on');requirements.forEach(x=>item(box,x));}
  if(consumers.length){section(box,'Used in');consumers.forEach(x=>item(box,x));}
  box.append(el('p','status-chip',`${p.manual?'Your local status':p.basis&&p.basis!=='unknown'?'Recorded status':'Progress'}: ${labels[p.status]||p.status}`));renderProgressControls(box,s,p);
  const source=el('details','source-layer');source.append(el('summary','','Source layer and work plan'));
  const md=el('div','md-content source-stage-description');md.append(TauMarkdown.render(s.description,{basePath:s.sourcePath}));source.append(md);box.append(source,btn('Read full roadmap',()=>openReader(r.id),'secondary'));return;
 }
 const x=external.get(id);$('selection-kind').textContent='EXTERNAL PREREQUISITE';detailHeader(box,x?.title||id,'Integration contract','#89959d');box.append(el('p','detail-summary',x?.action||'This prerequisite is outside the currently embedded roadmaps. Its exact statement and implementation must be checked in the supplying library.'));if(x?.integration_owner&&stages.has(x.integration_owner))item(box,x.integration_owner);if(x?.consumers?.length){section(box,'Consumers');x.consumers.forEach(c=>item(box,c));}}
function renderProgressControls(box,s,p){const card=el('div','progress-controls');card.append(el('h3','section-label','Track this layer'));const selectEl=el('select');selectEl.setAttribute('aria-label','Layer status');for(const [value,title]of Object.entries(labels)){const o=el('option','',title);o.value=value;selectEl.append(o);}selectEl.value=p.status||'unknown';const note=el('textarea');note.rows=2;note.maxLength=4000;note.placeholder='Evidence, PR link or a note (optional)';note.setAttribute('aria-label','Progress note');note.value=p.note||'';const count=descendants(s.id).length;if(count)card.append(el('p','detail-note',`Updating this layer also updates its ${count} sub-layers.`));card.append(selectEl,note);const row=el('div','button-row');row.append(btn('Save status',()=>{progress.setStage(s.id,selectEl.value,note.value);toast('Progress saved locally');},'primary'));if(p.manual)row.append(btn('Use recorded status',()=>{progress.resetStage(s.id);toast('Restored recorded status');},'quiet'));card.append(row);if(p.basis)card.append(el('p','detail-note','Source: '+String(p.basis).replace(/_/g,' ')+(p.snapshotDate?' · '+p.snapshotDate:'')));if(p.evidence?.length){const d=el('details','progress-evidence');d.append(el('summary','','Recorded evidence'));for(const evidence of p.evidence){d.append(el('p','detail-note',typeof evidence==='string'?evidence:evidence.quote||evidence.path||JSON.stringify(evidence)));}card.append(d);}box.append(card);}
function descendants(id){const result=[];const visit=n=>{for(const c of stageChildren.get(n)||[]){if(result.includes(c))continue;result.push(c);visit(c);}};visit(id);return result;}
function render(){clearTimeout(flightTimer);document.body.classList.toggle('is-system-view',!!state.layer);document.querySelector('.graph-shell').classList.remove('is-entering','is-travelling');document.querySelector('[data-view="subjects"] small').textContent=allGroups.filter(g=>DATA.roadmaps.some(r=>r.group===g.id&&permitted(r))||visibleOpportunities().some(a=>a.group===g.id)).length;document.querySelectorAll('[data-view]').forEach(n=>n.classList.toggle('active',n.dataset.view===state.view));$('source-filter').value=state.origin;$('show-unmapped').checked=state.unmapped;$('activity-filter').value=state.activity;renderBreadcrumbs();renderInspector();renderCatalogue();renderPins();renderStats();buildGraph();}
function showDocument(doc){currentDoc=doc;$('reader-title').textContent=shortTitle(doc.title);const body=clear($('reader-body'));if(doc.summary){const synopsis=el('aside','reader-summary');synopsis.append(el('p','eyebrow','MATHEMATICAL OVERVIEW'),el('p','',doc.summary));body.append(synopsis);}body.append(TauMarkdown.render(doc.text,{basePath:doc.path}));$('open-source').href=fileURL(doc.path);clear($('reader-toc'));body.querySelectorAll('h2,h3').forEach(h=>{$('reader-toc').append(btn(h.dataset.tocLabel||h.textContent,()=>h.scrollIntoView({behavior:'smooth',block:'start'})));});if(!$('reader').open)$('reader').showModal();body.scrollTop=0;}
function openReader(id,kind='readme'){const r=maps.get(id);if(!r){const doc=documents.get(id);if(doc)showDocument({...doc,path:doc.sourcePath});return;}let text=r.readme,title=r.title,path=r.sourcePath;if(kind==='status'){text=r.statusMarkdown;title=r.title+' — status';path=r.sourcePath.replace(/README\.md$/,'STATUS.md');}if(kind==='progress'){text=r.progressMarkdown;title=r.title+' — progress log';path=r.sourcePath.replace(/README\.md$/,'PROGRESS.md');}if(text)showDocument({id,kind,text,title,path,summary:kind==='readme'?r.summary:null});}

function fileURL(path){if(!path)return'#';try{if(/^(https?:|file:)/.test(path))return new URL(path).href;if(path.startsWith('/'))return new URL(path,'file:///').href;return new URL(path,location.href).href;}catch{return'#';}}
function download(name,text,type='application/json'){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function handleDocLink(event){const a=event.target.closest('[data-doc-link]');if(!a)return;event.preventDefault();const raw=a.dataset.docLink,base=a.dataset.basePath||currentDoc?.path||'';if(raw.startsWith('#')){const id=decodeURIComponent(raw.slice(1));const target=$('reader-body').querySelector('#'+CSS.escape(id))||$('inspector-content').querySelector('#'+CSS.escape(id));if(target)target.scrollIntoView({behavior:'smooth'});return;}let url;try{url=new URL(raw,fileURL(base));}catch{return;}const path=decodeURIComponent(url.pathname),r=DATA.roadmaps.find(x=>fileURL(x.sourcePath)===url.href.split('#')[0]||fileURL(x.sourcePath.replace(/README\.md$/,'STATUS.md'))===url.href.split('#')[0]||fileURL(x.sourcePath.replace(/README\.md$/,'PROGRESS.md'))===url.href.split('#')[0]);const doc=[...documents.values()].find(d=>fileURL(d.sourcePath)===url.href.split('#')[0]);if(r||doc){if(r)openReader(r.id,path.endsWith('STATUS.md')?'status':path.endsWith('PROGRESS.md')?'progress':'readme');else openReader(doc.id);if(url.hash)setTimeout(()=>{const target=$('reader-body').querySelector('#'+CSS.escape(decodeURIComponent(url.hash.slice(1))));target?.scrollIntoView();},50);return;}if(['file:','http:','https:'].includes(url.protocol))window.open(url.href,'_blank','noopener');}
document.addEventListener('click',handleDocLink);
$('search').addEventListener('input',renderCatalogue);
document.querySelectorAll('[data-view]').forEach(n=>n.addEventListener('click',()=>navigate({view:n.dataset.view,id:null,selected:null,tab:'overview'})));
$('source-filter').addEventListener('change',e=>navigate({origin:e.target.value,view:'all',id:null,selected:null,activity:'all'}));
$('show-unmapped').addEventListener('change',e=>navigate({unmapped:e.target.checked,view:'all',id:null,selected:null,...(!e.target.checked&&state.activity==='unmapped'?{activity:'all'}:{})}));
$('activity-filter').addEventListener('change',e=>navigate({activity:e.target.value,view:'all',id:null,selected:null,...(e.target.value==='unmapped'?{unmapped:true,origin:'all'}:{})}));
$('catalogue-button').addEventListener('click',()=>{const open=document.body.classList.toggle('catalogue-open');$('catalogue-button').setAttribute('aria-expanded',String(open));if(open)$('search').focus();});
$('stats-button').addEventListener('click',()=>{renderStats();$('stats-dialog').showModal();});$('close-stats').addEventListener('click',()=>$('stats-dialog').close());
$('download-offline').addEventListener('click',()=>download('TauCeti_Atlas.html',offlineDocument,'text/html'));
$('close-inspector').addEventListener('click',()=>{state.selected=null;try{history.replaceState(null,'',routeHash(state));}catch{}renderInspector();graph.select(null);});
$('zoom-in').addEventListener('click',()=>graph.zoomIn());$('zoom-out').addEventListener('click',()=>graph.zoomOut());$('fit-graph').addEventListener('click',()=>graph.fit());
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
progress.subscribe(()=>{renderInspector();renderCatalogue();renderStats();if(state.activity!=='all')buildGraph();const update={};for(const n of graphModel.nodes){if(stages.has(n.id)){const p=progress.stage(n.id);update[n.id]={progress:p.percent||0,progressLabel:labels[p.status]||'Not assessed'};}else if(maps.has(n.id)){const p=progress.roadmap(n.id);update[n.id]={progress:p.percent||0,progressLabel:p.total?Math.round(p.percent||0)+'% layers':'Not assessed'};}else if(groups.has(n.id)){const p=summarize(DATA.roadmaps.filter(r=>r.group===n.id&&permitted(r)));update[n.id]={progress:p.total?p.percent:null,progressLabel:p.total?Math.round(p.percent||0)+'% layers complete':'No tracked layers'};}}graph.setProgress(update);});
$('roadmap-total').textContent=DATA.roadmaps.length.toLocaleString();$('stage-total').textContent=DATA.stages.length.toLocaleString();document.querySelector('[data-view="subjects"] small').textContent=allGroups.length;document.querySelector('[data-view="all"] small').textContent=DATA.roadmaps.length;
state=readRoute();render();window.TauExplorer={data:DATA,graph,progress,navigate,openItem,openStage,openReader,getState:()=>({...state}),getGraph:()=>graphModel,landmarks:landmarkList,openLandmark,enterGalaxy,ascend,enterStar,presentation,stageTitle,stageSummary,isMathematicalStage,version:'2026-09-15-sector-atlas'};
})();
