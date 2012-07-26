#-*- coding:utf-8 -*- 

from twisted.internet.protocol import Factory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor
from twisted.enterprise import adbapi

from datetime import datetime
import os
import json

from dp.common import PROC_STATUS,getDatarootDir,checkDir,JSON,JSON_LEN,changeDpDir,selfFileSet,dpDir

version = "1.0.2"

DEFAULT_INVALID = {'status':PROC_STATUS.STOP,'lastUpdated':None}
DATA_DIR="data"

db = None 
resourceDict = {}
clientIpDict = {}

YAML = 'yaml:'
YAML_LEN = len(YAML)

TXT = 'txt:'
TXT_LEN = len(TXT)

def init():
  global db
  dataDir = os.path.join(getDatarootDir(),DATA_DIR) 
  checkDir(dataDir)
  db = adbapi.ConnectionPool("sqlite3", database=os.path.join(dataDir,"stdpm.db"),check_same_thread=False)
  def check(txn):
    res = txn.execute("SELECT * FROM sqlite_master WHERE type='table' AND name=?",['Process']).fetchone()
    if res is None:
      txn.execute('CREATE TABLE Process(clientIp VARCHAR(64),procGroup VARCHAR(255),procName VARCHAR(255),procInfo TEXT,PRIMARY KEY(clientIp,procGroup,procName))')
    else:
      def initDb(result):
        for res in result:
          ip = res[0]
          _checkIpDict(ip)
          _checkResourceDictName(uniqueProcName(ip,res[1],res[2]),)
      db.runQuery('SELECT clientIp,procGroup,procName  FROM Process').addCallback(initDb)
  db.runInteraction(check).addCallback(lambda x:x)

def checkUpdateDir(fileset):
  for f in fileset:
    remoteInfo = f.get('remote')
    if remoteInfo is None: continue
    remoteDir = remoteInfo.get('dir')
    if remoteDir is None: continue
    ftpDir = os.path.join(getDatarootDir(),'data','ftp','data','user',remoteDir)
    if os.path.exists(ftpDir):
      return True
  return False
def _checkIpDict(ip):
  if  not clientIpDict.has_key(ip):
    clientIpDict[ip] = {}
  return clientIpDict[ip]
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
    resourceDict[name] = {'status':status,'lastUpdated':None}
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
    _checkIpDict(clientIp)['protocol'] = self
  def connectionLost(self, reason):
    clientIp = self._getIp()
    del resourceDict[clientIp]
    checkIpDict(clientIp)['protocol'] = None

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
    elif action=='clientVersion':
      result = _checkIpDict(self._getIp())
      result['version'] = json['value']
    elif action=='updateFinish':
      db.runOperation('UPDATE Process SET fileUpdateTime = ? WHERE clientIp=? and procGroup=? and procName=?',\
      (json['datetime'],self._getIp(),json['group'],json['name'])).addCallback(lambda x:x)
    else:
      print 'unknow json:',json
  def _procName(self,value):
    return uniqueProcName(self._getIp(),value['group'],value['name'])

  def _processYaml(self,group,name,yamlStr):
    ip = self._getIp()
    def checkProc(result):
      if len(result)>0:
        db.runOperation('UPDATE Process SET procInfo = ? where clientIp=? and procGroup=? and procName=?',\
          (yamlStr,ip,group,name)).addCallback(lambda x:x)
      else:
        db.runOperation('INSERT INTO Process(clientIp,procGroup,procName,procInfo) VALUES(?,?,?,?)',\
          (ip,group,name,yamlStr)).addCallback(lambda x:x)
    db.runQuery('SELECT procName FROM Process where clientIp=? and procGroup=? and procName=?',(ip,group,name)).addCallback(checkProc)
  
  def sendJson(self,string):
    self.sendString("json:"+string)

class CoreServerFactory(Factory):
  protocol = CoreServer
  def __init__(self):
    init()  

from twisted.application import internet, service
from twisted.web import server
from dp.server.ftp import initFtpFactory
from dp.server.web import root

def makeService(config):
  serverService = service.MultiService()
  changeDpDir(config['dataDir'])
  internet.TCPServer(int(config['mainPort']), CoreServerFactory()).setServiceParent(serverService)
  internet.TCPServer(int(config['ftpPort']),initFtpFactory()).setServiceParent(serverService)
  internet.TCPServer(int(config['httpPort']),server.Site(root)).setServiceParent(serverService)
  return serverService

