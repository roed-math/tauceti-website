from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import json,math,time,sys,tempfile
REPO=Path(__file__).resolve().parents[1]
ROOT=Path(tempfile.mkdtemp(prefix='tauceti-browser-'))
url=next((arg for arg in sys.argv[1:] if not arg.startswith('--')),(REPO/'index.html').as_uri())
desktop_only='--desktop-only' in sys.argv[1:]
references_only='--references-only' in sys.argv[1:]
overview_only='--overview-only' in sys.argv[1:]
FORMULA_PLANET='EllipticKTheory:E.2::landmark:k-0-x-xrightarrow-sim-mathbb-z-oplus-opera-e9le4x'
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
def pinch_gesture(page, session, selector, scale):
 # One two-finger gesture on the chosen object, without any expectation.
 target=page.locator(selector).first.bounding_box();chart=page.locator('#graph').bounding_box()
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
 page.wait_for_timeout(400)
 return True
def reference_sources_are_exact(page, planet_id):
 return page.evaluate(r"""id => {
  const item=TauExplorer.landmarks.find(x=>x.id===id),entries=Object.values(TauExplorer.references.forLandmark(item)).flat();
  return entries.length>0&&entries.every(entry=>{
   const doc=TauExplorer.data.roadmaps.find(x=>x.sourcePath===entry.sourcePath);
   if(!doc||!Number.isInteger(entry.sourceLine)||entry.sourceLine<1)return false;
   const lines=doc.readme.split('\n'),length=entry.text.split('\n').length;
   return lines.slice(entry.sourceLine-1,entry.sourceLine-1+length).join('\n').includes(entry.text);
  });
 }""",planet_id)
def run_reference_checks(page,browser):
 global mp
 # This desktop fixture is independent of the preceding narrow-window check.
 page.set_viewport_size({'width':1600,'height':1000})
 page.wait_for_timeout(500)
 # A formula with no narrower citation must expose the roadmap bibliography as
 # wider reading, while preserving the mathematical statement and source record.
 page.evaluate("TauExplorer.openStage('EllipticKTheory:E.2')");page.wait_for_timeout(700)
 page.locator('[data-node-id="'+FORMULA_PLANET+'"] .tau-hit').click()
 reading=page.locator('#inspector .planet-references')
 record('Planet references distinguish wider reading from an exact topic citation',reading.is_visible() and page.evaluate("id => {const item=TauExplorer.landmarks.find(x=>x.id===id),refs=TauExplorer.references.forLandmark(item);return !refs.direct.length&&!refs.layer.length&&refs.roadmap.length>0}",FORMULA_PLANET) and reading.locator('[data-reference-scope="direct"],[data-reference-scope="layer"]').count()==0 and reading.locator('[data-reference-scope="roadmap"] h4').inner_text()=='Roadmap reading')
 text=reading.inner_text()
 record('Curve K-theory displays its recorded bibliography without inventing precision',all(name in text for name in ['Weibel V','Handbook II.2 and II.3','Bloch','Higher regulators','Thomason–Trobaugh']))
 record('Reference lookup preserves the named planet and typeset mathematics',page.locator('.landmark-description math').count()>0 and page.evaluate(r"""id => {const item=TauExplorer.landmarks.find(x=>x.id===id);return item.title.includes('\\operatorname{Pic}')&&item.description===item.sourceExcerpt&&TauExplorer.landmarkTitle(item)==='Curve rank–determinant decomposition'&&TauExplorer.getState().selected===id}""",FORMULA_PLANET))
 record('Curve K-theory citations point to the exact embedded source line',reference_sources_are_exact(page,FORMULA_PLANET))
 record('Recorded bibliography metadata expands work titles and public links',reading.locator('.reference-works').count()>0 and all(name in reading.locator('.reference-works').inner_text() for name in ['Charles A. Weibel','The K-book: An introduction to algebraic K-theory','Handbook of K-theory','Robert Thomason','Thomas Trobaugh','Higher Algebraic K-Theory of Schemes and of Derived Categories']) and reading.locator('.reference-works a[href="https://sites.math.rutgers.edu/~weibel/Kbook.html"]').count()==1)
 record('Reference links do not expose local reference PDFs',reading.evaluate(r"""e => Array.from(e.querySelectorAll('a')).every(a=>{const href=a.getAttribute('href')||'';return !/^file:/i.test(href)&&(!/\.pdf(?:[?#]|$)/i.test(href)||/^https?:\/\//i.test(href))})"""))
 reading.locator('.reference-source').first.scroll_into_view_if_needed()
 page.screenshot(path=str(ROOT/'preview-planet-references.png'),animations='disabled')
 reading.locator('.reference-source').first.click()
 record('A planet reference opens its owning roadmap source',page.locator('#reader[open]').is_visible() and page.locator('#reader-title').inner_text()=='K-theory of curves and elliptic curves' and 'Weibel V; Handbook II.2 and II.3' in page.locator('#reader-body').inner_text())
 page.locator('#close-reader').click()

 # An explicit paper in a TauCeti target belongs to that topic, not to every
 # target in the roadmap. Its public paper link and local source stay separate.
 topic='tauceti:TauCetiRoadmap/CombinatorialHeegaardFloer#milestone-g-7::landmark:k-u-k-1csrgny'
 page.evaluate("TauExplorer.openStage('tauceti:TauCetiRoadmap/CombinatorialHeegaardFloer#milestone-g-7')");page.wait_for_timeout(700)
 page.locator('[data-node-id="'+topic+'"] .tau-hit').click()
 direct=page.locator('.planet-references [data-reference-scope="direct"]')
 record('A TauCeti mathematical target exposes its explicit topic reference',direct.locator('h4').inner_text()=='For this topic' and 'Milnor conjecture' in direct.inner_text() and direct.locator('a[href="https://arxiv.org/abs/1011.5265"]').count()==1 and reference_sources_are_exact(page,topic))
 direct.locator('.reference-source').first.click()
 record('TauCeti topic citation opens its preserved roadmap passage',page.locator('#reader[open]').is_visible() and 'Milnor conjecture' in page.locator('#reader-body').inner_text() and 'Combinatorial' in page.locator('#reader-title').inner_text())
 page.locator('#close-reader').click()

 layer_topic='AInfCohomology:AI.0::landmark:common-integral-perfectoid-ring-and-witt-v-1vm5fxh'
 page.evaluate("TauExplorer.openStage('AInfCohomology:AI.0')");page.wait_for_timeout(700)
 page.locator('[data-node-id="'+layer_topic+'"] .tau-hit').click()
 layer=page.locator('.planet-references [data-reference-scope="layer"]')
 record('Layer source locators are labelled separately from direct topic citations',layer.locator('h4').inner_text()=='For this layer' and 'BMS1 §3; BS22 §§2–3,17' in layer.inner_text() and page.locator('.planet-references [data-reference-scope="direct"]').count()==0)

 empty='AbelianSchemesAndArithmeticModuli:A1::landmark:relative-dimension-as-locally-constant-all-13bhoef'
 page.evaluate("TauExplorer.openStage('AbelianSchemesAndArithmeticModuli:A1')");page.wait_for_timeout(700)
 page.locator('[data-node-id="'+empty+'"] .tau-hit').click()
 record('A target without recorded references says so without invented reading',page.evaluate("id => Object.values(TauExplorer.references.forLandmark(TauExplorer.landmarks.find(x=>x.id===id))).every(items=>!items.length)",empty) and page.locator('.planet-references .detail-note').inner_text()=='No bibliography is listed for this topic in the embedded roadmap.' and page.locator('.planet-references .planet-reference,.planet-references a,.planet-references .reference-source').count()==0)

 if not desktop_only:
  mobile=browser.new_context(viewport={'width':375,'height':812},device_scale_factor=2,is_mobile=True,has_touch=True)
  mp=mobile.new_page();mp.on('pageerror',lambda e:errors.append('mobile references: '+str(e)))
  if url.startswith('file:'):
   mp.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
   mp.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
  mp.goto(url,wait_until='load');mp.wait_for_function('!!window.TauExplorer')
  mp.evaluate("TauExplorer.openStage('EllipticKTheory:E.2')");mp.wait_for_timeout(800)
  mp.locator('[data-node-id="'+FORMULA_PLANET+'"] .tau-hit').tap()
  touch=mobile.new_cdp_session(mp)
  panel=mp.locator('#inspector-content');button=mp.locator('.planet-references .reference-source').first
  def reference_button_in_view():
   target=button.bounding_box();bounds=panel.bounding_box()
   return bool(target and bounds and target['y']>=bounds['y'] and target['y']+target['height']<=bounds['y']+bounds['height'])
  for _ in range(12):
   if reference_button_in_view():break
   bounds=panel.bounding_box();x=bounds['x']+bounds['width']/2;y=bounds['y']+bounds['height']-25
   touch_swipe(mp,touch,(x,y),(x,max(bounds['y']+25,y-125)))
  record('Phone users can scroll to planet references with touch',reference_button_in_view() and panel.evaluate('(e)=>e.scrollTop>0') and mp.evaluate('navigator.maxTouchPoints>0'))
  record('Phone bibliography remains readable without covering navigation',mp.locator('.planet-references .reference-text').first.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)>=12') and mp.locator('.cosmic-back').is_visible() and mp.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  mp.screenshot(path=str(ROOT/'preview-phone-planet-references.png'),animations='disabled')
  button.tap()
  record('Phone tap opens the embedded citation source',mp.locator('#reader[open]').is_visible() and mp.locator('#reader-title').inner_text()=='K-theory of curves and elliptic curves' and 'Thomason–Trobaugh' in mp.locator('#reader-body').inner_text())
  mp.locator('#close-reader').tap()
  record('Closing a citation reader preserves the selected planet',mp.evaluate('TauExplorer.getState().selected')==FORMULA_PLANET and mp.locator('.landmark-description math').count()>0)
  mobile.close()
def write_report(scope):
 report={'url':url,'checks':results,'pageErrors':errors,'externalRequests':requests,'result':'PASS','scope':scope}
 (ROOT/'BROWSER_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
 print('Screenshots and report:',ROOT)
BUILD=json.loads((REPO/'BUILD.json').read_text()) if (REPO/'BUILD.json').exists() else {}
def debug(page):return page.evaluate('TauExplorer.graph.debugState()')
def label_boxes(page):
 return page.evaluate("""() => Array.from(document.querySelectorAll('.tau-layer-label g.tau-label')).map(g=>{const t=g.querySelector('text'),b=t.getBoundingClientRect(),m=t.getScreenCTM();return {id:g.getAttribute('data-label-for'),kind:Array.from(g.classList).find(c=>c.startsWith('tau-label-')&&c!=='tau-label-hit').replace('tau-label-',''),x:b.left,y:b.top,w:b.width,h:b.height,font:m?Math.hypot(m.c,m.d)*parseFloat(getComputedStyle(t).fontSize):0,text:t.textContent};})""")
def labels_are_clean(page,minimum_font=8):
 # No two drawn labels overlap, every drawn label is legible and inside the chart.
 chart=page.locator('#graph').bounding_box();boxes=label_boxes(page);collisions=[]
 discs=page.evaluate("""() => Array.from(document.querySelectorAll('.tau-planet-body, .tau-star-core')).map(c=>{const b=c.getBoundingClientRect(),g=c.closest('[data-node-id]');return {id:g?g.getAttribute('data-node-id'):'',x:b.left+b.width/2,y:b.top+b.height/2,r:b.width/2};}).filter(d=>d.r>=3)""")
 overlays=page.evaluate("""() => Array.from(document.querySelectorAll('.graph-tools, .graph-hint')).map(e=>e.getBoundingClientRect()).filter(b=>b.width>0&&b.height>0).map(b=>({x:b.left,y:b.top,w:b.width,h:b.height}))""")
 for i,a in enumerate(boxes):
  if a['font']<minimum_font:collisions.append({'first':a['id'],'second':'illegible','font':a['font']})
  if a['x']<chart['x']-2 or a['x']+a['w']>chart['x']+chart['width']+2 or a['y']<chart['y']-2 or a['y']+a['h']>chart['y']+chart['height']+2:collisions.append({'first':a['id'],'second':'chart boundary'})
  for b in boxes[i+1:]:
   if min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])>1 and min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])>1:collisions.append({'first':a['id'],'second':b['id']})
  # Text never runs across another object's disc, nor behind the corner controls.
  for d in discs:
   if d['id']!=a['id'] and math.hypot(max(a['x'],min(d['x'],a['x']+a['w']))-d['x'],max(a['y'],min(d['y'],a['y']+a['h']))-d['y'])<d['r']-1:collisions.append({'first':a['id'],'second':'disc '+d['id']})
  for o in overlays:
   if min(a['x']+a['w'],o['x']+o['w'])-max(a['x'],o['x'])>1 and min(a['y']+a['h'],o['y']+o['h'])-max(a['y'],o['y'])>1:collisions.append({'first':a['id'],'second':'controls'})
 page.evaluate('c => { window.__tauTestCaptionCollisions=c; }',collisions)
 return not collisions
def names_are_unique(page):
 return page.evaluate("""() => { const seen=new Map(); for(const g of document.querySelectorAll('.tau-layer-label g.tau-label')){const id=g.getAttribute('data-label-for');seen.set(id,(seen.get(id)||0)+1);} const dup=Array.from(seen.entries()).filter(([,n])=>n>1); window.__tauTestCaptionCollisions=dup; return !dup.length; }""")
def legend_matches_map_encoding(page):
 # Colour encodes recorded progress only. A roadmap without any recorded
 # status is drawn as an open ring, never coloured as though it were planned.
 return page.evaluate("""() => {
  const beacon=id=>document.querySelector('[data-node-id="'+CSS.escape(id)+'"] .tau-beacon');
  const blank=beacon('AnalyticNumberTheory'),done=beacon('tauceti:Completed/EffectiveBounds'),d=TauExplorer.graph.debugState();
  const blankNode=d.constellations.find(n=>n.id==='AnalyticNumberTheory'),doneNode=d.constellations.find(n=>n.id==='tauceti:Completed/EffectiveBounds');
  const keys=Array.from(document.querySelectorAll('.progress-legend span')).map(e=>e.textContent.trim()),groupColours=TauExplorer.data.groups.map(g=>g.color.toLowerCase());
  return !!blank&&!!done&&blankNode.hasProgress===false&&doneNode.progress===100&&blank.getAttribute('fill')==='#0b1016'&&blank.getAttribute('stroke')==='#6f7f8c'&&done.getAttribute('fill')===doneNode.accent&&doneNode.accent==='#f7f3e9'
   &&keys.includes('No progress data')&&keys.includes('Not started')&&keys.includes('Complete')&&!!document.querySelector('.progress-legend .none')&&d.constellations.filter(n=>!n.hasProgress).every(n=>!groupColours.includes(n.accent.toLowerCase()));
 }""")
def fit_all(page,touch=False):
 if touch:page.locator('#fit-graph').tap()
 else:page.locator('#fit-graph').click()
 page.wait_for_timeout(500)
def check_overview(page,scope,touch=False):
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null,origin:'all',activity:'all',unmapped:true,references:false})");page.wait_for_timeout(700)
 d=debug(page)
 record(scope+' universe holds every galaxy, roadmap, layer and planet',d['layout']=='universe' and d['counts']['galaxies']==BUILD['areasWithRoadmaps'] and d['counts']['constellations']==BUILD['roadmaps'] and d['counts']['stars']==BUILD.get('mathematicalStars',1594)-BUILD.get('sourceRefinements',0) and d['counts']['planets']>=3440-BUILD.get('hiddenPlanets',0))
 record(scope+' overview resolves no stars or planets and stays light',d['visible']['resolved']==0 and d['visible']['stars']==0 and d['visible']['planets']==0 and d['rendered']<600)
 record(scope+' overview draws every roadmap as a point',page.locator('.tau-constellation').count()==BUILD['roadmaps'] and page.locator('.tau-unmapped-node').count()==0)
 # A heading waits for room rather than overlap. A large chart holds every
 # subject heading; a phone-width chart may hold back up to 15% of them and a
 # chart under 400px tall up to 40%, which reappear as the camera closes in.
 headings=page.locator('.tau-label-galaxy').count();box=page.locator('#graph').bounding_box();areas=BUILD['areasWithRoadmaps']
 allowed=math.ceil(areas*.4) if box['height']<400 else math.ceil(areas*.15) if box['width']<600 else 0
 record(scope+' every subject heading is drawn once, legibly, without overlap',headings>=areas-allowed and labels_are_clean(page) and names_are_unique(page))
 record(scope+' universe fits inside the chart',page.evaluate("() => { const d=TauExplorer.graph.debugState(),t=d.transform,g=document.querySelector('#graph').getBoundingClientRect(); const u=TauExplorer.getUniverse().bounds; const x0=u.x*t.k+t.x,x1=(u.x+u.w)*t.k+t.x,y0=u.y*t.k+t.y,y1=(u.y+u.h)*t.k+t.y; return x0>=-2&&x1<=g.width+2&&y0>=-2&&y1<=g.height+2; }"))
 record(scope+' no links are drawn until something is selected',page.locator('.tau-link').count()==0 and page.evaluate("Array.from(document.querySelectorAll('.tau-route')).every(e=>Number(e.getAttribute('opacity'))===0)"))
 record(scope+' legend colours match the map encoding',legend_matches_map_encoding(page))
 record(scope+' page has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
def check_hover_links(page):
 heading=page.locator('.tau-label-galaxy').first
 heading.hover();page.wait_for_timeout(200)
 own=page.evaluate("() => { const id=document.querySelector('.tau-label-galaxy').getAttribute('data-label-for'); const routes=Array.from(document.querySelectorAll('.tau-route')); const mine=routes.filter(r=>r.dataset.sourceArea===id||r.dataset.targetArea===id); return mine.length>0&&mine.every(r=>Number(r.getAttribute('opacity'))>=.5)&&routes.filter(r=>!mine.includes(r)).every(r=>Number(r.getAttribute('opacity'))===0); }")
 page.mouse.move(5,5);page.wait_for_timeout(200)
 record('Hovering an area heading reveals only that area\'s routes',own and page.evaluate("Array.from(document.querySelectorAll('.tau-route')).every(e=>Number(e.getAttribute('opacity'))===0)"))
def check_zoom_journey(page,scope):
 # A continuous wheel zoom carries the reader from the universe into one
 # galaxy, one constellation and one star system, and the address follows.
 fit_all(page)
 home=page.evaluate("TauExplorer.data.roadmaps.find(r=>r.id==='AnalyticNumberTheory').group")
 record(scope+' wheel zoom enters a galaxy',wheel_until(page,'.tau-galaxy[data-node-id="%s"] ellipse'%home,-300,"TauExplorer.getState().view==='group' && TauExplorer.getState().id==='%s'"%home,attempts=14))
 page.wait_for_timeout(400)
 record(scope+' inside a galaxy its constellations resolve into stars',wheel_until(page,'.tau-galaxy[data-node-id="%s"] ellipse'%home,-200,"(() => { const d=TauExplorer.graph.debugState(); return d.visible.resolved>0 && d.visible.stars>0; })()",attempts=6))
 record(scope+' wheel zoom enters a roadmap constellation',wheel_until(page,'[data-node-id="AnalyticNumberTheory"] .tau-hit',-300,"TauExplorer.getState().view==='roadmap' && TauExplorer.getState().id==='AnalyticNumberTheory' && !TauExplorer.getState().layer",attempts=14))
 record(scope+' constellation names and star names are legible and disjoint',labels_are_clean(page) and names_are_unique(page))
 record(scope+' wheel zoom enters a star system',wheel_until(page,'[data-node-id="AnalyticNumberTheory:AN.0"] .tau-hit',-300,"TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'",attempts=14))
 record(scope+' a star system shows its planets',page.locator('.tau-planet').count()>0 and page.locator('.tau-orbit').count()>0)
 page.screenshot(path=str(ROOT/('preview-'+scope.lower().replace(' ','-')+'-star-system.png')),animations='disabled')
 record(scope+' wheel zoom out returns to the roadmap',wheel_until(page,'#graph',300,"TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer",attempts=14))
 record(scope+' wheel zoom out returns to the universe',wheel_until(page,'#graph',300,"TauExplorer.getState().view==='all'",attempts=20))
def check_click_journey(page,scope):
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null})");page.wait_for_timeout(600)
 page.locator('[data-node-id="AnalyticNumberTheory"] .tau-hit').click()
 page.wait_for_function("TauExplorer.getState().view==='roadmap' && TauExplorer.getState().id==='AnalyticNumberTheory'");page.wait_for_timeout(500)
 record(scope+' clicking a roadmap point travels into its constellation',page.evaluate("() => { const d=TauExplorer.graph.debugState(); return d.focus.level==='constellation' && d.visible.stars>=10; }") and page.locator('#selection-kind').inner_text()=='Campaign roadmap')
 record(scope+' the selected roadmap shows its own links',page.locator('.tau-link').count()==page.evaluate("TauExplorer.data.edges.filter(e=>e.source==='AnalyticNumberTheory'||e.target==='AnalyticNumberTheory').length"))
 page.screenshot(path=str(ROOT/('preview-'+scope.lower().replace(' ','-')+'-constellation.png')),animations='disabled')
 page.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-hit').click()
 page.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'");page.wait_for_timeout(500)
 record(scope+' clicking a star travels to its system and opens the layer',page.locator('#selection-kind').inner_text()=='Layer' and page.locator('.tau-planet').count()>0)
 record(scope+' the selected star shows exactly its prerequisite and consumer links',page.locator('.tau-link').count()==page.evaluate("() => { const stars=new Set(TauExplorer.getUniverse().stars.map(s=>s.id)); return TauExplorer.data.stageEdges.filter(e=>(e.source==='AnalyticNumberTheory:AN.0'||e.target==='AnalyticNumberTheory:AN.0')&&stars.has(e.source)&&stars.has(e.target)).length; }"))
 planet=page.evaluate("TauExplorer.getUniverse().stars.find(s=>s.id==='AnalyticNumberTheory:AN.0').planetIds[0]")
 page.locator('[data-node-id="'+planet+'"] .tau-hit').click();page.wait_for_timeout(400)
 record(scope+' clicking a planet reads its mathematics',page.locator('.landmark-description').is_visible() and len(page.locator('.landmark-description').inner_text())>20 and page.evaluate("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'"))
 page.screenshot(path=str(ROOT/('preview-'+scope.lower().replace(' ','-')+'-planet.png')),animations='disabled')
 page.locator('.cosmic-back').click();page.wait_for_function("!TauExplorer.getState().layer");page.wait_for_timeout(400)
 page.locator('.cosmic-back').click();page.wait_for_function("TauExplorer.getState().view==='group'");page.wait_for_timeout(400)
 page.locator('.cosmic-back').click();page.wait_for_function("TauExplorer.getState().view==='all'");page.wait_for_timeout(400)
 record(scope+' back steps out through roadmap and area to the universe',page.evaluate("TauExplorer.graph.debugState().focus.level==='all'"))
 page.locator('.tau-graph').click(position={'x':8,'y':8});page.wait_for_timeout(200)
 record(scope+' clicking empty sky clears the selection and its links',page.evaluate("TauExplorer.getState().selected===null") and page.locator('.tau-link').count()==0)
def check_refinements(page):
 page.evaluate("TauExplorer.navigate({view:'roadmap',id:'PadicFamilies',layer:'PadicFamilies:L2a',selected:'PadicFamilies:L2a'})");page.wait_for_timeout(800)
 expected=page.evaluate("TauExplorer.data.stages.filter(s=>s.expansion&&s.parentStageId==='PadicFamilies:L2a').length")
 record('Reviewed source refinements orbit their layer as planets',expected==14 and page.locator('.tau-planet[data-node-id*="/"]').count()==expected)
 record('Refinements are excluded from progress denominators',page.evaluate("TauExplorer.progress.roadmapLeaves('PadicFamilies').every(id=>!id.includes('/')) && TauExplorer.progress.stage('PadicFamilies:L2a/spectral-hypersurface').status==='unknown'"))
 page.locator('.tau-planet[data-node-id="PadicFamilies:L2a/spectral-hypersurface"] .tau-hit').click();page.wait_for_timeout(400)
 record('A refinement planet explains its statement, sources and unchecked status',page.locator('#selection-kind').inner_text()=='Construction · source refinement' and 'Fredholm' in page.locator('.detail-title').inner_text() and page.locator('#inspector-content .reference-works a').count()>0 and 'unchecked' in page.locator('#inspector-content').inner_text())
 record('A layer lists its source decomposition beside its extracted targets',page.evaluate("() => { TauExplorer.openStage('PadicFamilies:L2a'); return true; }") and (page.wait_for_timeout(400) or True) and 'Source decomposition' in page.locator('#inspector-content').inner_text() and page.locator('#inspector-content .item-link[data-item-id*="/"]').count()==14)
 record('A roadmap summarises its reviewed expansion',page.evaluate("() => { TauExplorer.openItem('PadicFamilies'); return true; }") and (page.wait_for_timeout(500) or True) and 'Source expansion' in page.locator('#inspector-content').inner_text() and 'accepted' in page.locator('#inspector-content').inner_text())
 # Deeper zoom keeps adding structure: kind and excerpt, then the refinement's
 # hypotheses, proof steps and checks as moons, and the links among refinements.
 page.evaluate("TauExplorer.openStage('PadicFamilies:L2a/spectral-hypersurface')");page.wait_for_timeout(600)
 page.evaluate("""() => { const g=TauExplorer.graph,u=TauExplorer.getUniverse(),p=u.byId.get('PadicFamilies:L2a/spectral-hypersurface'),star=u.byId.get(p.starId); const k=g.transformFor({x:star.x-star.room*1.35,y:star.y-star.room*1.35,w:star.room*2.7,h:star.room*2.7}).k*3; g.svg.interrupt(); g.svg.call(g.zoom.transform,d3.zoomIdentity.translate(g.width/2-p.x*k,g.height/2-p.y*k).scale(k)); }""");page.wait_for_timeout(500)
 record('Deep zoom reveals a refinement\'s kind, excerpt, moons and internal links',page.locator('.tau-label-card[data-label-for="PadicFamilies:L2a/spectral-hypersurface"]').count()==1 and page.locator('.tau-moon').count()>0 and page.locator('.tau-system-link').count()>0 and labels_are_clean(page))
 page.screenshot(path=str(ROOT/'preview-deep-zoom.png'),animations='disabled')
 page.screenshot(path=str(ROOT/'preview-refined-layer.png'),animations='disabled')
def check_catalogue_selection(page,scope,touch=False):
 title=page.evaluate("TauExplorer.data.roadmaps.find(r=>r.id==='AnalyticNumberTheory').title")
 if touch:page.locator('#catalogue-button').tap()
 item=page.locator('#catalogue .catalogue-item[title='+json.dumps(title)+']');group=item.locator('xpath=..')
 if not group.evaluate('(e)=>e.open'):
  if touch:group.locator('summary').tap()
  else:group.locator('summary').click()
 if touch:item.scroll_into_view_if_needed();item.tap()
 else:item.click()
 page.wait_for_function("TauExplorer.getState().selected==='AnalyticNumberTheory'&&TauExplorer.getState().view==='roadmap'");page.wait_for_timeout(600)
 record(scope+' catalogue selection travels to the roadmap and names it once',page.locator('.tau-label[data-label-for="AnalyticNumberTheory"]').count()==1 and names_are_unique(page) and page.evaluate("TauExplorer.graph.debugState().focus.id==='AnalyticNumberTheory'"))
 page.screenshot(path=str(ROOT/('preview-'+scope.lower().replace(' ','-')+'-catalogue-selection.png')),animations='disabled')
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null})");page.wait_for_timeout(500)
def check_performance(page):
 fit_all(page)
 t=time.time();page.evaluate("""() => new Promise(resolve => { const g=TauExplorer.graph,s=g.debugState().transform; let step=0; const tick=()=>{ step++; const k=s.k*Math.pow(1.25,step); g.svg.call(g.zoom.transform,d3.zoomIdentity.translate(g.width/2-(g.width/2-s.x)/s.k*k,g.height/2-(g.height/2-s.y)/s.k*k).scale(k)); if(step<16)requestAnimationFrame(tick); else requestAnimationFrame(resolve); }; requestAnimationFrame(tick); })""")
 elapsed=int((time.time()-t)*1000)
 record('Sixteen zoom frames from the universe to a system render quickly',elapsed<2500)
 print('zoom frames ms',elapsed,flush=True)
 fit_all(page)
def run_overview_checks(page,browser):
 global mp
 fit_all(page);page.screenshot(path=str(ROOT/'preview-desktop-universe.png'),animations='disabled')
 check_overview(page,'Desktop');check_hover_links(page);check_catalogue_selection(page,'Desktop')
 if desktop_only:return
 mobile=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
 mp=mobile.new_page();mp.on('pageerror',lambda e:errors.append('mobile overview: '+str(e)))
 if url.startswith('file:'):
  mp.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
  mp.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
 mp.goto(url,wait_until='load');mp.wait_for_function('!!window.TauExplorer')
 for scope,width,height in [('Phone',390,844),('Narrow phone',375,812),('Landscape phone',844,390)]:
  mp.set_viewport_size({'width':width,'height':height});mp.wait_for_timeout(500);fit_all(mp,touch=True)
  mp.screenshot(path=str(ROOT/('preview-'+scope.lower().replace(' ','-')+'-universe.png')),animations='disabled')
  check_overview(mp,scope,touch=True);check_catalogue_selection(mp,scope,touch=True)
 mobile.close()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 context=browser.new_context(viewport={'width':1600,'height':1000},accept_downloads=True)
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 if url.startswith('file:'):
  page.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
  page.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
 page.goto(url,wait_until='load');page.wait_for_function('!!window.TauExplorer',timeout=15000)
 if overview_only:
  run_overview_checks(page,browser)
  record('No application exceptions',not errors)
  if url.startswith('file:'):record('No network requests needed',not requests)
  browser.close();write_report('overview desktop' if desktop_only else 'overview desktop and mobile');sys.exit(0)
 if references_only:
  run_reference_checks(page,browser)
  record('No application exceptions',not errors)
  if url.startswith('file:'):record('No network requests needed',not requests)
  browser.close();write_report('references desktop' if desktop_only else 'references desktop and mobile');sys.exit(0)
 record('Native offline mathematics renders',page.evaluate("() => {const d=TauMarkdown.render('$x^2$');return !!d.querySelector('math')}"))
 record('Snapshot records match the build report',page.evaluate("TauExplorer.data.roadmaps.length===%d && TauExplorer.data.stages.filter(s=>!s.expansion).length===%d && TauExplorer.data.stages.length===%d && TauExplorer.data.stages.filter(s=>s.expansion).length===%d"%(BUILD['roadmaps'],BUILD['originalStages'],BUILD.get('stages',1604),BUILD.get('sourceRefinements',0))))
 check_overview(page,'Desktop');check_hover_links(page);check_performance(page)
 page.screenshot(path=str(ROOT/'preview-overview.png'),animations='disabled')
 record('No placeholder areas are drawn',page.evaluate("TauExplorer.data.opportunities.areas.length===0") and page.locator('.tau-unmapped-node').count()==0 and page.locator('#show-unmapped').count()==0)
 record('A roadmap without status data has a blank progress indicator',page.evaluate("() => {const id='AnalyticNumberTheory',status=TauExplorer.progress.roadmap(id),node=TauExplorer.getGraph().nodes.find(n=>n.id===id);return status.total>0 && status.unknown===status.total && node.progress===null && node.progressLabel===''}"))
 check_zoom_journey(page,'Desktop');check_click_journey(page,'Desktop');check_catalogue_selection(page,'Desktop');check_refinements(page)
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null})");page.wait_for_timeout(500)
 record('Mathematical planets exclude procedural labels',page.evaluate("TauExplorer.landmarks.every(x=>!/^(Dependency|Canonical owner|API to develop|the|Tests|Suggested home)$/i.test(x.title))"))
 record('All roadmap summaries use mathematical prose',page.evaluate("TauExplorer.data.roadmaps.every(r=>r.summary.split(/\\s+/).length>=40 && !/portfolio audit|component implements|silently attributed/.test(r.summary))"))
 page.evaluate("TauExplorer.navigate({view:'roadmap',id:'FoundationsAndLibraryIntegration',layer:null,selected:null,origin:'all',activity:'all',unmapped:true})");page.wait_for_timeout(600)
 record('Administrative library pinning is not a star',page.evaluate("!TauExplorer.isMathematicalStage('FoundationsAndLibraryIntegration:LI.0') && !TauExplorer.getUniverse().byId.has('FoundationsAndLibraryIntegration:LI.0') && TauExplorer.getUniverse().stars.every(s=>TauExplorer.isMathematicalStage(s.id))"))
 record('Hidden administrative layer retains its raw source and progress',page.evaluate("() => {const id='FoundationsAndLibraryIntegration:LI.0',raw=TauExplorer.data.stages.find(s=>s.id===id);return raw.title==='Pinned libraries and declarations' && raw.description.includes('Record Lean, Mathlib, TauCeti and supplier-roadmap commits') && TauExplorer.progress.stage(id).status!==undefined}"))
 page.evaluate("TauExplorer.openReader('FoundationsAndLibraryIntegration')")
 record('Full source document preserves hidden administrative instructions','Pinned libraries and declarations' in page.locator('#reader-body').inner_text())
 page.locator('#close-reader').click()
 pinned_group='tauceti:TauCetiRoadmap/ReductiveGroups#layer-9-pinned-chevalleydemazure-group-schemes-over-ℤ'
 page.evaluate("TauExplorer.openItem('tauceti:TauCetiRoadmap/ReductiveGroups')");page.wait_for_timeout(600)
 record('Mathematical pinned group schemes remain visible',page.evaluate("id => TauExplorer.isMathematicalStage(id) && TauExplorer.getUniverse().byId.has(id) && TauExplorer.getUniverse().byId.get(id).label===TauExplorer.stageTitle(id)",pinned_group))
 page.locator('[data-node-id="'+pinned_group+'"] .tau-hit').click()
 page.wait_for_function("id => TauExplorer.getState().layer===id",arg=pinned_group);page.wait_for_timeout(400)
 record('Pinned group schemes show mathematics before progress controls',page.locator('.stage-description').is_visible() and page.evaluate("id => {const description=document.querySelector('.stage-description'),controls=document.querySelector('.progress-controls');return TauExplorer.stageSummary(id).length>60 && description && controls && description.compareDocumentPosition(controls)&Node.DOCUMENT_POSITION_FOLLOWING}",pinned_group))
 record('Planet label overrides refer to existing mathematical targets',page.evaluate("() => {const ids=new Set(TauExplorer.landmarks.map(x=>x.id)),labels=TauExplorer.data.landmarkLabels;return Object.keys(labels).length>0 && Object.keys(labels).every(id=>ids.has(id))}"))
 page.evaluate("TauExplorer.openStage('EllipticKTheory:E.2')");page.wait_for_timeout(700)
 page.locator('[data-node-id="'+FORMULA_PLANET+'"] .tau-hit').click();page.wait_for_timeout(400)
 record('Formula planet uses a short plain name in the map and SVG',page.evaluate(r"""id => {
  const item=TauExplorer.landmarks.find(x=>x.id===id),title=TauExplorer.presentation.landmarkTitle(item),node=TauExplorer.getUniverse().byId.get(id);
  const svg=new DOMParser().parseFromString(TauExplorer.graph.exportSVG(),'image/svg+xml');
  const caption=Array.from(svg.querySelectorAll('[data-label-for]')).find(e=>e.getAttribute('data-label-for')===id)?.querySelector('text');
  return title==='Curve rank–determinant decomposition'&&title.length<60&&!/[\\${}^_]/.test(title)&&node.label===title&&caption&&caption.textContent.replace(/\s/g,'')===title.replace(/\s/g,'')&&!svg.querySelector('parsererror');
 }""",FORMULA_PLANET))
 record('Opening a named planet renders its preserved source formula',page.locator('.landmark-description math').count()>0 and page.locator('.landmark-description math').first.evaluate('(e)=>e.getBoundingClientRect().width>30 && e.getBoundingClientRect().height>10') and page.locator('.landmark-description .katex-error').count()==0 and page.evaluate(r"""id => {
  const item=TauExplorer.landmarks.find(x=>x.id===id),roadmap=TauExplorer.data.roadmaps.find(x=>x.id===item.roadmapId);
  return item.title.includes('\\operatorname{Pic}')&&item.description===item.sourceExcerpt&&roadmap.readme.includes(item.sourceExcerpt)&&roadmap.readme.split('\n').slice(item.sourceLine-1).join('\n').startsWith(item.sourceExcerpt);
 }""",FORMULA_PLANET))
 page.screenshot(path=str(ROOT/'preview-formula-planet.png'),animations='disabled')
 page.evaluate("TauExplorer.openStage('AnalyticNumberTheory:AN.0')");page.wait_for_timeout(600)
 record('Central layer star exposes progress controls',page.get_by_label('Layer status',exact=True).is_visible())
 record('A stage without status data shows no badge and keeps its raw status',page.evaluate("TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='unknown' && TauExplorer.graph.debugState().stars.find(n=>n.id==='AnalyticNumberTheory:AN.0').progress===null") and page.locator('#inspector .status-chip').count()==0)
 page.get_by_label('Layer status',exact=True).select_option('complete');page.get_by_label('Progress note',exact=True).fill('Browser test evidence')
 page.get_by_role('button',name='Save status',exact=True).click();page.wait_for_timeout(400)
 record('Local update persists and makes the star green',page.evaluate("TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').manual && TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='complete'") and page.locator('#inspector .status-chip').inner_text().endswith('Complete') and page.locator('[data-node-id="AnalyticNumberTheory:AN.0"]').get_attribute('data-progress')=='100')
 page.reload(wait_until='load');page.wait_for_function('!!window.TauExplorer');page.wait_for_timeout(500)
 record('Progress survives reload',page.evaluate("TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='complete'"))
 page.screenshot(path=str(ROOT/'preview-stage.png'),animations='disabled')
 record('Export/reset/import round trip',page.evaluate("""() => {const x=TauExplorer.progress.export();TauExplorer.progress.resetStage('AnalyticNumberTheory:AN.0');const reverted=TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status!=='complete';TauExplorer.progress.import(x);return reverted&&TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='complete'}"""))
 record('Malformed import is atomic',page.evaluate("""() => {const a=JSON.stringify(TauExplorer.progress.export());try{TauExplorer.progress.import({version:1,stages:{bad:{status:'complete'}}});return false}catch{}return a===JSON.stringify(TauExplorer.progress.export())}"""))
 page.evaluate("TauExplorer.progress.resetStage('AnalyticNumberTheory:AN.0')");page.wait_for_timeout(300)
 record('Resetting local progress restores the blank indicator',page.evaluate("TauExplorer.progress.stage('AnalyticNumberTheory:AN.0').status==='unknown' && TauExplorer.graph.debugState().stars.find(n=>n.id==='AnalyticNumberTheory:AN.0').progress===null") and page.locator('#inspector .status-chip').count()==0)
 page.get_by_role('button',name='Read full roadmap',exact=True).click()
 record('Full document readable offline',page.locator('#reader[open]').is_visible() and len(page.locator('#reader-body').inner_text())>3000)
 page.locator('#close-reader').click()
 page.locator('#search').fill('Perron')
 record('Search reaches mathematical roadmap text',page.locator('.search-hit').count()>0)
 page.locator('#search').fill('')
 page.locator('#source-filter').select_option('tauceti');page.wait_for_timeout(400)
 record('Tau Ceti collection filter',page.evaluate("TauExplorer.getState().origin==='tauceti' && TauExplorer.graph.debugState().counts.constellations===TauExplorer.data.roadmaps.filter(r=>r.origin==='tauceti').length"))
 page.evaluate("TauExplorer.openItem('tauceti:Completed/EffectiveBounds')");page.wait_for_timeout(500)
 record('Maintainer completed area is green',page.evaluate("TauExplorer.progress.roadmap('tauceti:Completed/EffectiveBounds').percent===100"))
 page.evaluate("TauExplorer.openItem('tauceti:TauCetiRoadmap/RepresentationTheory')");page.wait_for_timeout(600)
 record('Nested roadmap collection frames all its child constellations',page.evaluate("TauExplorer.getState().view==='collection' && TauExplorer.getUniverse().constellations.filter(c=>c.parentRoadmapId==='tauceti:TauCetiRoadmap/RepresentationTheory').length===TauExplorer.data.roadmaps.filter(r=>r.parentRoadmapId==='tauceti:TauCetiRoadmap/RepresentationTheory').length && TauExplorer.data.roadmaps.filter(r=>r.parentRoadmapId==='tauceti:TauCetiRoadmap/RepresentationTheory').length>=11"))
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null,origin:'all',unmapped:false})");page.wait_for_timeout(500)
 record('All roadmaps and all roadmap edges available',page.evaluate('TauExplorer.getGraph().nodes.length===%d && TauExplorer.getGraph().edges.length===%d'%(BUILD['roadmaps'],BUILD.get('roadmapEdges',1011))))
 record('All positions finite',page.evaluate("() => { const u=TauExplorer.getUniverse(); return [...u.galaxies,...u.constellations,...u.stars,...u.planets].every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)); }"))
 page.screenshot(path=str(ROOT/'preview-all.png'),animations='disabled')
 page.locator('.tau-label-galaxy').first.click();page.wait_for_timeout(500)
 record('Area heading opens its subject',page.evaluate("TauExplorer.getState().view==='group'") and page.locator('#selection-kind').inner_text()=='Subject')
 page.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null,origin:'all',unmapped:false})");page.wait_for_timeout(400)
 record('Universe has one galaxy per area with roadmaps',page.evaluate("TauExplorer.graph.debugState().counts.galaxies===%d"%BUILD['areasWithRoadmaps']))
 record('Area routes account for every real cross-area dependency once',page.evaluate("""() => { const graph=TauExplorer.getGraph(),nodes=new Map(graph.nodes.map(n=>[n.id,n])),routes=TauExplorer.graph.debugState().routes; const expected=graph.edges.filter(e=>nodes.get(e.source).group!==nodes.get(e.target).group); const pair=(a,b)=>JSON.stringify([a,b].sort()),seen=new Set(); let witnesses=0; for(const route of routes){const p=pair(route.source,route.target); if(seen.has(p)||route.dependencies!==route.witnesses.length)return false; seen.add(p); witnesses+=route.witnesses.length;} return witnesses===expected.length; }"""))
 page.locator('#stats-button').click()
 record('Mission status uses unique leaf totals',page.locator('#stats-scope').inner_text().endswith(format(BUILD['terminalTargets'],',')+' tracked leaf layers'))
 record('Mission status distinguishes 4 states',page.locator('#stats-summary .metric.complete strong').inner_text().replace(',','').isdigit() and int(page.locator('#stats-summary .metric.complete strong').inner_text().replace(',',''))>=36 and page.locator('#stats-summary .metric.active strong').inner_text().replace(',','').isdigit() and sum(int(t.replace(',','')) for t in page.locator('#stats-summary .metric strong').all_inner_texts() if t.replace(',','').isdigit())==BUILD['terminalTargets'] and page.locator('#stats-summary .metric.unknown strong').inner_text().replace(',','').isdigit())
 record('Every area with roadmaps has a progress ledger',page.locator('#area-progress .area-stat').count()==BUILD['areasWithRoadmaps'])
 page.screenshot(path=str(ROOT/'preview-stats.png'),animations='disabled');page.locator('#close-stats').click()
 page.locator('#activity-filter').select_option('active');page.wait_for_timeout(400)
 record('Activity filter shows only active roadmaps',page.evaluate("TauExplorer.getGraph().nodes.length>0 && TauExplorer.getGraph().nodes.length<"+str(BUILD['roadmaps'])+" && TauExplorer.getGraph().nodes.every(n=>TauExplorer.progress.roadmap(n.id).active>0)"))
 page.locator('#activity-filter').select_option('all');page.wait_for_timeout(400)
 page.evaluate("TauExplorer.navigate({view:'roadmap',id:'AnalyticNumberTheory',selected:'AnalyticNumberTheory',tab:'links'})");page.wait_for_timeout(600)
 page.locator('.connection-card').first.locator('summary').click()
 record('Roadmap connections expose supporting layer pairs',page.locator('.connection-witness').count()>0)
 related='tauceti:TauCetiRoadmap/RepresentationTheory/LieHighestWeight'
 page.evaluate("id => TauExplorer.navigate({view:'roadmap',id,layer:null,selected:id,tab:'overview'})",related);page.wait_for_timeout(600)
 page.get_by_label('Show related-plan links',exact=True).check();page.wait_for_timeout(500)
 record('Related-plan links appear on request, dotted and without prerequisite arrows',page.locator('.tau-reference-edge').count()>0 and page.evaluate("Array.from(document.querySelectorAll('.tau-reference-edge')).every(e=>!e.getAttribute('marker-end') && e.getAttribute('stroke-dasharray'))"))
 page.get_by_label('Show related-plan links',exact=True).uncheck();page.wait_for_timeout(300)
 record('Related-plan links disappear when switched off',page.locator('.tau-reference-edge').count()==0)
 page.evaluate("TauExplorer.navigate({view:'roadmap',id:'AnalyticNumberTheory',layer:null,selected:'AnalyticNumberTheory',tab:'overview'})");page.wait_for_timeout(500)
 page.locator('.pin-button').click()
 record('Roadmap can be pinned',page.locator('#pinned-list .pin-item').count()==1)
 page.reload(wait_until='load');page.wait_for_function('!!window.TauExplorer');page.wait_for_timeout(500)
 record('Pinned roadmap persists',page.locator('.pin-button').get_attribute('aria-pressed')=='true')
 page.locator('#activity-filter').select_option('pinned');page.wait_for_timeout(400)
 record('Pinned filter returns saved roadmap',page.evaluate("TauExplorer.getGraph().nodes.length===1 && TauExplorer.getGraph().nodes[0].id==='AnalyticNumberTheory'"))
 page.locator('#activity-filter').select_option('all');page.wait_for_timeout(400)
 page.evaluate("TauExplorer.openReader('tauceti:TauCetiRoadmap/ModularForms')")
 internal=page.locator('#reader-body [data-doc-link]').all();linked=False
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
  record('Campaign execution guide is embedded and linked','execution' in page.locator('#reader-title').inner_text().lower())
  page.locator('#close-reader').click()
 page.locator('#progress-button').click()
 with page.expect_download() as dl:page.locator('#download-offline').click()
 artifact=ROOT/'verified-offline.html';dl.value.save_as(str(artifact));page.locator('#close-progress').click()
 offline=browser.new_context();op=offline.new_page();op.goto(artifact.as_uri());op.wait_for_function('!!window.TauExplorer')
 record('Offline universe loads independently',op.evaluate("TauExplorer.landmarks.length>2500 && TauExplorer.graph.debugState().layout==='universe' && TauExplorer.data.roadmaps.length===%d"%BUILD['roadmaps']) and op.locator('#pinned-list .pin-item').count()==0)
 offline.close()
 if not desktop_only:
  mobile=context.browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
  mp=mobile.new_page();mp.on('pageerror',lambda e:errors.append('mobile: '+str(e)))
  if url.startswith('file:'):
   mp.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
   mp.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
  mp.goto(url,wait_until='load');mp.wait_for_function('!!window.TauExplorer');mp.wait_for_timeout(500)
  touch=mobile.new_cdp_session(mp)
  record('Phone uses touch input at a real mobile viewport',mp.evaluate('navigator.maxTouchPoints>0 && innerWidth===390'))
  check_overview(mp,'Phone',touch=True)
  mp.screenshot(path=str(ROOT/'preview-phone-overview.png'),animations='disabled')
  box=mp.locator('#graph').bounding_box();before=mp.evaluate('TauExplorer.getState().view')
  touch_swipe(mp,touch,(box['x']+20,box['y']+25),(box['x']+65,box['y']+65))
  record('One-finger pan does not open anything',mp.evaluate('TauExplorer.getState().view')==before=='all' and mp.evaluate('TauExplorer.getState().selected===null'))
  fit_all(mp,touch=True)
  mp.locator('[data-node-id="AnalyticNumberTheory"] .tau-hit').tap()
  mp.wait_for_function("TauExplorer.getState().view==='roadmap' && TauExplorer.getState().id==='AnalyticNumberTheory'");mp.wait_for_timeout(600)
  record('Phone tap enters a roadmap constellation',mp.evaluate("TauExplorer.graph.debugState().visible.stars>=10"))
  mp.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-hit').tap()
  mp.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'");mp.wait_for_timeout(600)
  record('Phone tap enters a star system',mp.locator('.tau-planet').count()>0)
  planet=mp.evaluate("TauExplorer.getUniverse().stars.find(s=>s.id==='AnalyticNumberTheory:AN.0').planetIds[0]")
  pinch_gesture(mp,touch,'[data-node-id="'+planet+'"] .tau-hit',1.12)
  record('Phone pinch over a planet does not open it',mp.evaluate("TauExplorer.getState().selected==='AnalyticNumberTheory:AN.0'"))
  mp.wait_for_timeout(800)
  mp.locator('[data-node-id="'+planet+'"] .tau-hit').tap();mp.wait_for_timeout(400)
  record('Phone tap opens mathematical planet details',mp.locator('.landmark-description').is_visible())
  record('Phone reading pane leaves the sky and back navigation visible',mp.locator('.cosmic-back').is_visible() and mp.evaluate("() => {const g=document.querySelector('#graph').getBoundingClientRect(),i=document.querySelector('#inspector').getBoundingClientRect();return g.height>80 && i.height>150 && g.bottom<=i.top+2 && i.bottom<=innerHeight+1}"))
  reading=mp.locator('#inspector-content')
  if reading.evaluate('(e)=>e.scrollHeight>e.clientHeight+10'):
   rb=reading.bounding_box();touch_swipe(mp,touch,(rb['x']+rb['width']/2,rb['y']+rb['height']-30),(rb['x']+rb['width']/2,rb['y']+30))
   record('Phone mathematical details scroll with touch',reading.evaluate('(e)=>e.scrollTop>0'))
  record('Phone mathematical text has a readable size and no page overflow',mp.locator('.landmark-description').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)>=12') and mp.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  record('Phone system labels are legible and disjoint',labels_are_clean(mp) and names_are_unique(mp))
  mp.screenshot(path=str(ROOT/'preview-phone-planet.png'),animations='disabled')
  mp.locator('.cosmic-back').tap();mp.wait_for_function("!TauExplorer.getState().layer");mp.wait_for_timeout(500)
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='group'");mp.wait_for_timeout(500)
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='all'")
  record('Phone back buttons retrace every level',mp.evaluate("!TauExplorer.getState().layer && TauExplorer.graph.debugState().counts.constellations===%d"%BUILD['roadmaps']))
  mp.set_viewport_size({'width':375,'height':812});mp.wait_for_timeout(500);fit_all(mp,touch=True)
  check_overview(mp,'Narrow phone',touch=True)
  mp.screenshot(path=str(ROOT/'preview-phone-narrow-overview.png'),animations='disabled')
  home=mp.evaluate("TauExplorer.data.roadmaps.find(r=>r.id==='AnalyticNumberTheory').group")
  record('Two-finger pinch enters a galaxy on a narrow phone',pinch_until(mp,touch,'[data-label-for="%s"]'%home,3,"TauExplorer.getState().view==='group' && TauExplorer.getState().id==='%s'"%home))
  record('Two-finger pinch enters a roadmap on a narrow phone',pinch_until(mp,touch,'[data-node-id="AnalyticNumberTheory"] .tau-hit',3,"TauExplorer.getState().view==='roadmap' && TauExplorer.getState().id==='AnalyticNumberTheory'"))
  record('Two-finger pinch enters a star system on a narrow phone',pinch_until(mp,touch,'[data-node-id="AnalyticNumberTheory:AN.0"] .tau-hit',3,"TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'"))
  mp.screenshot(path=str(ROOT/'preview-phone-star-system.png'),animations='disabled')
  record('Pinching out returns to the roadmap',pinch_until(mp,touch,'#graph',.3,"TauExplorer.getState().view==='roadmap' && !TauExplorer.getState().layer"))
  record('Pinching out returns to the universe',pinch_until(mp,touch,'#graph',.3,"TauExplorer.getState().view==='all'",attempts=12))
  mp.set_viewport_size({'width':844,'height':390});mp.wait_for_timeout(600);fit_all(mp,touch=True)
  check_overview(mp,'Landscape phone',touch=True)
  mp.screenshot(path=str(ROOT/'preview-phone-landscape-overview.png'),animations='disabled')
  mp.locator('[data-node-id="AnalyticNumberTheory"] .tau-hit').tap();mp.wait_for_function("TauExplorer.getState().view==='roadmap'");mp.wait_for_timeout(500)
  mp.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-hit').tap();mp.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'");mp.wait_for_timeout(500)
  planet=mp.evaluate("TauExplorer.getUniverse().stars.find(s=>s.id==='AnalyticNumberTheory:AN.0').planetIds[0]")
  mp.locator('[data-node-id="'+planet+'"] .tau-hit').tap();mp.wait_for_timeout(400)
  record('Landscape phone opens a mathematical planet',mp.locator('.landmark-description').is_visible())
  record('Landscape phone preserves readable chart and back navigation',mp.locator('.cosmic-back').is_visible() and mp.evaluate("() => {const g=document.querySelector('#graph').getBoundingClientRect(),i=document.querySelector('#inspector').getBoundingClientRect();return g.width>200 && g.height>70 && i.width>240 && i.height>180 && document.documentElement.scrollWidth<=innerWidth+1}"))
  mp.screenshot(path=str(ROOT/'preview-phone-landscape.png'),animations='disabled')
  mp.locator('.cosmic-back').tap();mp.wait_for_function("!TauExplorer.getState().layer");mp.wait_for_timeout(400)
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='group'");mp.wait_for_timeout(400)
  mp.locator('.cosmic-back').tap();mp.wait_for_function("TauExplorer.getState().view==='all'")
  record('Landscape phone back controls remain tappable',mp.locator('#catalogue-button').is_visible())
  mp.set_viewport_size({'width':375,'height':812});mp.wait_for_timeout(500)
  mp.evaluate("TauExplorer.openStage('EllipticKTheory:E.2')");mp.wait_for_timeout(700)
  mp.locator('[data-node-id="'+FORMULA_PLANET+'"] .tau-hit').tap();mp.wait_for_timeout(400)
  formula=mp.locator('.landmark-description math').first
  reading=mp.locator('#inspector-content');reading_box=reading.bounding_box();formula_box=formula.bounding_box()
  if formula_box and formula_box['y']+formula_box['height']>reading_box['y']+reading_box['height']:
   touch_swipe(mp,touch,(reading_box['x']+reading_box['width']/2,reading_box['y']+reading_box['height']-25),(reading_box['x']+reading_box['width']/2,reading_box['y']+25))
  record('Phone tap opens readable mathematics behind the plain planet name',formula.is_visible() and mp.evaluate("() => {const math=document.querySelector('.landmark-description math').getBoundingClientRect(),panel=document.querySelector('#inspector-content').getBoundingClientRect();return math.width>30&&math.height>10&&math.left>=panel.left-1&&math.right<=panel.right+1}"))
  mp.screenshot(path=str(ROOT/'preview-phone-formula-planet.png'),animations='disabled')
  mp.locator('.cosmic-back').tap();mp.wait_for_function("!TauExplorer.getState().layer");mp.wait_for_timeout(400)
  mp.evaluate("TauExplorer.navigate({view:'all',id:null,layer:null,selected:null})");mp.wait_for_timeout(400)
  mp.locator('#catalogue-button').tap()
  record('Phone view has working browse/search',mp.locator('#search').is_visible())
  mp.locator('#search').fill('Perron');record('Phone search returns topics',mp.locator('.search-hit').count()>0)
  mp.locator('.search-hit').first.tap();record('Phone selection dismisses index',not mp.locator('#search').is_visible())
  mp.screenshot(path=str(ROOT/'preview-phone.png'),animations='disabled')
  mobile.close()
  if Path(p.webkit.executable_path).exists():
   safari=p.webkit.launch(headless=True)
   sc=safari.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
   sp=sc.new_page();sp.on('pageerror',lambda e:errors.append('webkit: '+str(e)))
   sp.goto(url,wait_until='load');sp.wait_for_function('!!window.TauExplorer');sp.wait_for_timeout(600)
   sp.locator('[data-node-id="AnalyticNumberTheory"] .tau-hit').tap();sp.wait_for_function("TauExplorer.getState().view==='roadmap'");sp.wait_for_timeout(600)
   sp.locator('[data-node-id="AnalyticNumberTheory:AN.0"] .tau-hit').tap();sp.wait_for_function("TauExplorer.getState().layer==='AnalyticNumberTheory:AN.0'");sp.wait_for_timeout(600)
   planet=sp.evaluate("TauExplorer.getUniverse().stars.find(s=>s.id==='AnalyticNumberTheory:AN.0').planetIds[0]")
   sp.locator('[data-node-id="'+planet+'"] .tau-hit').tap();sp.wait_for_timeout(400)
   record('Installed WebKit supports mobile galaxy, layer and planet taps',sp.locator('.landmark-description').is_visible() and sp.locator('.cosmic-back').is_visible())
   sp.screenshot(path=str(ROOT/'preview-webkit-phone.png'),animations='disabled');safari.close()
 page.evaluate("TauExplorer.openItem('AnalyticNumberTheory')")
 page.set_viewport_size({'width':900,'height':800});page.wait_for_timeout(600);page.screenshot(path=str(ROOT/'preview-narrow.png'),animations='disabled')
 record('Narrow desktop view usable',page.locator('#inspector').is_visible())
 record('Markdown rejects unsafe HTML and schemes',page.evaluate("""() => {const f=TauMarkdown.render('<img src=x onerror=alert(1)>\\n\\n[x](javascript:alert(1))');const d=document.createElement('div');d.append(f);return !d.querySelector('img,script,iframe')&&!Array.from(d.querySelectorAll('a')).some(a=>a.href.startsWith('javascript'))}"""))
 page.evaluate("TauExplorer.openItem('GeometricSatakeAndFusion')");page.wait_for_timeout(600)
 record('Layer order respects internal prerequisites',page.evaluate("() => {const u=TauExplorer.getUniverse(),stars=u.stars.filter(s=>s.constellationId==='GeometricSatakeAndFusion'),ids=new Set(stars.map(s=>s.id)),rank=new Map(stars.map(s=>[s.id,s.rank]));return stars.every(s=>s.dependencyOrderValid) && TauExplorer.data.stageEdges.filter(e=>ids.has(e.source)&&ids.has(e.target)).every(e=>rank.get(e.source)<rank.get(e.target));}"))
 page.evaluate("TauExplorer.navigate({view:'all',id:null,selected:null,origin:'all'})");page.wait_for_timeout(500)
 svg=page.evaluate('TauExplorer.graph.exportSVG()');svgpath=ROOT/'verified-universe.svg';svgpath.write_text(svg)
 record('SVG export contains the universe and no scripts','tau-galaxy-disc' in svg and '<script' not in svg and 'file:///' not in svg)
 svgp=page.context.new_page();svgp.goto(svgpath.as_uri());record('SVG export opens independently',svgp.locator('svg').count()==1);svgp.close()
 run_reference_checks(page,browser)
 record('No application exceptions',not errors)
 if url.startswith('file:'):record('No network requests needed',not requests)
 browser.close()
write_report('desktop' if desktop_only else 'desktop and mobile')
