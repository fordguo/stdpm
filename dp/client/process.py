#-*- coding:utf-8 -*- 


from twisted.internet import error,reactor,protocol
from twisted.python.logfile import DailyLogFile,LogFile
from datetime import datetime
from dp.common import SIGNAL_NAME,PROC_STATUS,getDatarootDir,dpDir,LPConfig,TIME_FORMAT,CR
from dep_resolver import resortPs,SEP

import os,time
import yaml
import glob

procGroupDict = {}
sendStatusFunc = None
LAST_END = 8192

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

def startAll():
  for uniName in resortPs(procGroupDict):
    gpName,psName = uniName.split(SEP)
    procGroupDict[gpName].startProc(psName)

def stopAll():
  for procGroup in procGroupDict.itervalues():
    procGroup.stop()


def restartProc(psGroup,psName,secs=10):
  pg = procGroupDict.get(psGroup)
  if pg:
    pg.restartProc(psName,secs)
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
  logFd.write("%s,%s%s"%(fname,datetime.now().strftime(TIME_FORMAT),CR))
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
def getPsLog(psGroup,psName):
  pg = procGroupDict.get(psGroup)
  if pg:
    localValue = pg.locals.get(psName)
    if localValue:
      localProc = localValue[0]
      fsize = os.path.getsize(localProc.logFile.path)
      with open(localProc.logFile.path,'r') as f:
        if fsize>LAST_END:
          f.seek(-LAST_END,os.SEEK_END)
        return f.read()
  return None

class ProcessGroup:
  def __init__(self,yamlFile):
    self.yamlFile = yamlFile
    self.name = _getFname(yamlFile)
    self.groupDir = dirName = os.path.join(getDatarootDir(),'data','ps',self.name)
    if not os.path.exists( dirName):
      os.makedirs(dirName)
    self.procsMap = None
    self.locals = {}
    self.reload()
  def _start(self,name,procInfo):
    localValue = self.locals.get(name)
    localProc = LocalProcess(name,self)
    conf = None
    if localValue:
      localValue[0] =localProc
      conf = localValue[1]
    else:
      conf = LPConfig(procInfo)
      localValue = [localProc,conf]
      self.locals[name] = localValue
    reactor.spawnProcess(localProc,conf.executable, conf.execArgs,conf.env,\
      conf.path,conf.uid,conf.gid,conf.usePTY,conf.childFDs)
  def reload(self):
    self.procsMap = yaml.load(file(self.yamlFile))
  def startProc(self,procName):
    localProc = self.locals.get(procName)
    if localProc is None or  not localProc[0].isRunning():
      self._start(procName,self.procsMap[procName])

  def iterStatus(self):
    return self.locals.iteritems()
  def iterMap(self):
    return self.procsMap.iteritems()
  def stop(self):
    for localValue in self.locals.itervalues():
      if localValue[0].isRunning():
        self._forceStopProcess(localValue[0],None,False)
  def _forceStopProcess(self,localProc,procName,restart=False):
    try:
      localProc.signal(SIGNAL_NAME.KILL)
    except error.ProcessExitedAlready:
      pass
    if restart:
      time.sleep(3)
      self.startProc(procName)
  def _stopProc(self,localProc,killTime,procName,restart=False):
    try:
      localProc.signal(SIGNAL_NAME.TERM)
    except error.ProcessExitedAlready:
      if restart:
        time.sleep(killTime)
        self.startProc(procName)
      pass
    else:
      reactor.callLater(killTime,self._forceStopProcess,localProc,procName,restart)
  def stopProc(self,procName,killTime=3,restart=False):
    localValue = self.locals[procName]
    localProc = localValue[0]
    localProc.status = PROC_STATUS.STOPPING
    self._stopProc(localProc,killTime,procName,restart)
  def restartProc(self,procName,secs=10):
    self.stopProc(procName,secs,True)
  def checkRestart(self):
    now = datetime.now()
    for name,localValue in self.iterStatus():
      localProc = localValue[0]
      period = localValue[1].getPeriod()
      if localProc.endTime and not localProc.isRunning() and \
        period is not None and (now-localProc.endTime).seconds > (period*60):
        self.startProc(name)

class LocalProcess(protocol.ProcessProtocol):
  def __init__(self, name,group):
    self.orgName = name
    self.name = "".join([x for x in name if x.isalnum()])
    self.group = group
    self.logFile = LogFile(self.name+".log",group.groupDir,maxRotatedFiles=10)
    self.updateLogFile = LogFile(self.name+".ulog",group.groupDir,rotateLength=1000000000,maxRotatedFiles=3)#100M
    self.status = PROC_STATUS.STOP
    self.endTime = None

  def connectionMade(self):
    self.status = PROC_STATUS.RUN#todo add support startCompletion check
    self._writeLog("[processStarted] at:%s"%(datetime.now().strftime(TIME_FORMAT)))
    global sendStatusFunc
    if sendStatusFunc:
      sendStatusFunc(self.group.name,self.orgName,self.status)

  def _writeLog(self,data):
    self.logFile.write("%s%s"%(data,CR)) 
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
      self._writeLog("[processEnded] code is None,info:%s"% (reason))
    elif reason.value.exitCode != 0 :
      self._writeLog("[processEnded] code:%d,info:%s"% (reason.value.exitCode,reason))
    self.status = PROC_STATUS.STOP
    self._writeLog("[processEnded] at:%s"%(self.endTime.strftime(TIME_FORMAT)))
    global sendStatusFunc
    if sendStatusFunc:
      sendStatusFunc(self.group.name,self.orgName,self.status)

  def signal(self,signalName):
    self.transport.signalProcess(signalName.name)
