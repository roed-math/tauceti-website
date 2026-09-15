from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import json,time,sys,tempfile
REPO=Path(__file__).resolve().parents[1]
ROOT=Path(tempfile.mkdtemp(prefix='tauceti-browser-'))
url=next((arg for arg in sys.argv[1:] if not arg.startswith('--')),(REPO/'index.html').as_uri())
desktop_only='--desktop-only' in sys.argv[1:]
results=[];errors=[];requests=[]
def record(name,value=True):
 if not value:
  active=globals().get('mp')
  if active is None or active.is_closed():active=globals().get('page')
  try:
   diagnostic=active.evaluate("() => ({state:TauExplorer.getState(),graph:TauExplorer.graph.debugState().semantic,graphSelected:TauExplorer.graph.debugState().selectedId,captionCollisions:window.__tauTestCaptionCollisions||[],selectionKind:document.querySelector('#selection-kind')?.textContent,controls:Array.from(document.querySelectorAll('[aria-label=\"Layer status\"]')).map(e=>({display:getComputedStyle(e).display,visibility:getComputedStyle(e).visibility,rect:e.getBoundingClientRect().toJSON()}))})")
   print(json.dumps({'failedCheck':name,'diagnostic':diagnostic,'artifacts':str(ROOT)},indent=2),flush=True)
   active.screenshot(path=str(ROOT/'failure.png'),animations='disabled')
  except Exception as error:print('Could not collect diagnostics:',error,flush=True)
  raise AssertionError(name)
 results.append(name)
def wheel_until(page, selector, delta, predicate, attempts=12):
 # Exercise the user's wheel gesture at a visible target; allow the semantic
 # transition and its animation to settle before issuing the next gesture.
 for _ in range(attempts):
  if page.evaluate(predicate):return True
  target=page.locator(selector).first
  bounds=target.bounding_box()
  if bounds is None:return False
  page.mouse.move(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
  page.mouse.wheel(0,delta)
  try:
   page.wait_for_function(predicate,timeout=1100)
   return True
  except PlaywrightTimeoutError:pass
 return bool(page.evaluate(predicate))
def touch_points(points):
 return [dict(x=x,y=y,id=i+1,radiusX=5,radiusY=5,force=1) for i,(x,y) in enumerate(points)]
def touch_swipe(page, session, start, end, steps=10):
 session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':touch_points([start])})
 for step in range(1,steps+1):
  f=step/steps
  point=(start[0]+(end[0]-start[0])*f,start[1]+(end[1]-start[1])*f)
  session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':touch_points([point])})
  page.wait_for_timeout(18)
 session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
 page.wait_for_timeout(120)
def pinch_until(page, session, selector, scale, predicate, attempts=7):
 # Two independently moving fingers generate native touch events. Their centroid
 # stays on the chosen object, so entering it tests the map's touch targeting.
 page.wait_for_timeout(900)
 for _ in range(attempts):
  if page.evaluate(predicate):return True
  target=page.locator(selector).first.bounding_box()
  chart=page.locator('#graph').bounding_box()
  if target is None or chart is None:return False
  x=target['x']+target['width']/2;y=target['y']+target['height']/2
  room=min(x-chart['x'],chart['x']+chart['width']-x,60)-3
  if room<4:return False
  radius=min(28,room/scale) if scale>1 else min(45,room)
  def fingers(r):return touch_points([(x-r,y),(x+r,y)])
  session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':fingers(radius)})
  for step in range(1,13):
   r=radius*(1+(scale-1)*step/12)
   session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':fingers(r)})
   page.wait_for_timeout(20)
  session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
  try:
   page.wait_for_function(predicate,timeout=1100)
   return True
  except PlaywrightTimeoutError:pass
 return bool(page.evaluate(predicate))
def finite_chart(page):
 return page.evaluate("TauExplorer.graph.debugState().positions.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y))")
def captions_do_not_overlap(page, minimum=1):
 # Caption rectangles include every text line, while excluding the star cores.
 # Hiding lower-priority labels is valid; displaying overlapping text is not.
 page.wait_for_timeout(500)
 return page.evaluate("""minimum => {
  const captions=TauExplorer.graph.debugState().positions.filter(n=>n.caption);
  const collisions=[];
  for(let i=0;i<captions.length;i++)for(let j=i+1;j<captions.length;j++){
   const a=captions[i],b=captions[j],x=a.caption,y=b.caption;
   const width=Math.min(x.x+x.w,y.x+y.w)-Math.max(x.x,y.x);
   const height=Math.min(x.y+x.h,y.y+y.h)-Math.max(x.y,y.y);
   if(width>1&&height>1)collisions.push({first:a.id,second:b.id,width,height});
  }
  window.__tauTestCaptionCollisions=collisions;
  return captions.length>=minimum&&captions.every(n=>Object.values(n.caption).every(Number.isFinite))&&!collisions.length;
 }""",minimum)
def sector_routes_match_dependencies(page):
 return page.evaluate("""() => {
  const graph=TauExplorer.getGraph(),nodes=new Map(graph.nodes.map(n=>[n.id,n])),routes=TauExplorer.graph.debugState().sectorRoutes;
  if(!Array.isArray(routes)||!routes.length)return false;
  const key=e=>JSON.stringify([e.source,e.target,e.kind]),pair=(a,b)=>JSON.stringify([a,b].sort());
  const expected=graph.edges.filter(e=>e.kind!=='reference'&&e.kind!=='contains'&&nodes.has(e.source)&&nodes.has(e.target)&&nodes.get(e.source).group!==nodes.get(e.target).group);
  const edgeKeys=expected.map(key).sort(),routePairs=new Set();
  for(const route of routes){
   const p=pair(route.source,route.target);
   if(routePairs.has(p)||!route.witnesses.length||route.dependencies!==route.witnesses.length)return false;
   routePairs.add(p);
   if(!route.witnesses.every(e=>nodes.has(e.source)&&nodes.has(e.target)&&pair(nodes.get(e.source).group,nodes.get(e.target).group)===p))return false;
  }
  return JSON.stringify(routes.flatMap(r=>r.witnesses).map(key).sort())===JSON.stringify(edgeKeys);
 }""")
def headings_clear_controls(page):
 page.wait_for_timeout(500)
 return page.evaluate("""() => {
  const tools=document.querySelector('.graph-tools').getBoundingClientRect();
  const headings=Array.from(document.querySelectorAll('.tau-constellation-subject')).filter(e=>getComputedStyle(e).display!=='none');
  const boxes=headings.map(e=>({label:e.textContent,box:e.getBoundingClientRect()}));
  const intersects=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1;
  const collisions=boxes.filter(({box})=>intersects(box,tools)).map(({label,box})=>({first:label,second:'Chart controls',box}));
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++)if(intersects(boxes[i].box,boxes[j].box))collisions.push({first:boxes[i].label,second:boxes[j].label,box:boxes[i].box,other:boxes[j].box});
  window.__tauTestCaptionCollisions=collisions;
  return headings.length===TauExplorer.graph.debugState().constellationSubjects&&!collisions.length;
 }""")
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 context=browser.new_context(viewport={'width':1600,'height':1000},accept_downloads=True)
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 if url.startswith('file:'):
  page.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
  page.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
 page.goto(url,wait_until='load');page.wait_for_function('!!window.TauExplorer',timeout=15000)
 record('Native offline mathematics renders',page.evaluate("() => {const d=TauMarkdown.render('$x^2$');return !!d.querySelector('math')}"))
 record('180 roadmap and 1604 stage records',page.evaluate('TauExplorer.data.roadmaps.length===180 && TauExplorer.data.stages.length===1604'))
 page.screenshot(path=str(ROOT/'preview-overview.png'),animations='disabled')
 record('16 unmapped areas are separate from 180 roadmaps',page.evaluate('TauExplorer.data.opportunities.areas.length===16 && TauExplorer.getGraph().nodes.filter(n=>n.unmapped).length===16'))
 record('Unmapped regions have outlined galaxy symbols',page.locator('.tau-unmapped-node').count()==16)
 record('Outer atlas contains 180 roadmap galaxies and 16 unmapped areas',page.evaluate("TauExplorer.getGraph().nodes.filter(n=>n.type==='roadmap').length===180 && TauExplorer.getGraph().nodes.length===196"))
 record('Real prerequisite sector routes are visible on arrival',page.evaluate("() => {const routes=Array.from(document.querySelectorAll('.tau-sector-route')),data=TauExplorer.graph.debugState().sectorRoutes;return TauExplorer.getGraph().edges.filter(e=>e.kind!=='reference'&&e.kind!=='contains').length===1011 && routes.length>0 && routes.length===data.length && routes.every(e=>Number(getComputedStyle(e).opacity)>0 && getComputedStyle(e).display!=='none' && e.getAttribute('data-source-area') && e.getAttribute('data-target-area'));}"))
 page.evaluate("TauExplorer.navigate({view:'subjects',id:null,selected:null})")
 record('Roadmap-free regions do not imply zero percent completion',page.evaluate("TauExplorer.getGraph().nodes.filter(n=>['geometry','combinatorics','computation','logic'].includes(n.id)).every(n=>n.progress===null)"))
 page.evaluate("TauExplorer.navigate({view:'all',id:null,selected:null,references:true})")
 record('Unmapped areas can show contextual links',page.evaluate("TauExplorer.getGraph().edges.some(e=>e.kind==='reference' && e.source.startsWith('unmapped:'))"))
 page.evaluate("TauExplorer.navigate({references:false})")
 gap=page.evaluate('TauExplorer.data.opportunities.areas[0].id')
 page.locator('[data-node-id="'+gap+'"]').click()
 record('Unmapped area explains missing plan without fake progress',page.locator('#selection-kind').inner_text()=='UNMAPPED MATHEMATICS' and page.locator('.progress-summary').count()==0)
 page.locator('#show-unmapped').uncheck()
 record('Unmapped areas can be hidden',page.evaluate('TauExplorer.getGraph().nodes.length===180'))
 page.locator('#source-filter').select_option('tauceti')
 page.locator('#activity-filter').select_option('unmapped')
 record('Dedicated unmapped filter restores all opportunity areas',page.evaluate("TauExplorer.getState().origin==='all' && TauExplorer.getState().unmapped && TauExplorer.getGraph().nodes.length===16 && TauExplorer.getGraph().nodes.every(n=>n.unmapped)"))
 page.locator('#show-unmapped').uncheck()
 record('Hiding unmapped areas restores the roadmap view',page.evaluate("TauExplorer.getState().activity==='all' && TauExplorer.getGraph().nodes.length===180"))
 record('Mathematical stars exclude procedural labels',page.evaluate("TauExplorer.landmarks.every(x=>!/^(Dependency|Canonical owner|API to develop|the|Tests|Suggested home)$/i.test(x.title))"))
 record('All roadmap summaries use mathematical prose',page.evaluate("TauExplorer.data.roadmaps.every(r=>r.summary.split(/\\s+/).length>=40 && !/portfolio audit|component implements|silently attributed/.test(r.summary))"))

 # Presentation hides administrative tasks without deleting their source or status.
 page.evaluate("TauExplorer.navigate({view:'roadmap',id:'FoundationsAndLibraryIntegration',layer:null,selected:null,origin:'all',activity:'all',outside:false})")
 record('Administrative library pinning is not a mathematical star',page.evaluate("!TauExplorer.isMathematicalStage('FoundationsAndLibraryIntegration:LI.0') && !TauExplorer.getGraph().nodes.some(n=>n.id==='FoundationsAndLibraryIntegration:LI.0') && TauExplorer.getGraph().nodes.every(n=>TauExplorer.isMathematicalStage(n.id))"))
 record('Hidden administrative layer retains its raw source and progress',page.evaluate("() => {const id='FoundationsAndLibraryIntegration:LI.0',raw=TauExplorer.data.stages.find(s=>s.id===id);return raw.title==='Pinned libraries and declarations' && raw.description.includes('Record Lean, Mathlib, TauCeti and supplier-roadmap commits separately.') && TauExplorer.progress.roadmapLeaves(raw.owner).includes(id) && typeof TauExplorer.progress.stage(id).status==='string'}"))
 page.evaluate("TauExplorer.openReader('FoundationsAndLibraryIntegration')")
 record('Full source document preserves hidden administrative instructions','Pinned libraries and declarations' in page.locator('#reader-body').inner_text())
 page.locator('#close-reader').click()
 pinned_group='tauceti:TauCetiRoadmap/ReductiveGroups#layer-9-pinned-chevalleydemazure-group-schemes-over-ℤ'
 page.evaluate("TauExplorer.openItem('tauceti:TauCetiRoadmap/ReductiveGroups')")
 record('Mathematical pinned group schemes remain visible',page.evaluate("id => TauExplorer.isMathematicalStage(id) && TauExplorer.getGraph().nodes.some(n=>n.id===id && n.label===TauExplorer.stageTitle(id))",pinned_group))
 page.locator('[data-node-id="'+pinned_group+'"] .tau-star-hit').click()
 page.wait_for_function("id => TauExplorer.getState().layer===id",arg=pinned_group)
 record('Pinned group schemes show mathematics before progress controls',page.locator('.stage-description').is_visible() and page.evaluate("id => {const description=document.querySelector('.stage-description'),controls=document.querySelector('.progress-controls');return TauExplorer.stageSummary(id).length>60 && TauExplorer.getGraph().nodes.some(n=>n.id===id && n.type==='stage') && !!(description.compareDocumentPosition(controls)&Node.DOCUMENT_POSITION_FOLLOWING)}",pinned_group))

 # A real wheel gesture traverses each semantic level, then reverses it.
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null,origin:'all',activity:'all',unmapped:true,outside:false})")
 page.wait_for_timeout(900)
 record('Wheel zoom enters a roadmap galaxy',wheel_until(page,'[data-node-id="AnalyticNumberTheory"] .tau-star-hit',-450,"TauExplorer.getState().view==='roadmap' && TauExplorer.getState().id==='AnalyticNumberTheory' && !TauExplorer.getState().layer"))
 record('A roadmap displays only its mathematical layer stars',page.evaluate("() => {const expected=TauExplorer.data.roadmaps.find(r=>r.id==='AnalyticNumberTheory').stages.filter(TauExplorer.isMathematicalStage),nodes=TauExplorer.getGraph().nodes;return TauExplorer.graph.debugState().layout==='layer-constellations' && nodes.length===expected.length && nodes.every(n=>n.type==='stage' && expected.includes(n.id))}"))
 record('Layer constellation positions are finite and distinct',finite_chart(page) and page.evaluate("new Set(TauExplorer.graph.debugState().positions.map(n=>n.x+','+n.y)).size===TauExplorer.getGraph().nodes.length"))
 page.screenshot(path=str(ROOT/'preview-layer-constellations.png'),animations='disabled')
 page.wait_for_timeout(900)
 record('Wheel zoom enters a layer solar system',wheel_until(page,'[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit',-450,"TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0' && TauExplorer.graph.debugState().layout==='solar-system'"))
 record('Solar system contains one layer and only its mathematical targets',page.evaluate("() => {const graph=TauExplorer.getGraph(),layer=TauExplorer.getState().layer;return graph.nodes.filter(n=>n.type==='stage').length===1 && graph.nodes.find(n=>n.type==='stage').id===layer && graph.nodes.filter(n=>n.type==='landmark').length===TauExplorer.landmarks.filter(x=>x.stageId===layer).length && graph.nodes.filter(n=>n.type==='landmark').every(n=>n.stageId===layer)}"))
 record('Solar system has orbital paths and finite positions',page.locator('.tau-orbit-path').count()>0 and finite_chart(page))
 page.screenshot(path=str(ROOT/'preview-solar-system.png'),animations='disabled')
 page.wait_for_timeout(900)
 record('Wheel zoom out returns to the roadmap',wheel_until(page,'#graph',450,"TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer && TauExplorer.graph.debugState().layout==='layer-constellations'"))
 page.wait_for_timeout(900)
 record('Wheel zoom out returns to the atlas',wheel_until(page,'#graph',450,"TauExplorer.getState().view==='all' && !TauExplorer.getState().layer && TauExplorer.graph.debugState().layout==='constellations'"))
 record('Zoom round trip retains the whole atlas',page.evaluate('TauExplorer.getGraph().nodes.length===196'))
 page.screenshot(path=str(ROOT/'preview-galaxy-atlas.png'),animations='disabled')

 # Click navigation provides the same path without requiring zoom gestures.
 page.evaluate("TauExplorer.navigate({view:'subjects',id:null,layer:null,selected:null,origin:'all'})")
 page.locator('[data-node-id="classical"]').click()
 record('Click subject opens its description',page.locator('#inspector').is_visible())
 page.get_by_role('button',name='Open roadmaps →').click()
 page.locator('[data-node-id="AnalyticNumberTheory"] .tau-star-hit').click()
 page.wait_for_function("TauExplorer.getState().view==='roadmap' && TauExplorer.graph.debugState().layout==='layer-constellations'")
 record('Single click enters roadmap galaxy',page.evaluate("TauExplorer.getState().id==='AnalyticNumberTheory' && !TauExplorer.getState().layer"))
 record('Click roadmap shows meaningful summary',len(page.locator('.detail-summary').inner_text())>50)
 page.wait_for_timeout(500)
 record('Roadmap layer view has no mathematical planets yet',page.evaluate("TauExplorer.getGraph().nodes.length>0 && TauExplorer.getGraph().nodes.every(n=>n.type==='stage' && TauExplorer.isMathematicalStage(n.id))"))
 page.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit').click()
 page.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0' && TauExplorer.graph.debugState().layout==='solar-system'")
 record('Single click opens the chosen layer solar system',page.evaluate("TauExplorer.getState().selected==='AnalyticNumberTheory:AN.0'"))
 star=page.evaluate("TauExplorer.getGraph().nodes.find(n=>n.type==='landmark').id")
 page.locator('[data-node-id="'+star+'"] .tau-star-hit').click()
 record('Planet opens source-backed mathematical details',page.locator('.landmark-description').is_visible() and len(page.locator('.landmark-description').inner_text())>20)
 record('Inspecting a planet preserves its parent solar system',page.evaluate("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0' && TauExplorer.graph.debugState().layout==='solar-system'"))
 page.screenshot(path=str(ROOT/'preview-mathematical-planet.png'),animations='disabled')
 page.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit').click()
 record('Central layer star exposes progress controls',page.get_by_label('Layer status',exact=True).is_visible())

 page.get_by_label('Layer status',exact=True).select_option('complete');page.get_by_label('Progress note',exact=True).fill('Browser test evidence')
 page.get_by_role('button',name='Save status',exact=True).click()
 record('Local update persists and makes stage green',page.evaluate("TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').manual && TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='complete'"))
 record('Node progress colour updates',page.locator('[data-node-id="AnalyticNumberTheory:AN.0"]').get_attribute('data-progress')=='100')
 page.reload(wait_until='load');page.wait_for_function('!!window.TauExplorer')
 record('Progress survives reload',page.evaluate("TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='complete'"))
 page.screenshot(path=str(ROOT/'preview-stage.png'),animations='disabled')
 record('Export/reset/import round trip',page.evaluate("""() => {const x=TauExplorer.progress.export();TauExplorer.progress.resetStage('AnalyticNumberTheory:AN.0');const reverted=TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status!=='complete';TauExplorer.progress.import(x);return reverted&&TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='complete'}"""))
 record('Malformed import is atomic',page.evaluate("""() => {const a=JSON.stringify(TauExplorer.progress.export());try{TauExplorer.progress.import({version:1,stages:{bad:{status:'complete'}}});return false}catch{}return a===JSON.stringify(TauExplorer.progress.export())}"""))
 page.evaluate("TauExplorer.progress.resetStage('AnalyticNumberTheory:AN.0')")
 page.get_by_role('button',name='Read full roadmap',exact=True).click()
 record('Full document readable offline',page.locator('#reader[open]').is_visible() and len(page.locator('#reader-body').inner_text())>3000)
 page.locator('#close-reader').click()
 page.locator('#search').fill('Perron')
 record('Search reaches mathematical roadmap text',page.locator('.search-hit').count()>0)
 page.locator('#search').fill('')
 page.locator('#source-filter').select_option('tauceti')
 record('Tau Ceti collection filter',page.evaluate("TauExplorer.getState().origin==='tauceti'"))
 page.evaluate("TauExplorer.openItem('tauceti:Completed/EffectiveBounds')")
 record('Maintainer completed area is green',page.evaluate("TauExplorer.progress.roadmap('tauceti:Completed/EffectiveBounds').percent===100"))
 page.evaluate("TauExplorer.openItem('tauceti:TauCetiRoadmap/RepresentationTheory')")
 record('Nested roadmap collection opens 11 children',page.evaluate("TauExplorer.getState().view==='collection' && TauExplorer.graph.debugState().nodes===11"))
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null,origin:'all',unmapped:false})")
 record('All nodes and all roadmap edges available',page.evaluate('TauExplorer.graph.debugState().nodes===180 && TauExplorer.graph.debugState().edges===1011'))
 record('All graph positions finite',page.evaluate('TauExplorer.graph.debugState().positions.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y))'))
 page.screenshot(path=str(ROOT/'preview-all.png'),animations='disabled')
 first_caption=page.locator('.tau-constellation-subject').first
 first_caption.click();record('Area caption opens its mathematical group',page.evaluate("TauExplorer.getState().view==='group'"))
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null,origin:'all',unmapped:false})")
 record('Galaxy overview has 13 mathematical regions',page.evaluate("TauExplorer.graph.debugState().layout==='constellations' && TauExplorer.graph.debugState().constellationSubjects===13"))
 page.locator('#fit-graph').click();page.wait_for_timeout(500)
 record('Every subject heading stays visible and readable at atlas fit',page.evaluate("""() => {
  const chart=document.querySelector('#graph').getBoundingClientRect(),headings=Array.from(document.querySelectorAll('.tau-constellation-subject'));
  return headings.length===13&&headings.every(e=>{
   const box=e.getBoundingClientRect(),text=e.querySelector('text'),matrix=text?.getScreenCTM();
   return getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden'&&box.width>0&&box.height>0&&box.left>=chart.left-2&&box.right<=chart.right+2&&box.top>=chart.top-2&&box.bottom<=chart.bottom+2&&matrix&&Math.hypot(matrix.c,matrix.d)*parseFloat(getComputedStyle(text).fontSize)>=10;
  });
 }"""))
 record('No old lung geometry remains',page.locator('.tau-vessel,.tau-vessel-lobe,.tau-lobe').count()==0)
 record('Sector routes account for every real cross-area dependency once',sector_routes_match_dependencies(page))
 page.locator('#stats-button').click()
 record('Mission status uses unique leaf totals',page.locator('#stats-scope').inner_text().endswith('1,543 tracked leaf layers'))
 record('Mission status distinguishes 4 states',page.locator('#stats-summary .metric.complete strong').inner_text()=='36' and page.locator('#stats-summary .metric.active strong').inner_text()=='49' and page.locator('#stats-summary .metric.unknown strong').inner_text()=='1,352')
 record('All 13 mathematical areas have progress ledgers',page.locator('#area-progress .area-stat').count()==13)
 page.screenshot(path=str(ROOT/'preview-stats.png'),animations='disabled');page.locator('#close-stats').click()
 page.locator('#activity-filter').select_option('active')
 record('Activity filter shows only active roadmaps',page.evaluate("TauExplorer.getGraph().nodes.length>0 && TauExplorer.getGraph().nodes.length<180 && TauExplorer.getGraph().nodes.every(n=>TauExplorer.progress.roadmap(n.id).active>0)"))
 page.locator('#activity-filter').select_option('all')
 page.evaluate("TauExplorer.navigate({view:'neighbors',id:'AnalyticNumberTheory',selected:'AnalyticNumberTheory',tab:'links'})")
 page.locator('.connection-card').first.locator('summary').click()
 record('Roadmap connections expose supporting layer pairs',page.locator('.connection-witness').count()>0)
 page.evaluate("TauExplorer.navigate({view:'all',id:null,selected:null,references:true})")
 record('Related-plan links are dotted without prerequisite arrows',page.locator('.tau-reference-edge').count()>0 and page.evaluate("Array.from(document.querySelectorAll('.tau-reference-edge')).every(e=>!e.getAttribute('marker-end') && e.getAttribute('stroke-dasharray'))"))
 page.evaluate("TauExplorer.navigate({references:false})")
 page.evaluate("TauExplorer.openItem('AnalyticNumberTheory')")
 page.locator('.pin-button').click()
 record('Roadmap can be pinned',page.locator('#pinned-list .pin-item').count()==1)
 page.reload(wait_until='load');page.wait_for_function('!!window.TauExplorer')
 record('Pinned roadmap persists',page.locator('.pin-button').get_attribute('aria-pressed')=='true')
 page.locator('#activity-filter').select_option('pinned')
 record('Pinned filter returns saved roadmap',page.evaluate("TauExplorer.getGraph().nodes.length===1 && TauExplorer.getGraph().nodes[0].id==='AnalyticNumberTheory'"))
 page.locator('#activity-filter').select_option('all')
 page.evaluate("TauExplorer.openReader('tauceti:TauCetiRoadmap/ModularForms')")
 internal=page.locator('#reader-body [data-doc-link]').all()
 linked=False
 for link in internal:
  raw=link.get_attribute('data-doc-link')
  if raw and 'README.md' in raw and not raw.startswith(('http','file','#')):
   before=page.locator('#reader-title').inner_text();link.click()
   if page.locator('#reader-title').inner_text()!=before:linked=True;break
 record('Embedded roadmap document links resolve',linked)
 page.locator('#close-reader').click()
 if page.evaluate('(TauExplorer.data.documents||[]).length'):
  page.evaluate("TauExplorer.openReader('AnalyticNumberTheory')")
  page.locator('#reader-body [data-doc-link]').filter(has_text='campaign execution protocol').click()
  record('Campaign execution guide is embedded and linked', 'execution' in page.locator('#reader-title').inner_text().lower())
  page.locator('#close-reader').click()
 page.locator('#progress-button').click()
 with page.expect_download() as dl:page.locator('#download-offline').click()
 artifact=ROOT/'verified-offline.html';dl.value.save_as(str(artifact));page.locator('#close-progress').click()
 offline=browser.new_context();op=offline.new_page();op.goto(artifact.as_uri());op.wait_for_function('!!window.TauExplorer')
 record('Offline galaxy and mathematical stars load',op.evaluate("TauExplorer.landmarks.length>3000 && TauExplorer.graph.debugState().layout==='constellations'"))
 record('Downloaded atlas starts independently',op.evaluate('TauExplorer.data.roadmaps.length===180') and op.locator('#pinned-list .pin-item').count()==0)
 offline.close()
 if not desktop_only:
  # A genuine touch viewport exercises mobile input, not only responsive CSS.
  mobile=context.browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
  mp=mobile.new_page();mp.on('pageerror',lambda e:errors.append('mobile: '+str(e)))
  if url.startswith('file:'):
   mp.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
   mp.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
  mp.goto(url,wait_until='load');mp.wait_for_function('!!window.TauExplorer')
  touch=mobile.new_cdp_session(mp)
  record('Phone uses touch input at a real mobile viewport',mp.evaluate('navigator.maxTouchPoints>0 && innerWidth===390'))
  record('Phone overview headings do not overlap each other or controls',headings_clear_controls(mp))
  mp.screenshot(path=str(ROOT/'preview-phone-overview.png'),animations='disabled')
  box=mp.locator('#graph').bounding_box()
  before=mp.evaluate('TauExplorer.getState().view')
  touch_swipe(mp,touch,(box['x']+20,box['y']+25),(box['x']+65,box['y']+65))
  record('One-finger chart pan does not enter a galaxy',mp.evaluate('TauExplorer.getState().view')==before=='all')
  mp.locator('#fit-graph').tap();mp.wait_for_timeout(500)
  mp.locator('[data-node-id="AnalyticNumberTheory"] .tau-star-hit').tap()
  mp.wait_for_function("TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer")
  record('Phone tap enters a roadmap constellation',mp.evaluate("TauExplorer.getState().id==='AnalyticNumberTheory' && TauExplorer.getGraph().nodes.every(n=>n.type==='stage')"))
  mp.wait_for_timeout(500)
  mp.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit').tap()
  mp.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'")
  record('Phone tap enters a layer solar system',mp.evaluate("TauExplorer.graph.debugState().layout==='solar-system'"))
  planet=mp.evaluate("TauExplorer.getGraph().nodes.find(n=>n.type==='landmark').id")
  mp.locator('[data-node-id="'+planet+'"] .tau-star-hit').tap()
  record('Phone tap opens mathematical planet details',mp.locator('.landmark-description').is_visible())
  record('Phone reading pane leaves graph and back navigation visible',mp.locator('.cosmic-back').is_visible() and mp.evaluate("() => {const g=document.querySelector('#graph').getBoundingClientRect(),i=document.querySelector('#inspector').getBoundingClientRect();return g.height>80 && i.height>150 && g.bottom<=i.top+2 && i.bottom<=innerHeight+2}"))
  reading=mp.locator('#inspector-content')
  if reading.evaluate('(e)=>e.scrollHeight>e.clientHeight+10'):
   rb=reading.bounding_box()
   touch_swipe(mp,touch,(rb['x']+rb['width']/2,rb['y']+rb['height']-30),(rb['x']+rb['width']/2,rb['y']+30))
   record('Phone mathematical details scroll with touch',reading.evaluate('(e)=>e.scrollTop>0'))
  record('Phone mathematical text has a readable size and no page overflow',mp.locator('.landmark-description').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)>=12') and mp.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  next_planet=mp.evaluate("TauExplorer.getGraph().nodes.filter(n=>n.type==='landmark')[1].id")
  mp.locator('[data-node-id="'+next_planet+'"] .tau-star-hit').tap()
  record('Selecting another planet starts its explanation at the top',reading.evaluate('(e)=>e.scrollTop===0') and mp.evaluate('TauExplorer.getState().selected')==next_planet)
  record('Portrait phone solar captions do not overlap',captions_do_not_overlap(mp))
  mp.screenshot(path=str(ROOT/'preview-phone-planet.png'),animations='disabled')
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer");mp.wait_for_timeout(500)
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='all'")
  record('Phone back buttons retrace both levels while details are open',mp.evaluate("!TauExplorer.getState().layer && TauExplorer.getGraph().nodes.length===196"))

  # A second common phone width runs a full pinch-to-dive and pinch-to-ascend route.
  mp.set_viewport_size({'width':375,'height':812});mp.locator('#fit-graph').tap()
  record('Narrow phone overview headings do not overlap each other or controls',headings_clear_controls(mp))
  mp.screenshot(path=str(ROOT/'preview-phone-narrow-overview.png'),animations='disabled')
  record('Two-finger pinch enters a galaxy on a narrow phone',pinch_until(mp,touch,'[data-node-id="AnalyticNumberTheory"] .tau-star-hit',3,"TauExplorer.getState().id==='AnalyticNumberTheory' && TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer"))
  record('Two-finger pinch enters a layer on a narrow phone',pinch_until(mp,touch,'[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit',3,"TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0' && TauExplorer.graph.debugState().layout==='solar-system'"))
  record('Narrow phone solar system stays finite and readable',finite_chart(mp) and mp.locator('.cosmic-back').is_visible())
  record('Narrow phone solar captions do not overlap',captions_do_not_overlap(mp,minimum=0))
  mp.screenshot(path=str(ROOT/'preview-phone-solar-system.png'),animations='disabled')
  record('Pinching out returns to the roadmap',pinch_until(mp,touch,'#graph',.3,"TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer"))
  record('Pinching out returns to the galaxy field',pinch_until(mp,touch,'#graph',.3,"TauExplorer.getState().view==='all' && !TauExplorer.getState().layer"))

  # Coarse-pointer landscape uses a side reading pane, keeping the sky available.
  mp.set_viewport_size({'width':844,'height':390});mp.locator('#fit-graph').tap();mp.wait_for_timeout(900)
  record('Landscape phone overview headings do not overlap each other or controls',headings_clear_controls(mp))
  mp.screenshot(path=str(ROOT/'preview-phone-landscape-overview.png'),animations='disabled')
  mp.locator('[data-node-id="AnalyticNumberTheory"] .tau-star-hit').tap()
  mp.wait_for_function("TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer");mp.wait_for_timeout(500)
  mp.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit').tap()
  mp.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'");mp.wait_for_timeout(500)
  planet=mp.evaluate("TauExplorer.getGraph().nodes.find(n=>n.type==='landmark').id")
  mp.locator('[data-node-id="'+planet+'"] .tau-star-hit').tap()
  record('Landscape phone opens a mathematical planet',mp.locator('.landmark-description').is_visible())
  record('Landscape phone preserves readable chart and back navigation',mp.locator('.cosmic-back').is_visible() and mp.evaluate("() => {const g=document.querySelector('#graph').getBoundingClientRect(),i=document.querySelector('#inspector').getBoundingClientRect();return g.width>200 && g.height>70 && i.width>240 && i.height>180 && g.right<=i.left+2}"))
  record('Landscape phone has no horizontal page overflow',mp.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  record('Landscape phone solar captions do not overlap',captions_do_not_overlap(mp))
  mp.screenshot(path=str(ROOT/'preview-phone-landscape.png'),animations='disabled')
  mp.locator('.cosmic-back').tap();mp.wait_for_function("!TauExplorer.getState().layer");mp.wait_for_timeout(500)
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='all'")
  record('Landscape phone back controls remain tappable',mp.locator('#catalogue-button').is_visible())
  mp.set_viewport_size({'width':375,'height':812})
  mp.locator('#catalogue-button').tap()
  record('Phone view has working browse/search',mp.locator('#search').is_visible())
  mp.locator('#search').fill('Perron');record('Phone search returns topics',mp.locator('.search-hit').count()>0)
  mp.locator('.search-hit').first.tap();record('Phone selection dismisses index',not mp.locator('#search').is_visible())
  mp.screenshot(path=str(ROOT/'preview-phone.png'),animations='disabled')
  mobile.close()

  # Exercise WebKit when its browser is already installed; never download one.
  if Path(p.webkit.executable_path).exists():
   safari=p.webkit.launch(headless=True)
   sc=safari.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
   sp=sc.new_page();sp.on('pageerror',lambda e:errors.append('webkit: '+str(e)))
   sp.goto(url,wait_until='load');sp.wait_for_function('!!window.TauExplorer')
   sp.locator('[data-node-id="AnalyticNumberTheory"] .tau-star-hit').tap()
   sp.wait_for_function("TauExplorer.getState().view==='roadmap'");sp.wait_for_timeout(500)
   sp.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-star-hit').tap()
   sp.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'")
   planet=sp.evaluate("TauExplorer.getGraph().nodes.find(n=>n.type==='landmark').id")
   sp.locator('[data-node-id="'+planet+'"] .tau-star-hit').tap()
   record('Installed WebKit supports mobile galaxy, layer and planet taps',sp.locator('.landmark-description').is_visible() and sp.locator('.cosmic-back').is_visible())
   sp.screenshot(path=str(ROOT/'preview-webkit-phone.png'),animations='disabled');safari.close()
 page.evaluate("TauExplorer.openItem('AnalyticNumberTheory')")
 page.set_viewport_size({'width':900,'height':800});page.screenshot(path=str(ROOT/'preview-narrow.png'),animations='disabled')
 record('Narrow desktop view usable',page.locator('#inspector').is_visible())
 record('Markdown rejects unsafe HTML and schemes',page.evaluate("""() => {const f=TauMarkdown.render('<img src=x onerror=alert(1)>\\n\\n[x](javascript:alert(1))');const d=document.createElement('div');d.append(f);return !d.querySelector('img,script,iframe')&&!Array.from(d.querySelectorAll('a')).some(a=>a.href.startsWith('javascript:'))}"""))
 page.evaluate("TauExplorer.openItem('GeometricSatakeAndFusion')")
 record('Layer order respects internal prerequisites',page.evaluate("() => {const d=TauExplorer.graph.debugState().positions;const index=new Map(d.map((n,i)=>[n.id,i]));const data=TauExplorer.data;const ids=new Set(data.roadmaps.find(r=>r.id==='GeometricSatakeAndFusion').stages);const positions=new Map(d.map(n=>[n.id,n]));return TauExplorer.getGraph().edges.filter(e=>ids.has(e.source)&&ids.has(e.target)).every(e=>Number.isInteger(positions.get(e.source).rank) && positions.get(e.source).rank<positions.get(e.target).rank);}"))
 page.locator('#close-inspector').click()
 page.get_by_label('Show outside dependencies',exact=True).check()
 record('Outside prerequisite stars stay mathematical and within a usable chart',page.evaluate("TauExplorer.graph.debugState().positions.every(n=>Number.isFinite(n.x)&&Math.abs(n.x)<10000 && TauExplorer.isMathematicalStage(n.id))"))
 page.evaluate("TauExplorer.navigate({view:'all',id:null,selected:null,origin:'all',outside:false})")
 svg=page.evaluate('TauExplorer.graph.exportSVG()')
 svgpath=ROOT/'verified-galaxies.svg';svgpath.write_text(svg)
 record('SVG export contains galaxy artwork and no scripts', 'tau-galaxy-glow' in svg and '<script' not in svg and 'file:///' not in svg)
 svgp=page.context.new_page();svgp.goto(svgpath.as_uri());record('SVG export opens independently',svgp.locator('svg').count()==1);svgp.close()
 record('No application exceptions',not errors)
 if url.startswith('file:'):record('No network requests needed',not requests)
 browser.close()
report={'url':url,'checks':results,'pageErrors':errors,'externalRequests':requests,'result':'PASS','scope':'desktop' if desktop_only else 'desktop and mobile'}
(ROOT/'BROWSER_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
print('Screenshots and report:',ROOT)
