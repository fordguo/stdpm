#-*- coding:utf-8 -*- 

from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.server import NOT_DONE_YET
from twisted.python.filepath import FilePath
from twisted.internet.defer import Deferred

import os
from string import Template

from dp_common import dpDir
from dp_server import getDb,clientIps,getStatus,isRun,countStop

templatePath = os.path.join(dpDir,'web','template','')


activeCssDict = {'procActiveCss':'','clientActiveCss':'','aboutActiveCss':''}

def getTemplate(name):
  with open(os.path.join(templatePath,"%s.html"%name)) as f:
    return Template(f.read())

mainTemplate = getTemplate('main')
clientSideTemplate = getTemplate('clientSidebar')

class RootResource(Resource):
  def _changeActiveCss(self,name):
    for k in activeCssDict.iterkeys():
      activeCssDict[k] = 'active' if k==name else ''
  def getChild(self, name, request):
    if name=='client':
      self._changeActiveCss('clientActiveCss')
      return "client"
    elif name=='about':
      self._changeActiveCss('aboutActiveCss')
      return "about"
    else:
      self._changeActiveCss('procActiveCss')
      return ProcessResource()

def finishRequest(result,request):
  if result:
    print result
  request.finish()

class ProcessResource(Resource):
  def _sidebarContent(self,currentIp):
    tagLis = []
    for i,ip in enumerate(clientIps):
      actCss = '' if ip!=currentIp else 'active'
      labelCss =  '' if isRun(ip) else 'label label-important'
      count = countStop(ip)
      stopCountLabel = '' if count<=0 else '<span class="badge badge-warning">%d</span>'%count
      tagLis.append('<li class="%s"><a href="/clientProc?ip=%s"><span class="%s">%s</span> %s</a></li>'
        %(actCss,ip,labelCss,ip,stopCountLabel))
    return clientSideTemplate.safe_substitute(clientList='\n'.join(tagLis))
  def render_GET(self, request):
    print request.args
    currentIp = request.args.get('ip')
    if currentIp is None and len(clientIps)>0:
      currentIp = iter(clientIps).next()
    else:
      currentIp = currentIp[0]
    def procList(result):
      mainDict = {'mainContent':str(self._sidebarContent(currentIp))}
      mainDict.update(activeCssDict)
      request.write(mainTemplate.safe_substitute(mainDict))
      request.finish()          
    getDb().runQuery('SELECT clientIp,procGroup,procName FROM Process').addCallback(procList)
    return NOT_DONE_YET

root = RootResource()
root.putChild("static", File(os.path.join(dpDir,'web','static')))
root.putChild("favicon.ico", File(os.path.join(dpDir,'web','static','img','favicon.ico')))
