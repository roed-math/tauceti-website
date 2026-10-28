"""Prepare the public app and roadmap-text snapshot, without local filesystem metadata."""
from pathlib import Path
import argparse,copy,hashlib,json,posixpath,re,shutil
from urllib.parse import unquote,urlsplit
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);args=parser.parse_args();repo=args.destination
repo.mkdir(parents=True,exist_ok=True)
data=json.loads((HERE/'data.json').read_text());overlay=json.loads((HERE/'status_overlay.json').read_text())
paths={};documents=[];companions=[]
def register(source,target,text):
 paths[str(Path(source))]=target
 paths[str(Path(source).resolve())]=target
 documents.append((source,target,text))
for r in data['roadmaps']:
 if r.get('origin')=='tauceti':
  name=r['repositoryPath'].removesuffix('/README.md').replace('TauCetiRoadmap/','').replace('Completed/','Completed/')
  target='content/tau-ceti/'+name+'/README.md'
 else:target='content/campaign/'+r['id']+'/README.md'
 register(r['sourcePath'],target,r['readme'])
 for field,filename in [('statusMarkdown','STATUS.md'),('progressMarkdown','PROGRESS.md')]:
  if r.get(field):register(str(Path(r['sourcePath']).with_name(filename)),str(Path(target).with_name(filename)),r[field])
# Register the execution guides before rewriting any roadmap links. The allowlist
# is deliberately limited to these Markdown companions, without source PDFs,
# extracted paper text, historical baselines, or review directories.
campaign_root=Path(data['meta']['sourceRoot'])
companion_sources=sorted((campaign_root/'campaign').glob('*.md'))
extension_sources=campaign_root/'revision/EXTENSION_SOURCES.md'
if extension_sources.is_file():companion_sources.append(extension_sources)
for source in companion_sources:
 text=source.read_text()
 target='content/campaign-guide/'+source.name
 assert target not in paths.values(),f'Duplicate companion filename: {source.name}'
 register(str(source),target,text)
 heading=re.search(r'^#\s+(.+)$',text,re.M)
 title=heading[1].strip().strip('#').strip() if heading else source.stem.replace('_',' ').title()
 companions.append({'id':'guide:'+source.stem,'title':title,'sourcePath':str(source)})
linkpat=re.compile(r'\[([^\]\n]+)\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)')
def scrub_string(s):
 s=re.sub(r'file:///Users/[^\s)<>\]"\']+', '[local-source]', s)
 s=re.sub(r'/Users/[^\s)<>\]"\']+', '[local-source]', s)
 return s
removed_links=0
converted_links=0
def rewrite_unprotected(text,rewrite):
 """Apply a link rewrite only outside fenced code, code spans and TeX math.

 Collision-free placeholders preserve code/math inside a link label while still
 letting that enclosing link's destination be rewritten. Protected source slices
 are restored verbatim; the caller then scrubs local paths, including code paths.
 """
 result=[];protected=[];plain_start=0;i=0
 marker_prefix='\x00TAUCETI_PROTECTED_'
 while marker_prefix in text:
  marker_prefix+='_' 
 def escaped(index):
  backslashes=0;index-=1
  while index>=0 and text[index]=='\\':backslashes+=1;index-=1
  return backslashes%2==1
 def math_end(start,closing):
  end=text.find(closing,start)
  while end>=0:
   if not escaped(end) and (closing!='$' or
       (not text.startswith('$$',end) and (end==0 or text[end-1]!='$'))):
    return end+len(closing)
   end=text.find(closing,end+len(closing))
  return None
 while i<len(text):
  end=None
  if i==0 or text[i-1]=='\n':
   fence=re.match(r'[ \t]*(?:>[ \t]*)*(`{3,}|~{3,})[^\n]*(?:\n|$)',text[i:])
   if fence:
    marker=fence[1]
    closing=re.compile(r'^[ \t]*(?:>[ \t]*)*'+re.escape(marker[0])+r'{'+str(len(marker))+r',}[ \t]*(?:\n|$)',re.M)
    match=closing.search(text,i+len(fence[0]))
    end=match.end() if match else len(text)
  if end is None and text[i]=='`' and not escaped(i):
   run=re.match(r'`+',text[i:])[0]
   closing=re.compile(r'(?<!`)'+re.escape(run)+r'(?!`)')
   match=closing.search(text,i+len(run))
   if match:end=match.end()
  if end is None and not escaped(i):
   opening=next((m for m in ('\\(','\\[','$$','$') if text.startswith(m,i)),None)
   if opening:
    closing={'\\(':'\\)','\\[':'\\]'}.get(opening,opening)
    end=math_end(i+len(opening),closing)
  if end is not None:
   result.append(text[plain_start:i])
   result.append(marker_prefix+str(len(protected))+'\x00')
   protected.append(text[i:end])
   i=end;plain_start=end
  else:i+=1
 result.append(text[plain_start:])
 rewritten=rewrite(''.join(result))
 return re.sub(re.escape(marker_prefix)+r'(\d+)\x00',lambda m:protected[int(m[1])],rewritten)
def markdown(text,source,target):
 def replace(m):
  global removed_links,converted_links
  label,dest=m[1],m[2].strip('<>')
  if dest.startswith('#') or urlsplit(dest).scheme in ['https','http','mailto']:return m[0]
  if urlsplit(dest).scheme and not dest.startswith('file:'):
   removed_links+=1;return label
  path,sep,frag=dest.partition('#')
  try:resolved=str((Path(source).parent/unquote(path)).resolve())
  except Exception:return label
  if resolved in paths:
   converted_links+=1
   rel=posixpath.relpath(paths[resolved],str(Path(target).parent))
   return '['+label+']('+rel+('#'+frag if sep else '')+')'
  removed_links+=1;return label
 return scrub_string(rewrite_unprotected(text,lambda segment:linkpat.sub(replace,segment)))
prepared_docs={}
for source,target,text in documents:
 clean=markdown(text,source,target);prepared_docs[source]=clean
 dest=repo/target;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(clean)
for r in data['roadmaps']:
 source=r['sourcePath'];r['readme']=prepared_docs[source]
 for field,filename in [('statusMarkdown','STATUS.md'),('progressMarkdown','PROGRESS.md')]:
  if r.get(field):r[field]=prepared_docs[str(Path(source).with_name(filename))]
for s in data['stages']:
 old=s['sourcePath'];s['description']=markdown(s['description'],old,paths.get(old,'content/unknown/README.md'))
data['documents']=[dict(item,text=prepared_docs[item['sourcePath']]) for item in companions]
def clean_obj(obj,key=None):
 if isinstance(obj,dict):return {k:clean_obj(v,k) for k,v in obj.items() if k not in {'dirtyEntries','sourceRoot','suggestedPath','executionPath'}}
 if isinstance(obj,list):return [clean_obj(v,key) for v in obj]
 if isinstance(obj,str):
  if obj in paths:return paths[obj]
  if key=='repositoryPath' and obj.startswith('/'):return 'TauCetiProject/TauCetiRoadmap'
  return scrub_string(obj)
 return obj
data=clean_obj(data);overlay=clean_obj(overlay)
data['meta']['publication']='Embedded text snapshot; source PDFs and local progress overrides are not part of the published atlas.'
data['meta']['canonicalRepository']='https://github.com/TauCetiProject/TauCetiRoadmap'
(repo/'data').mkdir(exist_ok=True)
(repo/'data/atlas.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
(repo/'data/status.json').write_text(json.dumps(overlay,ensure_ascii=False,separators=(',',':'))+'\n')
for directory in ['src','vendor']:
 (repo/directory).mkdir(exist_ok=True)
 for p in (HERE/directory).iterdir():
  if p.is_file():shutil.copy2(p,repo/directory/p.name)
(repo/'scripts').mkdir(exist_ok=True)
report={'roadmaps':len(data['roadmaps']),'stages':len(data['stages']),'documents':len(documents),'companion_documents':len(companions),'internal_links_rewritten':converted_links,'unbundled_local_links_retained_as_text':removed_links,'absolute_home_paths_in_public_data':0,'reference_pdfs_included':0,'local_progress_overrides_included':False,'source_provenance':'Original document hashes and reported commit/date retained; local filesystem locations omitted.'}
for p in [repo/'data/atlas.json',repo/'data/status.json']:
 assert '/Users/' not in p.read_text() and 'file:///' not in p.read_text(),p
(repo/'data/PUBLICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
