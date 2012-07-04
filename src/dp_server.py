#-*- coding:utf-8 -*- 

from twisted.internet.protocol import Factory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor
from twisted.enterprise import adbapi

from datetime import datetime
import os

from dp_common import SIGNAL_NAME,PROC_STATUS,dpDir,checkDir

DEFAULT_INVALID = {'communication':False,'lastUpdated':None}
DATA_DIR="data"

db = None 
resourceDict = {}

def init():
  global db
  dataDir = os.path.join(dpDir,DATA_DIR) 
  checkDir(dataDir)
  db = adbapi.ConnectionPool("sqlite3", database=os.path.join(dataDir,"stdpm.db"),check_same_thread=False)
  def check(txn):
    res = txn.execute("SELECT * FROM sqlite_master WHERE type='table' AND name=?",['Process']).fetchone()
    if res is None:
      txn.execute("CREATE TABLE Process(clientIp VARCHAR(64),procGroup VARCHAR(255),procName VARCHAR(255),procInfo TEXT)")
  db.runInteraction(check).addCallback(lambda x:x)

def getStatus(name):
  return resourceDict.get(name,DEFAULT_INVALID)

class CoreServer(NetstringReceiver):
  def __init__(self):
    self.ip = None
  def _getIp(self):
    if not self.ip:
      self.ip =  self.transport.getPeer().host
    return self.ip
  def connectionMade(self):
    resourceDict[self._getIp()] = {'communication':True,"lastUpdated":datetime.now()}
    print self._getIp()
  def connectionLost(self, reason):
    del resourceDict[self._getIp()]

  def stringReceived(self, string):
    print "---str:",string


class CoreServerFactory(Factory):
  protocol = CoreServer
  def __init__(self):
    init()  
