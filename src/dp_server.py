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
clientIps = set()
clientProtocolDict = {}

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
      txn.execute('CREATE TABLE Process(clientIp VARCHAR(64),procGroup VARCHAR(255),procName VARCHAR(255),procInfo TEXT,\
        PRIMARY KEY(clientIp,procGroup,procName))')
    else:
      def initDb(result):
        for res in result:
          ip = res[0]
          if ip not in clientIps:
            clientIps.add(ip)
          _checkResourceDictName(uniqueProcName(ip,res[1],res[2]),)
      db.runQuery('SELECT clientIp,procGroup,procName  FROM Process').addCallback(initDb)
  db.runInteraction(check).addCallback(lambda x:x)
def getDb():
  return db
def getStatus(name):
  return resourceDict.get(name,DEFAULT_INVALID)

def isRun(name):
  return resourceDict.get(name,DEFAULT_INVALID)['status']==PROC_STATUS.RUN
def countStop(ip):
  return len(filter(lambda x: x[0].startswith(ip+':') and x[1]['status']==PROC_STATUS.STOP,resourceDict.iteritems()))
def uniqueProcName(ip,group,name):
  return "%s:%s:%s"%(ip,group,name)
def splitProcName(name):
  return name.split(":")

def _checkResourceDictName(name,status=None):
  value = resourceDict.get(name)
  status = PROC_STATUS.STOP if status is None else status
  if value is None:
    resourceDict[name] = {'status':status,'lastUpdated':datetime.now()}
  else:
    value['status'] = status
    value['lastUpdated'] = datetime.now()
class CoreServer(NetstringReceiver):
  def __init__(self):
    self.ip = None
  def _getIp(self):
    if not self.ip:
      self.ip =  self.transport.getPeer().host
    return self.ip
  def connectionMade(self):
    clientIp = self._getIp()
    resourceDict[clientIp] = {'status':PROC_STATUS.RUN,"lastUpdated":datetime.now()}
    clientProtocolDict[clientIp] = self
    clientIps.add(clientIp)
  def connectionLost(self, reason):
    clientIp = self._getIp()
    del resourceDict[clientIp]
    del clientProtocolDict[clientIp]

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
    return uniqueProcName(self._getIp(),value['group'],value['name'])

  def _processYaml(self,group,name,yamlStr):
    db.runOperation('INSERT OR REPLACE INTO Process(clientIp,procGroup,procName,procInfo) VALUES(?,?,?,?)',
      (self._getIp(),group,name,yamlStr)).addCallback(lambda x:x)

class CoreServerFactory(Factory):
  protocol = CoreServer
  def __init__(self):
    init()  
