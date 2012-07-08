#-*- coding:utf-8 -*- 

from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.server import NOT_DONE_YET

import os,tempfile
from mako.template import Template
from mako.lookup import TemplateLookup

from dp_common import dpDir
from dp_server import getDb,clientIps,getStatus,isRun,countStop

templatePath = os.path.join(dpDir,'web','template','')
webLookup = TemplateLookup(directories=[templatePath],input_encoding='utf-8',module_directory=tempfile.gettempdir())

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
    else:
      self._changeActiveCss('procActiveCss')
      return ProcessResource()

def finishRequest(result,request):
  if result:
    print result
  request.finish()

class ProcessResource(Resource):
  def render_GET(self, request):
    currentIp = request.args.get('ip')
    if currentIp is None and len(clientIps)>0:
      currentIp = iter(clientIps).next()
    else:
      currentIp = currentIp[0]
    def procList(result):
      actCssList = []
      labelCssList = []
      countList = []
      for ip in clientIps:
        actCssList.append('active' if currentIp==ip else '')
        labelCssList.append('' if isRun(ip) else 'label label-important')
        countList.append(countStop(ip))
      request.write(getTemplateContent('proc',clientIps=clientIps,actCssList=actCssList,labelCssList=labelCssList,\
        countList=countList,result=result,**activeCssDict))
    print currentIp
    getDb().runQuery('SELECT procGroup,procName FROM Process WHERE clientIp = ?',[currentIp]).addCallback(procList).addBoth(finishRequest,request)
    return NOT_DONE_YET

root = RootResource()
root.putChild("static", File(os.path.join(dpDir,'web','static')))
root.putChild("favicon.ico", File(os.path.join(dpDir,'web','static','img','favicon.ico')))
