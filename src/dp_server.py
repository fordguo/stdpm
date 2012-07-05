#-*- coding:utf-8 -*- 

from twisted.internet.protocol import Factory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor
from twisted.enterprise import adbapi

from datetime import datetime
import os
import json

from dp_common import PROC_STATUS,dpDir,checkDir

DEFAULT_INVALID = {'status':PROC_STATUS.STOP,'lastUpdated':datetime.now()}
DATA_DIR="data"

db = None 
resourceDict = {}

JSON = 'json:'
JSON_LEN = len(JSON)
YAML = 'yaml:'
YAML_LEN = len(YAML)

def init():
  global db
  dataDir = os.path.join(dpDir,DATA_DIR) 
  checkDir(dataDir)
  db = adbapi.ConnectionPool("sqlite3", database=os.path.join(dataDir,"stdpm.db"),check_same_thread=False)
  def check(txn):
    res = txn.execute("SELECT * FROM sqlite_master WHERE type='table' AND name=?",['Process']).fetchone()
    if res is None:
      txn.execute("CREATE TABLE Process(clientIp VARCHAR(64),procGroup VARCHAR(255),procName VARCHAR(255),procInfo TEXT,\
        PRIMARY KEY(clientIp,procGroup,procName))")
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
  def connectionLost(self, reason):
    del resourceDict[self._getIp()]

  def stringReceived(self, string):
    if string.startswith(JSON):
      self._processJson(json.loads(string[JSON_LEN:]))
    elif string.startswith(YAML):
      idx = string.find(':',YAML_LEN+1)
      nIdx = string.find(':',idx+1)
      name = string[idx+1:nIdx].replace('_-_',':')
      self._processYaml(string[YAML_LEN:idx],name,string[nIdx+1:])
  def _processJson(self,json):
    action = json.get('action')
    if action=='procStatus':
      value = json['value']
      name = self._procName(value)
      status = resourceDict.get(name)
      if not status:
        resourceDict[name] = {'status':PROC_STATUS.lookupByName(value['status']),'lastUpdated':datetime.now()}
      else:
        status['status'] = PROC_STATUS.lookupByName(value['status'])
        status['lastUpdated'] = datetime.now()
    else:
      print 'unknow json:',json
  def _procName(self,value):
    return "%s:%s:%s"%(self._getIp(),value['group'],value['name'])

  def _processYaml(self,group,name,yamlStr):
    db.runOperation('INSERT OR REPLACE INTO Process(clientIp,procGroup,procName,procInfo) VALUES(?,?,?,?)',
      (self._getIp(),group,name,yamlStr)).addCallback(lambda x:x)

class CoreServerFactory(Factory):
  protocol = CoreServer
  def __init__(self):
    init()  
