#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ReconnectingClientFactory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor,task

import json
from dp_process import procGroupDict,initYaml
from dp_ftp_client import downloadFiles

client = None

def minuteCheck():
  if client is None:return
  for procGroup in procGroupDict.itervalues():
    for name,proc in procGroup.locals.iteritems():
      client.sendJson(json.dumps({'procStatus': {'group':procGroup.name,\
        'name':name,'status':proc.status.name}}))

looping = task.LoopingCall(minuteCheck)

class CoreClient(NetstringReceiver):
  def __init__(self):
    pass
  def connectionMade(self):
    global client
    client = self
  def connectionLost(self, reason):
    global client
    client = None

  def stringReceived(self, string):
    print "---str:",string

  def sendJson(self,string):
    self.sendString("json:"+string)

  def sendYaml(self,string):
    self.sendString("yaml:"+string)

  def sendText(self,string):
    self.sendString("text:"+string)

class CoreClientFactory(ReconnectingClientFactory):

  def __init__(self,):
    looping.start(60)
    initYaml()
    downloadFiles()

  def buildProtocol(self, addr):
    self.resetDelay()
    return CoreClient()
