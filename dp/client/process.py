#-*- coding:utf-8 -*- 


from twisted.internet import error,reactor,protocol
from twisted.python.logfile import DailyLogFile,LogFile
from datetime import datetime
from dp.common import SIGNAL_NAME,PROC_STATUS,getDatarootDir,dpDir,LPConfig,TIME_FORMAT,CR,SEP
from dep_resolver import resortPs,DEP_SEP

import os,time
import yaml
import glob

procGroupDict = {}
sendStatusFunc = None
LAST_END = 4096

def registerSendStatus(func):
  global sendStatusFunc
  sendStatusFunc = func

def initYaml(yamlDir=None):
  if yamlDir is None:
    yamlDir = os.path.join(dpDir,'..','conf')
  files = glob.glob(os.path.join(yamlDir,'*.yaml'))
  for f in files:
    name = _getFname(f)
    pg = procGroupDict.get(name)
    if pg is None:
      pg = ProcessGroup(f)
      procGroupDict[name] = pg
    else:
      pg.reload()
def _getFname(fullFile):
    fileName = os.path.basename(fullFile)
    return os.path.splitext(fileName)[0]

def startAll(memo):
  for uniName in resortPs(procGroupDict):
    gpName,psName = uniName.split(DEP_SEP)
    procGroupDict[gpName].startProc(psName,memo)

def stopAll():
  for procGroup in procGroupDict.itervalues():
    procGroup.stop()


def restartProc(psGroup,psName,secs=10,memo=''):
  pg = procGroupDict.get(psGroup)
  if pg:
    pg.restartProc(psName,secs,memo)
  else:
    print 'can not found process group:'+psGroup

def getLPConfig(psGroup,psName):
  pg = procGroupDict.get(psGroup)
  if pg:
    procInfo = pg.procsMap.get(psName)
    if procInfo:
      return LPConfig(procInfo)
  return None

def _updateLog(logFd,fname):
  logFd.write("%s%s%s%s"%(fname,SEP,datetime.now().strftime(TIME_FORMAT),CR))
_clientUpdateLogFile = os.path.join(getDatarootDir(),'data','clientUpdateLog.ulog')
def clientUpdateLog(fname):
  with open(_clientUpdateLogFile,'w+') as f:
    _updateLog(f,fname)
def updateLog(psGroup,psName,fname):
  if psGroup is None: return
  pg = procGroupDict.get(psGroup)
  if pg:
    localValue = pg.locals.get(psName)
    if localValue:
      localValue[0].logUpdate(fname)
def _lastUpdateTime(logFd):
  fsize = os.path.getsize(logFd.name)
  if fsize>100:
    logFd.seek(-100,os.SEEK_END)
  lines = logFd.readlines()
  if len(lines)>0:
    return lines[-1].split(',')[1].strip()
  else:
    return None
def lastFileUpdateTime(psGroup,psName):
  if psGroup is None and os.path.exists(_clientUpdateLogFile):
    with open(_clientUpdateLogFile,'r') as f:
      return _lastUpdateTime(f)
  pg = procGroupDict.get(psGroup)
  if pg:
    localValue = pg.locals.get(psName)
    if localValue:
      with open(localValue[0].updateLogFile.path,'r') as f:
        return _lastUpdateTime(f)
  return None
def getPsLog(psGroup,psName,startPos=None,endPos=None,suffix=None,logType='console',checkSuffix=True,lastEndSize=LAST_END):
  pg = procGroupDict.get(psGroup)
  if pg:
    localValue = pg.locals.get(psName)
    if localValue:
      localProc = localValue[0]
      if logType=='console':
        return _logContent(localProc.logFile.path,startPos,endPos,suffix,checkSuffix)
      elif logType=='log':
        if localValue[1].logFullName:
          return _logContent(localValue[1].logFullName,startPos,endPos,suffix,checkSuffix)
        else:return None,None,None,None
      elif logType=='start':
        return _logContent(localProc.ssLogFile.path,startPos,endPos,suffix,checkSuffix)
      elif logType=='update':
        return _logContent(localProc.updateLogFile.path,startPos,endPos,suffix,checkSuffix)
  return None,None,None,None
def _logContent(fname,startPos=None,endPos=None,suffix=None,checkSuffix=True,lastEndSize=LAST_END):
  suffixes = ''
  mtime = None
  if checkSuffix:
    flen = len(fname)+1  
    suffixes = [d[flen:] for d in glob.glob('%s.*'%fname)]
    suffixes.sort()
    suffixes = ','.join(suffixes)
    if suffix :fname = '%s.%s'%(fname,suffix)
    mtime = os.path.getmtime(fname)
  fsize = os.path.getsize(fname)
  if startPos is None: startPos = fsize - lastEndSize
  if endPos is None: endPos = fsize
  if startPos<0: startPos = 0
  with open(fname,'r') as f:
    f.seek(startPos,os.SEEK_SET)
    return f.read(endPos-startPos),fsize,mtime,suffixes
def logSize(psGroup,psName,logType):
  pg = procGroupDict.get(psGroup)
  if pg:
    localValue = pg.locals.get(psName)
    if localValue:
      localProc = localValue[0]
      if logType=='console':
        return os.path.getsize(localProc.logFile.path)
      elif logType=='log':
        if localValue[1].logFullName:
          return os.path.getsize(localValue[1].logFullName)
        else:return None
      elif logType=='start':
        return os.path.getsize(localProc.ssLogFile.path)
      elif logType=='update':
        return os.path.getsize(localProc.updateLogFile.path)
  return None
class ProcessGroup:
  def __init__(self,yamlFile):
    self.yamlFile = yamlFile
    self.name = _getFname(yamlFile)
    self.groupDir = dirName = os.path.join(getDatarootDir(),'data','ps',self.name)
    if not os.path.exists( dirName):
      os.makedirs(dirName)
    self.procsMap = None #yaml map
    self.locals = {}#key is procName,value[0] is LocalProcess,value[1] is LPConfig
    self.reload()
    self.tailMap = {} #key is procName log/console,value is lastSize
  def _start(self,name,procInfo,memo=''):
    localValue = self.locals.get(name)
    localProc = LocalProcess(name,self)
    conf = None
    if localValue:
      localValue[0] =localProc
      conf = localValue[1]
    else:
      conf = LPConfig(procInfo)
      conf.verifyLog()
      localValue = [localProc,conf]
      self.locals[name] = localValue
    localProc.startMemo = memo
    reactor.spawnProcess(localProc,conf.executable, conf.execArgs,conf.env,\
      conf.path,conf.uid,conf.gid,conf.usePTY,conf.childFDs)
  def reload(self):
    self.procsMap = yaml.load(file(self.yamlFile))
  def startProc(self,procName,memo=''):
    localProc = self.locals.get(procName)
    if localProc is None or  not localProc[0].isRunning():
      self._start(procName,self.procsMap[procName],memo)

  def iterStatus(self):
    return self.locals.iteritems()
  def iterMap(self):
    return self.procsMap.iteritems()
  def stop(self):
    for localValue in self.locals.itervalues():
      if localValue[0].isRunning():
        self._forceStopProcess(localValue[0],None,False)
  def _forceStopProcess(self,localProc,procName,restart=False,memo=''):
    try:
      localProc.signal(SIGNAL_NAME.KILL)
    except error.ProcessExitedAlready:
      pass
    if restart:
      time.sleep(3)
      self.startProc(procName,memo)
  def _stopProc(self,localProc,killTime,procName,restart=False,memo=''):
    try:
      localProc.signal(SIGNAL_NAME.TERM)
    except error.ProcessExitedAlready:
      if restart:
        time.sleep(killTime)
        self.startProc(procName,memo)
      pass
    else:
      reactor.callLater(killTime,self._forceStopProcess,localProc,procName,restart,memo)
  def stopProc(self,procName,killTime=3,restart=False,memo=''):
    localValue = self.locals[procName]
    localProc = localValue[0]
    localProc.status = PROC_STATUS.STOPPING
    self._stopProc(localProc,killTime,procName,restart,memo)
  def restartProc(self,procName,secs=10,memo=''):
    self.stopProc(procName,secs,True,memo)
  def checkRestart(self):
    now = datetime.now()
    for name,localValue in self.iterStatus():
      localProc = localValue[0]
      period = localValue[1].getPeriod()
      if localProc.endTime and not localProc.isRunning() and \
        period is not None and (now-localProc.endTime).seconds > (period*60):
        self.startProc(name,'period')
      if localValue[1].monEnable and localProc.isRunning():
        if self._checkLogContent(name,'console',localValue):
          self.startProc(name,'period_console')
        elif self._checkLogContent(name,'log',localValue):
          self.startProc(name,'period_log')
  def _checkLogContent(self,name,logType,localValue):
    localProc = localValue[0]
    tailName = '%s_%s'%(name,logType)
    oldLastSize = self.tailMap.get(tailName)
    lastSize = None
    isRestart = False
    def checkContent(delta):
      content,_,_,_ = getPsLog(localProc.group.name,name,None,None,None,logType,False,delta)
      keywords = localValue[1].monKeywords()
      if keywords:
        for key in keywords:
          if content.find(key)>=0: 
            isRestart = True
            break

    if oldLastSize is None:
      lastSize = logSize(localProc.group.name,name,logType)
      if lastSize>0:
        checkContent(1024)
    else:
      lastSize = logSize(localProc.group.name,name,logType)
      if lastSize>0:
        delta = abs(lastSize-oldLastSize)
        if delta>0 :
          if delta>1024:delta = 1024
          checkContent(delta)
    self.tailMap[tailName] = lastSize
    return isRestart

class LocalProcess(protocol.ProcessProtocol):
  def __init__(self, name,group):
    self.orgName = name
    self.name = "".join([x for x in name if x.isalnum()])
    self.group = group
    self.logFile = LogFile(self.name+".log",group.groupDir,rotateLength=100000000,maxRotatedFiles=10)#10M
    self.updateLogFile = LogFile(self.name+".ulog",group.groupDir,rotateLength=100000000,maxRotatedFiles=5)
    self.ssLogFile = LogFile(self.name+".slog",group.groupDir,rotateLength=100000000,maxRotatedFiles=5)
    self.status = PROC_STATUS.STOP
    self.endTime = None
    self.startMemo = ''

  def connectionMade(self):
    self.status = PROC_STATUS.RUN#todo add support startCompletion check
    self._ssLog("startTime",datetime.now().strftime(TIME_FORMAT),self.startMemo)
    self.startMemo = ''
    global sendStatusFunc
    if sendStatusFunc:
      sendStatusFunc(self.group.name,self.orgName,self.status)

  def _writeLog(self,data):
    self.logFile.write("%s%s"%(data,CR)) 
  def _ssLog(self,stage,time,memo=''):
    self.ssLogFile.write("%s%s%s%s%s%s"%(stage,SEP,time,SEP,memo,CR)) 
  def logUpdate(self,fname):
    _updateLog(self.updateLogFile,fname)

  def outReceived(self, data):
    self._writeLog(data)
  def errReceived(self, data):
    self._writeLog("[ERROR DATA %s]:%s"%(datetime.now().strftime(TIME_FORMAT),data))
  def childDataReceived(self, childFD, data):
    self._writeLog(data)
  def inConnectionLost(self):
    pass
  def outConnectionLost(self):
    pass
  def errConnectionLost(self):
    pass
  def childConnectionLost(self, childFD):
    pass

  def isRunning(self):
    return self.status == PROC_STATUS.RUN

  def processExited(self,reason):
    pass
  def processEnded(self,reason):
    self.endTime = datetime.now()
    if reason.value.exitCode is None:
      self._ssLog("endInfo","code is None,info:%s"% (reason))
    elif reason.value.exitCode != 0 :
      self._ssLog("endInfo", "code:%d,info:%s"%(reason.value.exitCode,reason))
    self.status = PROC_STATUS.STOP
    self._ssLog("endTime",self.endTime.strftime(TIME_FORMAT))
    global sendStatusFunc
    if sendStatusFunc:
      sendStatusFunc(self.group.name,self.orgName,self.status)
    self.logFile.close()
    self.updateLogFile.close()
    self.ssLogFile.close()

  def signal(self,signalName):
    self.transport.signalProcess(signalName.name)
