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

from dp.common import LPConfig,dpDir,selfFileSet,SEP
from dp.server.main import getDb,clientIpDict,getStatus,isRun,countStop,uniqueProcName,\
  splitProcName,checkUpdateDir

serverDir = os.path.join(dpDir,'server')

templatePath = os.path.join(serverDir,'web','template','')
webLookup = TemplateLookup(directories=[templatePath],input_encoding='utf-8',output_encoding='utf-8',\
  module_directory=tempfile.gettempdir())

activeCssDict = {'procActiveCss':'','clientActiveCss':'','aboutActiveCss':''}

def convertPage(curPage,pageSize):
  if curPage is None: return {}
  startPos = (curPage-1)*pageSize
  return {'startPos':startPos,'endPos':startPos+pageSize}
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
    elif name=='clientConfInfo':
      self._changeActiveCss('procActiveCss')
      return ProcessConfInfoResource()
    elif name=='clientConsoleInfo':
      self._changeActiveCss('procActiveCss')
      return ProcessConsoleInfoResource()
    elif name=='clientLogInfo':
      self._changeActiveCss('procActiveCss')
      return ProcessLogInfoResource()
    elif name=='clientStartHistory':
      self._changeActiveCss('procActiveCss')
      return ProcessStartHistoryResource()
    elif name=='clientUpdateHistory':
      self._changeActiveCss('procActiveCss')
      return ProcessUpdateHistoryResource()
    elif name=='procOp':
      return ProcOpResource()
    elif name=='groupOp':
      return GroupOpResource()
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
    finishRequest(None,request)
    return NOT_DONE_YET

class ClientResource(Resource):
  def __init__(self):
    Resource.__init__(self)
  def render_GET(self, request):
    flash = IFlash(request.getSession())
    clientDict = {}
    for key,val in clientIpDict.iteritems():
      status = getStatus(key)
      clientDict[key] = {'version':val.get('version','N/A'),'status':status['status'],\
        'lastConnected':fmtDate(status['lastUpdated']),'fileUpdated':fmtDate(status.get('fileUpdated')),\
        'lastShaked':fmtDate(val.get('lastShaked'))}
    request.write(getTemplateContent('client',clientDict=clientDict,flash=flash,canUpdate=checkUpdateDir(selfFileSet),**activeCssDict))
    finishRequest(None,request,flash)
    return NOT_DONE_YET

class ProcessResource(Resource):
  def _initClientSideArgs(self,currentIp):
    ips = clientIpDict.keys()
    clientSideArgs = {'actCssList':[],'labelCssList':[],'countList':[],'clientIps':ips,'currentIp':currentIp}
    for ip in ips:
      clientSideArgs['actCssList'].append('active' if currentIp==ip else '')
      clientSideArgs['labelCssList'].append('' if isRun(ip) else 'label')
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
        procRow = [procName,procStatus['status'],fmtDate(procStatus['lastUpdated']),uniName,fmtDate(procStatus.get('fileUpdated')),]
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
  def render_GET(self, request):
    cmdStr = request.args['op'][0]
    name = request.args.get('name')[0]
    if cmdStr=='Console':
      clientip,pgName,psName = name.split(SEP)
      defQueue = defer.DeferredQueue(1,1)
      defQueue.get().addCallback(lambda x:request.write(getTemplateContent('consoleLog',psLabel='%s:%s'%(pgName,psName),logContent=x['content']))).addBoth(finishRequest,request)
      clientIpDict[clientip]['protocol'].asyncSendJson({'action':'procOp','op':'Console','grp':pgName,'name':psName},defQueue)
    else:      
      names = name.split(SEP)
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

class ProcessConfInfoResource(ProcessResource):
  def render_GET(self, request):
    uniName = request.args.get('name')
    if uniName is None:request.redirect("/")
    ip,grpName,procName = splitProcName(uniName[0])
    def procInfo(result):
      yamContent = result[0][0]
      request.write(getTemplateContent('procConfInfo',clientSideArgs=self._initClientSideArgs(ip),\
        grpName=grpName,procName=procName,ip=ip,yamContent=yamContent,\
        monLog=getMonLog(uniName[0]),uniName=uniName[0],**activeCssDict))
    getDb().runQuery('SELECT procInfo FROM Process WHERE clientIp = ? and procGroup = ? and procName = ?',\
      [ip,grpName,procName]).addCallback(procInfo).addBoth(finishRequest,request)
    return NOT_DONE_YET
def getMonLog(uniName):
  return getStatus(uniName).get('monLog')

class BaseProcessInfoResource(ProcessResource):
  def __init__(self,templateName,opName):
    ProcessResource.__init__(self)
    self.templateName = templateName
    self.opName = opName
  def render_GET(self, request):
    uniName = request.args.get('name')
    if uniName is None:request.redirect("/")
    curPage = request.args.get('curPage')
    pageSize = request.args.get('pageSize')
    if curPage is not None: curPage = int(curPage[0])
    pageSize = 4096 if pageSize is None else int(pageSize[0])
    clientip,pgName,psName = splitProcName(uniName[0])
    defQueue = defer.DeferredQueue(1,1)
    defQueue.get().addCallback(lambda x:request.write(getTemplateContent(self.templateName,\
      clientSideArgs=self._initClientSideArgs(clientip),grpName=pgName,procName=psName,ip=clientip,monLog=getMonLog(uniName[0]),\
      uniName=uniName[0],logInfo=x,curPage=curPage,pageSize=pageSize,**activeCssDict))).addBoth(finishRequest,request)
    jsonArgs = {'action':'procOp','op':self.opName,'grp':pgName,'name':psName}
    jsonArgs.update(convertPage(curPage,pageSize))
    clientIpDict[clientip]['protocol'].asyncSendJson(jsonArgs,defQueue)
    return NOT_DONE_YET
class ProcessConsoleInfoResource(BaseProcessInfoResource):
  def __init__(self):
    BaseProcessInfoResource.__init__(self,'procConsoleInfo','Console')
class ProcessLogInfoResource(BaseProcessInfoResource):
  def __init__(self):
    BaseProcessInfoResource.__init__(self,'procLogInfo','Log')
    
class BaseProcessHistoryResource(ProcessResource):
  def __init__(self,templateName,opName):
    ProcessResource.__init__(self)
    self.templateName = templateName
    self.opName = opName
  def render_GET(self, request):
    uniName = request.args.get('name')
    if uniName is None:request.redirect("/")
    curPage = request.args.get('curPage')
    if curPage is not None: curPage = int(curPage[0])
    pageSize = 8192
    clientip,pgName,psName = splitProcName(uniName[0])
    defQueue = defer.DeferredQueue(1,1)
    defQueue.get().addCallback(lambda x:request.write(getTemplateContent(self.templateName,\
      clientSideArgs=self._initClientSideArgs(clientip),grpName=pgName,procName=psName,ip=clientip,monLog=getMonLog(uniName[0]),\
      uniName=uniName[0],logInfo=x,curPage=curPage,pageSize=pageSize,showPageSize=False,**activeCssDict))).addBoth(finishRequest,request)
    jsonArgs = {'action':'procOp','op':self.opName,'grp':pgName,'name':psName}
    jsonArgs.update(convertPage(curPage,pageSize))
    clientIpDict[clientip]['protocol'].asyncSendJson(jsonArgs,defQueue)
    return NOT_DONE_YET
class ProcessStartHistoryResource(BaseProcessInfoResource):
  def __init__(self):
    BaseProcessInfoResource.__init__(self,'procStartHistory','StartHistory')
class ProcessUpdateHistoryResource(BaseProcessInfoResource):
  def __init__(self):
    BaseProcessInfoResource.__init__(self,'procUpdateHistory','UpdateHistory')
    
class GroupOpResource(Resource):
  def render_GET(self, request):
    cmdStr = request.args['op'][0]
    name = request.args.get('name')[0]
    names = name.split(SEP)
    ip = names[0]
    msg = '%s remote group : %s/%s'%(cmdStr,ip,names[1])
    def delayRender(msg,alert='info'):
      flash = IFlash(request.getSession())
      flash.msg = msg
      flash.alert = alert
      request.redirect('/proc')
      finishRequest(None,request)
    if cmdStr=='Restart':
      clientIpDict[ip]['protocol'].sendJson(json.dumps({'action':'groupOp','op':cmdStr,'grp':names[1]}))
      reactor.callLater(0.5,delayRender,msg)
    elif cmdStr=='Update':
      clientIpDict[ip]['protocol'].sendJson(json.dumps({'action':'groupOp','op':cmdStr,'grp':names[1]}))
      reactor.callLater(0.5,delayRender,msg)
    return NOT_DONE_YET

root = RootResource()
root.putChild("static", File(os.path.join(serverDir,'web','static')))
root.putChild("favicon.ico", File(os.path.join(serverDir,'web','static','img','favicon.ico')))
