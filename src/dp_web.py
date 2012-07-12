#-*- coding:utf-8 -*- 

from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.server import NOT_DONE_YET

import os,tempfile
from mako.template import Template
from mako.lookup import TemplateLookup

from dp_common import dpDir
from dp_process import LPConfig
from dp_server import getDb,clientIps,getStatus,isRun,countStop,uniqueProcName,splitProcName

templatePath = os.path.join(dpDir,'web','template','')
webLookup = TemplateLookup(directories=[templatePath],input_encoding='utf-8',output_encoding='utf-8',\
  module_directory=tempfile.gettempdir())

activeCssDict = {'procActiveCss':'','clientActiveCss':'','aboutActiveCss':''}

def getTemplateContent(name,**kw):
  return str(webLookup.get_template('%s.html'%name).render(**kw))

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
    elif name=='clientProcInfo':
      self._changeActiveCss('procActiveCss')
      return ProcessInfoResource()
    else:
      self._changeActiveCss('procActiveCss')
      return ProcessResource()

def finishRequest(result,request):
  if result:
    print result
  request.finish()

class ProcessResource(Resource):
  def _initClientSideArgs(self,currentIp):
    clientSideArgs = {'actCssList':[],'labelCssList':[],'countList':[],'clientIps':clientIps,'currentIp':currentIp}
    for ip in clientIps:
      clientSideArgs['actCssList'].append('active' if currentIp==ip else '')
      clientSideArgs['labelCssList'].append('' if isRun(ip) else 'label label-important')
      clientSideArgs['countList'].append(countStop(ip))
    return clientSideArgs
  def render_GET(self, request):
    currentIp = request.args.get('ip')
    if currentIp is None and len(clientIps)>0:
      currentIp = iter(clientIps).next()
    else:
      currentIp = currentIp[0]
    def procList(result):
      procDict = {}
      for row in result:
        grpName,procName = [row[0],row[1]]
        uniName = uniqueProcName(currentIp,grpName,procName)
        procStatus = getStatus(uniName)
        procRow = [procName,procStatus['status'],procStatus['lastUpdated'],uniName]
        procGrp =  procDict.get(grpName)
        if procGrp is None:
          procGrp = [procRow]
          procDict[grpName] = procGrp
        else:
          procGrp.append(procRow)
      request.write(getTemplateContent('proc',clientSideArgs=self._initClientSideArgs(currentIp),\
        procDict=procDict,currentIp=currentIp,**activeCssDict))
    getDb().runQuery('SELECT procGroup,procName FROM Process WHERE clientIp = ?',[currentIp]).addCallback(procList).addBoth(finishRequest,request)
    return NOT_DONE_YET

class ProcessInfoResource(ProcessResource):
  def render_GET(self, request):
    uniName = request.args.get('name')
    if uniName is None:request.redirect("/")
    ip,grpName,procName = splitProcName(uniName[0])
    def procInfo(result):
      yamContent = result[0][0]
      request.write(getTemplateContent('procInfo',clientSideArgs=self._initClientSideArgs(ip),\
        grpName=grpName,procName=procName,ip=ip,yamContent=yamContent,**activeCssDict))
    getDb().runQuery('SELECT procInfo FROM Process WHERE clientIp = ? and procGroup = ? and procName = ?',\
      [ip,grpName,procName]).addCallback(procInfo).addBoth(finishRequest,request)
    return NOT_DONE_YET

root = RootResource()
root.putChild("static", File(os.path.join(dpDir,'web','static')))
root.putChild("favicon.ico", File(os.path.join(dpDir,'web','static','img','favicon.ico')))
