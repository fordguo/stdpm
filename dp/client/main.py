#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor,task

import os,json
import yaml
import process
from process import procGroupDict,lastFileUpdateTime
from dp.client.ftp import downloadFiles
from dp.common import JSON,JSON_LEN,changeDpDir,selfFileSet,SEP

client = None

version="1.0.3"

loopCount = 0

def minuteCheck():
  global loopCount
  loopCount += 1
  if client is None:return
  client.sendJson(json.dumps({'action':'clientStatus','value':''}))
  for procGroup in procGroupDict.itervalues():
    procGroup.checkRestart()
    if loopCount%5==0:
      for name,proc in procGroup.iterStatus():
        client.sendProcStatus(procGroup.name,name,proc[0].status)      
looping = task.LoopingCall(minuteCheck)

def getClient():
  global client
  return client

class CoreClient(NetstringReceiver):
  def __init__(self,config):
    self.config = config
  def connectionMade(self):
    global client
    client = self
    process.registerSendStatus(self.sendProcStatus)
    self.sendFileUpdate(None,None,lastFileUpdateTime(None,None))
    self._initSend()
    self.sendJson(json.dumps({'action':'clientVersion','value':version}))

  def _initSend(self):
    for procGroup in procGroupDict.itervalues():
      for name,procInfo in procGroup.iterMap():
        self.sendYaml("%s:%s:%s"%(procGroup.name,name.replace(':',SEP),yaml.dump(procInfo,default_flow_style=None)))
      for name,proc in procGroup.iterStatus():
        self.sendProcStatus(procGroup.name,name,proc[0].status)
        self.sendFileUpdate(procGroup.name,name,lastFileUpdateTime(procGroup.name,name))
  def connectionLost(self, reason):
    global client
    client = None

  def stringReceived(self, string):
    if string.startswith(JSON):
      self._processJson(json.loads(string[JSON_LEN:]))
    else:
      print 'string is not json %s'%string

  def _processJson(self,json):
    action = json.get('action')
    if action=='clientOp':
      value = json['value']
      if value=='Restart':
        reactor.stop()
      elif value=='Update':
        downloadFiles(self.config,selfFileSet)
      elif value=='Reload':
        process.initYaml()
        process.startAll()
        self._initSend()
      else:
        print 'unknown clientOp value:'+value
    elif action=='procOp':
      psGroup = json['grp']
      psName = json['name']
      op = json['op']
      if op=='Restart':
        process.restartProc(psGroup,psName)
      elif op=='Update':
        self._updateProc(psGroup,psName)
      elif op=='Console':
        self.sendLogTxt(json['uuid'],*(process.getPsLog(psGroup,psName,json.get('startPos'),json.get('endPos'))))
      else:
        print 'unknown procOp value:'+op
    elif action=='groupOp':
      psGroup = json['grp']
      op = json['op']
      if op=='Restart':
        pg = procGroupDict.get(psGroup)
        if pg:
          for name,proc in pg.iterStatus():
            pg.restartProc(name)
        else:
          print 'restart group,can not found process group:'+psGroup
      elif op=='Update':
        pg = procGroupDict.get(psGroup)
        if pg:
          for name,proc in pg.iterStatus():
            self._updateProc(psGroup,name)
        else:
          print 'update group,can not found process group:'+psGroup
    else:
      print 'unknown json %s'%json
  def _updateProc(self,grpName,procName):
    lp = process.getLPConfig(grpName,procName)
    if lp:
      updateInfo = lp.fileUpdateInfo()
      if len(updateInfo) > 0:
        downloadFiles(self.config,updateInfo[1][1],grpName,procName,updateInfo[0][1],self)
    else:
      print 'can not found LPConfig with '+json
  def sendJson(self,string):
    self.sendString("json:%s"%string)

  def sendYaml(self,string):
    self.sendString("yaml:%s"%string)

  def sendLogTxt(self,uuid,content,size,modifyTime,suffixes):
    self.sendTxt(uuid,'%(size)d%(sep)s%(modifyTime)d%(sep)s%(suffixes)s%(sep)s%(content)s'%{'sep':SEP,'size':size,\
      'modifyTime':modifyTime,'suffixes':suffixes,'content':content})
  def sendTxt(self,uuid,string):
    if string is None:
      string = 'No Data'
    self.sendString("txt:%s:%s"%(uuid,string.decode('unicode_escape').encode('utf-8','ignore')))

  def sendProcStatus(self,procGroup,procName,status):
    self.sendJson(json.dumps({'action':'procStatus','group':procGroup,'name':procName,'status':status.name}))
  def sendFileUpdate(self,procGroup,procName,strTime):
    self.sendJson(json.dumps({'action':'fileUpdate','group':procGroup,'name':procName,'datetime':strTime}))

class CoreClientFactory(ReconnectingClientFactory):
  def __init__(self,config):
    self.config = config
    
  def buildProtocol(self, addr):
    self.resetDelay()
    return CoreClient(self.config)

from twisted.application import internet, service
def makeService(config):
  clientService = service.MultiService()
  changeDpDir(config['dataDir'])
  process.initYaml()
  process.startAll()
  looping.start(60)
  internet.TCPClient(config['server'],int(config['port']), CoreClientFactory(config)).setServiceParent(clientService)
  def shutdown():
    process.stopAll()
  reactor.addSystemEventTrigger("before", "shutdown", shutdown)
  return clientService

