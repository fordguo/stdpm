#-*- coding:utf-8 -*- 

from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.server import NOT_DONE_YET
from twisted.internet import reactor,defer

from zope.interface import Interface, Attribute, implements
from twisted.python.components import registerAdapter
from twisted.web.server import Session

import os,tempfile,json
import time
import yaml
from mako.template import Template
from mako.lookup import TemplateLookup

from dp.common import LPConfig,dpDir,selfFileSet
from dp.server.main import getDb,clientIpDict,getStatus,isRun,countStop,uniqueProcName,\
  splitProcName,checkUpdateDir

serverDir = os.path.join(dpDir,'server')

templatePath = os.path.join(serverDir,'web','template','')
webLookup = TemplateLookup(directories=[templatePath],input_encoding='utf-8',output_encoding='utf-8',\
  module_directory=tempfile.gettempdir())

activeCssDict = {'procActiveCss':'','clientActiveCss':'','aboutActiveCss':''}

class IFlash(Interface):
    msg = Attribute("A temp message.")
    alert = Attribute("A temp alert level.")

class Flash(object):
    implements(IFlash)
    def __init__(self, session):
        self.msg = ''
        self.alert = 'info'

registerAdapter(Flash, Session, IFlash)

def getTemplateContent(name,**kw):
  return str(webLookup.get_template('%s.html'%name).render(**kw))
def fmtDate(date):
  return 'N/A' if date is None else date.strftime('%Y-%m-%d %H:%M:%S')
class RootResource(Resource):
  def _changeActiveCss(self,name):
    for k in activeCssDict.iterkeys():
      activeCssDict[k] = 'active' if k==name else ''
  def getChild(self, name, request):
    if name=='client':
      self._changeActiveCss('clientActiveCss')
      return ClientResource()
    elif name=='clientOp':
      return ClientOpResource()
    elif name=='about':
      self._changeActiveCss('aboutActiveCss')
      return AboutResource()
    elif name=='clientProcInfo':
      self._changeActiveCss('procActiveCss')
      return ProcessInfoResource()
    elif name=='procOp':
      return ProcOpResource()
    else:
      self._changeActiveCss('procActiveCss')
      return ProcessResource()

def finishRequest(result,request,flash=None):
  if result:
    print result
  if flash:
    flash.msg = ''
    flash.alert = 'info'
  request.finish()

class AboutResource(Resource):
  def __init__(self):
    Resource.__init__(self)
  def render_GET(self, request):
    return getTemplateContent('about',**activeCssDict)

class ClientOpResource(Resource):
  def render_POST(self, request):
    cmdStr = request.args['op'][0]
    ip = request.args.get('ip')[0]
    clientIpDict[ip]['protocol'].sendJson(json.dumps({'action':'clientOp','value':cmdStr}))
    msg = 'Send command %s to %s'%(cmdStr,ip)
    flash = IFlash(request.getSession())
    flash.msg = msg
    time.sleep(0.5)
    request.redirect('/client')
    return ""

class ClientResource(Resource):
  def __init__(self):
    Resource.__init__(self)
  def render_GET(self, request):
    flash = IFlash(request.getSession())
    clientDict = {}
    for key,val in clientIpDict.iteritems():
      status = getStatus(key)
      clientDict[key] = {'version':val.get('version','N/A'),'status':status['status'],\
      'lastConnected':fmtDate(status['lastUpdated']),'fileUpdated':fmtDate(status.get('fileUpdated'))}
    request.write(getTemplateContent('client',clientDict=clientDict,flash=flash,canUpdate=checkUpdateDir(selfFileSet),**activeCssDict))
    finishRequest(None,request,flash)
    return NOT_DONE_YET

class ProcessResource(Resource):
  def _initClientSideArgs(self,currentIp):
    ips = clientIpDict.keys()
    clientSideArgs = {'actCssList':[],'labelCssList':[],'countList':[],'clientIps':ips,'currentIp':currentIp}
    for ip in ips:
      clientSideArgs['actCssList'].append('active' if currentIp==ip else '')
      clientSideArgs['labelCssList'].append('' if isRun(ip) else 'label label-important')
      clientSideArgs['countList'].append(countStop(ip))
    return clientSideArgs
  def render_GET(self, request):
    flash = IFlash(request.getSession())
    currentIp = request.args.get('ip')
    if currentIp is None and len(clientIpDict)>0:
      currentIp = iter(clientIpDict.keys()).next()
    elif currentIp:
      currentIp = currentIp[0]
    def procList(result):
      procDict = {}
      for row in result:
        grpName,procName = [row[0],row[1]]
        uniName = uniqueProcName(currentIp,grpName,procName)
        procStatus = getStatus(uniName)
        procRow = [procName,procStatus['status'],fmtDate(procStatus['lastUpdated']),uniName,fmtDate(procStatus.get('fileUpdated'))]
        procGrp =  procDict.get(grpName)
        if procGrp is None:
          procGrp = [procRow]
          procDict[grpName] = procGrp
        else:
          procGrp.append(procRow)
      request.write(getTemplateContent('proc',clientSideArgs=self._initClientSideArgs(currentIp),\
        procDict=procDict,currentIp=currentIp,flash=flash,**activeCssDict))
      finishRequest(None,request,flash)
    getDb().runQuery('SELECT procGroup,procName FROM Process WHERE clientIp = ?',[currentIp]).addCallback(procList).addBoth(finishRequest,request)
    return NOT_DONE_YET

class ProcOpResource(Resource):
  def render_GET(self,request):
    name = request.args.get('name')[0]
    clientip,pgName,psName = name.split(':')
    defQueue = defer.DeferredQueue()
    defQueue.get().addCallback(lambda x:request.write(getTemplateContent('consoleLog',psLabel='%s:%s'%(pgName,psName),logContent=x))).addBoth(finishRequest,request)
    clientIpDict[clientip]['protocol'].asyncSendJson({'action':'procOp','op':'Console','grp':pgName,'name':psName},defQueue)
    return NOT_DONE_YET
  def render_POST(self, request):
    cmdStr = request.args['op'][0]
    name = request.args.get('name')[0]
    names = name.split(":")
    ip = names[0]
    msg = '%s remote://%s/%s/%s'%(cmdStr,ip,names[1],names[2])
    def delayRender(msg,alert='info'):
      flash = IFlash(request.getSession())
      flash.msg = msg
      flash.alert = alert
      request.redirect('/proc')
      finishRequest(None,request)
    if cmdStr=='Restart':
      clientIpDict[ip]['protocol'].sendJson(json.dumps({'action':'procOp','op':cmdStr,'grp':names[1],'name':names[2]}))
      reactor.callLater(0.5,delayRender,msg)
    elif cmdStr == 'Update':
      def procInfo(result,msg):
        yamContent = result[0][0]
        lp = LPConfig(yaml.load(yamContent))
        alert = 'info'
        if lp.fileUpdateInfo():
          clientIpDict[ip]['protocol'].sendJson(json.dumps({'action':'procOp','op':cmdStr,'grp':names[1],'name':names[2]}))
        else:
          msg += " invalid"
          alert = 'error'
        delayRender(msg,alert)
      getDb().runQuery('SELECT procInfo FROM Process WHERE clientIp = ? and procGroup = ? and procName = ?',\
      [ip,names[1],names[2]]).addCallback(procInfo,msg)
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
root.putChild("static", File(os.path.join(serverDir,'web','static')))
root.putChild("favicon.ico", File(os.path.join(serverDir,'web','static','img','favicon.ico')))
