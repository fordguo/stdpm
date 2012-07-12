#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor,task

import json
import yaml
from dp_process import procGroupDict,initYaml
from dp_ftp_client import downloadFiles

client = None

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
  def connectionLost(self, reason):
    global client
    client = None

  def stringReceived(self, string):
    print "---str:",string

  def sendJson(self,string):
    self.sendString("json:"+string)

  def sendYaml(self,string):
    self.sendString("yaml:"+string)

class CoreClientFactory(ReconnectingClientFactory):

  def __init__(self):
    looping.start(10)
    initYaml()

  def buildProtocol(self, addr):
    self.resetDelay()
    return CoreClient()
