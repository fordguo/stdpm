#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor,task

import os,json
import yaml
from process import procGroupDict,initYaml,restartProc,getLPConfig
from dp.client.ftp import downloadFiles
from dp.common import JSON,JSON_LEN,changeDpDir,selfFileSet

client = None

version="1.0.1"


def minuteCheck():
  if client is None:return
  for procGroup in procGroupDict.itervalues():
    for name,proc in procGroup.iterStatus():
      client.sendJson(json.dumps({'action':'procStatus','value':{'group':procGroup.name,\
        'name':name,'status':proc.status.name}}))

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
    for procGroup in procGroupDict.itervalues():
      for name,procInfo in procGroup.iterMap():
        self.sendYaml("%s:%s:%s"%(procGroup.name,name.replace(':','_-_'),yaml.dump(procInfo,default_flow_style=None)))
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
      elif value=='Patch':
        downloadFiles(self.config,selfFileSet)
    elif action=='procOp':
      psGroup = json['grp']
      psName = json['name']
      op = json['op']
      if op=='Restart':
        restartProc(psGroup,psName)
      elif op=='Patch':
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
  initYaml(config['confDir'])
  looping.start(10)
  internet.TCPClient(config['server'],config['port'], CoreClientFactory(config)).setServiceParent(clientService)
  return clientService

