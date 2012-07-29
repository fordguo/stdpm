#-*- coding:utf-8 -*- 

#http://code.activestate.com/recipes/576569/ A simple dependency resolver
def _no_deps(items, deps, built):
  return [i for i in items if not _depends_on_unbuilt(i, deps, built)]
def _depends_on_unbuilt(item, deps, built):
  if not item in deps:
    return False    
  return any(d not in built for d in deps[item])
def resolve_paralell(items, deps):
  items = set(items)
  built = set()
  out = []
  while True:
    if not items:
      break
    no_d = set(_no_deps(items, deps, built))
    items -= no_d

    built |= no_d
    out.append(no_d)

    if set(sum(deps.values(), [])) == built:
      out.append(items)
      break      
  return out
SEP = '::'
def resortPs(procGroupDict):
  allPs = []
  psDeps = {}
  for gpName,pg in procGroupDict.iteritems():
    for psName,psInfo in pg.iterMap():
      uniqueName = "%s%s%s"%(gpName,SEP,psName)
      allPs.append(uniqueName)
      if psInfo.get('dependencies'):
        psDeps[uniqueName] = psInfo.get('dependencies')
  depSet = resolve_paralell(allPs,psDeps)
  result = []
  def _priority(name):
    gpName,psName = name.split(SEP)
    return procGroupDict[gpName].procsMap[psName].get('priority',50)
  for psSet in depSet:
    result += sorted(psSet,key=lambda x:_priority(x))
  return result

