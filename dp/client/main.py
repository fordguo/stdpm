#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor,task

import os,json
import yaml
from process import procGroupDict,initYaml,restartProc,getLPConfig,registerSendStatus,lastFileUpdateTime
from dp.client.ftp import downloadFiles
from dp.common import JSON,JSON_LEN,changeDpDir,selfFileSet

client = None

version="1.0.2"

loopCount = 0

def minuteCheck():
  global loopCount
  loopCount += 1
  if client is None:return
  if loopCount%5==0:
    for procGroup in procGroupDict.itervalues():
      for name,proc in procGroup.iterStatus():
        client.sendProcStatus(procGroup.name,name,proc.status)
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
    registerSendStatus(self.sendProcStatus)
    self.sendFileUpdate(None,None,lastFileUpdateTime(None,None))
    for procGroup in procGroupDict.itervalues():
      for name,procInfo in procGroup.iterMap():
        self.sendYaml("%s:%s:%s"%(procGroup.name,name.replace(':','_-_'),yaml.dump(procInfo,default_flow_style=None)))
      for name,proc in procGroup.iterStatus():
        self.sendProcStatus(procGroup.name,name,proc.status)
        self.sendFileUpdate(procGroup.name,name,lastFileUpdateTime(procGroup.name,name))
    self.sendJson(json.dumps({'action':'clientVersion','value':version}))
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
    elif action=='procOp':
      psGroup = json['grp']
      psName = json['name']
      op = json['op']
      if op=='Restart':
        restartProc(psGroup,psName)
      elif op=='Update':
        lp = getLPConfig(psGroup,psName)
        if lp:
          updateInfo = lp.fileUpdateInfo()
          downloadFiles(self.config,updateInfo[1][1],psGroup,psName,updateInfo[0][1],self)
        else:
          print 'can not found LPConfig with '+json
      elif op=='Console':
        print json
    else:
      print 'unknown json %s'%json
  def sendJson(self,string):
    self.sendString("json:"+string)

  def sendYaml(self,string):
    self.sendString("yaml:"+string)

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
  initYaml()
  looping.start(60)
  internet.TCPClient(config['server'],int(config['port']), CoreClientFactory(config)).setServiceParent(clientService)
  def shutdown():
    for procGroup in procGroupDict.itervalues():
      procGroup.stop()
  reactor.addSystemEventTrigger("before", "shutdown", shutdown)
  return clientService

