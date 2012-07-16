#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor,task

import json
import yaml
from process import procGroupDict,initYaml
from dp.client.ftp import downloadFiles
from dp.common import JSON,JSON_LEN,changeDpDir

client = None

version="1.0.1"

def minuteCheck():
  if client is None:return
  for procGroup in procGroupDict.itervalues():
    for name,proc in procGroup.iterStatus():
      client.sendJson(json.dumps({'action':'procStatus','value':{'group':procGroup.name,\
        'name':name,'status':proc.status.name}}))

looping = task.LoopingCall(minuteCheck)

class CoreClient(NetstringReceiver):
  def __init__(self):
    pass
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
      print value
      if value=='Restart':
        reactor.stop()
    else:
      print 'unknown json %s'%json
  def sendJson(self,string):
    self.sendString("json:"+string)

  def sendYaml(self,string):
    self.sendString("yaml:"+string)

class CoreClientFactory(ReconnectingClientFactory):

  def __init__(self):
    pass
    
  def buildProtocol(self, addr):
    self.resetDelay()
    return CoreClient()

from twisted.application import internet, service
def makeService(config):
  clientService = service.MultiService()
  changeDpDir(config['dataDir'])
  initYaml(config['confDir'])
  looping.start(10)
  internet.TCPClient(config['server'],config['port'], CoreClientFactory()).setServiceParent(clientService)
  return clientService

