#-*- coding:utf-8 -*- 

from twisted.internet.protocol import Factory
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor
from twisted.enterprise import adbapi

from datetime import datetime
import os,uuid
import json

from dp.common import PROC_STATUS,getDatarootDir,checkDir,JSON,JSON_LEN,changeDpDir,selfFileSet,dpDir,TIME_FORMAT,SEP

version = "1.0.4"

DEFAULT_INVALID = {'status':PROC_STATUS.STOP,'lastUpdated':None,'fileUpdated':None}
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

def _total_seconds(td):
  return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6
def isRun(name):
  status = resourceDict.get(name,DEFAULT_INVALID)['status']==PROC_STATUS.RUN
  ipInfo = clientIpDict.get(name)
  if ipInfo and ipInfo.get('lastShaked'):
    lastShake = ipInfo['lastShaked']
    return status and _total_seconds(datetime.now()-lastShake)<300
  return status
def countStop(ip):
  return len(filter(lambda x: x[0].startswith(ip+SEP) and x[1]['status']==PROC_STATUS.STOP,resourceDict.iteritems()))
def uniqueProcName(ip,group,name):
  return "%s%s%s%s%s"%(ip,SEP,group,SEP,name)
def splitProcName(name):
  return name.split(SEP)

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
    self.uuidDict = {}
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
    _checkIpDict(clientIp)['protocol'] = None

  def stringReceived(self, string):
    if string.startswith(JSON):
      self._processJson(json.loads(string[JSON_LEN:]))
    elif string.startswith(YAML):
      idx = string.find(':',YAML_LEN+1)
      nIdx = string.find(':',idx+1)
      name = string[idx+1:nIdx].replace(SEP,':')
      self._processYaml(string[YAML_LEN:idx],name,string[nIdx+1:])
    elif string.startswith(TXT):
      idx = string.find(':',TXT_LEN+1)
      uuidStr = string[TXT_LEN:idx]
      value = self.uuidDict.get(uuidStr)
      if value:
        content = string[idx+1:]
        val,idx = self._findSepContent(content,None)
        valMap = {'size':long(val)}
        val,idx = self._findSepContent(content,idx)
        valMap['time'] = long(val)
        val,idx = self._findSepContent(content,idx)
        valMap['suffixes'] = val
        valMap['content'] = content[idx+len(SEP):]
        value.put(valMap)
        del self.uuidDict[uuidStr]
  def _findSepContent(self,string,idx=None):
    if idx is None:
      idx = -len(SEP)
      nIdx = string.find(SEP)
    else:
      nIdx =  string.find(SEP,idx+1)
    return string[idx+len(SEP):nIdx],nIdx
  def _processJson(self,json):
    action = json.get('action')
    clientIp = self._getIp()
    if action=='procStatus':
      name = self._procName(json)
      status = resourceDict.get(name)
      if not status:
        resourceDict[name] = {'status':PROC_STATUS.lookupByName(json['status']),'lastUpdated':datetime.now()}
      else:
        status['status'] = PROC_STATUS.lookupByName(json['status'])
        status['lastUpdated'] = datetime.now()
    elif action=='clientVersion':
      result = _checkIpDict(clientIp)
      result['version'] = json['value']
    elif action=='clientStatus':
      result = _checkIpDict(clientIp)
      result['lastShaked'] = datetime.now()
    elif action=='fileUpdate':
      if json['group']:
        name = self._procName(json)
      else:
        name = clientIp
      if json['datetime']:
        resourceDict.get(name)['fileUpdated'] = datetime.strptime(json['datetime'],TIME_FORMAT)
    elif action=='procLogInfo':
      name = self._procName(json)
      resourceDict.get(name)['monLog'] = json['monLog']
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
  def asyncSendJson(self,jsonMap,defQueue):
    uuidStr = uuid.uuid4().hex
    jsonMap['uuid'] = uuidStr
    self.uuidDict[uuidStr] = defQueue
    self.sendJson(json.dumps(jsonMap))

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
  site = server.Site(root)
  internet.TCPServer(int(config['httpPort']),site).setServiceParent(serverService)
  return serverService

