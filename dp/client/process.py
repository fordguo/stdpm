#-*- coding:utf-8 -*- 


from twisted.internet import error,reactor,protocol
from twisted.python.logfile import DailyLogFile,LogFile
from datetime import datetime
from dp.common import SIGNAL_NAME,PROC_STATUS,getDatarootDir,dpDir,LPConfig,TIME_FORMAT,CR

import os,time
import yaml
import glob

PS_BASIC = ['executable','args','path','user','group','usePTY','childFDs']

procGroupDict = {}

def initYaml(yamlDir=None):
  if yamlDir is None:
    yamlDir = os.path.join(dpDir,'..','conf')
  files = glob.glob(os.path.join(yamlDir,'*.yaml'))
  for f in files:
    pg = ProcessGroup(f)
    procGroupDict[pg.name] = pg
    pg.start()

def restartProc(psGroup,psName):
  pg = procGroupDict.get(psGroup)
  if pg:
    pg.restartProc(psName)
  else:
    print 'can not found process group:'+psGroup

def getLPConfig(psGroup,psName):
  pg = procGroupDict.get(psGroup)
  if pg:
    procInfo = pg.procsMap.get(psName)
    if procInfo:
      return LPConfig(procInfo)
  return None

def updateLog(psGroup,psName,fname):
  if psGroup is None: return
  pg = procGroupDict.get(psGroup)
  if pg:
    localProc = pg.locals.get(psName)
    if localProc:
      localProc.logUpdate(fname)

class ProcessGroup:
  def __init__(self,yamlFile):
    fileName = os.path.basename(yamlFile)
    self.name = os.path.splitext(fileName)[0]
    self.groupDir = dirName= os.path.join(getDatarootDir(),'data','ps',self.name)
    if not os.path.exists( dirName):
      os.makedirs(dirName)
    self.procsMap = yaml.load(file(yamlFile))
    self.locals = {}
  def start(self):
    for name,procInfo in self.procsMap.iteritems():
      self._start(name,procInfo)
  def _start(self,name,procInfo):
    localProc = LocalProcess(name,self)
    conf = LPConfig(procInfo)
    self.locals[name] = localProc
    reactor.spawnProcess(localProc,conf.executable, conf.execArgs,conf.env,\
      conf.path,conf.user,conf.group,conf.usePTY,conf.childFDs)
  def startProc(self,procName):
    localProc = self.locals[procName]
    if localProc and not localProc.isRunning():
      self._start(procName,self.procsMap[procName])
    else:
      print 'process '+procName +' have not found or have been started.'

  def iterStatus(self):
    return self.locals.iteritems()
  def iterMap(self):
    return self.procsMap.iteritems()
  def stop(self):
    for localProc in self.locals.itervalues():
      if localProc.isRunning():
        self._stopProc(localProc,1)
    self.locals.clear()
  def _forceStopProcess(self,localProc):
    try:
      localProc.signal(SIGNAL_NAME.KILL)
    except error.ProcessExitedAlready:
      pass
  def _stopProc(self,localProc,killTime):
    try:
      localProc.signal(SIGNAL_NAME.TERM)
    except error.ProcessExitedAlready:
      pass
    else:
      reactor.callLater(killTime,self._forceStopProcess,localProc)
  def stopProc(self,procName,killTime=3):
    localProc = self.locals[procName]
    if localProc and localProc.isRunning():
      localProc.status = PROC_STATUS.STOPPING
      self._stopProc(localProc,killTime)
      del self.locals[procName]
    else:
      print 'process '+procName +' have not found or have been stopped.'
  def restartProc(self,procName,secs=1,clearCache=False):
    localProc = self.locals[procName]
    if localProc and localProc.isRunning():
      self.stopProc(procName)
      time.sleep(secs)
    self.startProc(procName)

    
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
    self.status = PROC_STATUS.RUN
    self._writeLog("[processStarted] at:%s"%(datetime.now().strftime(TIME_FORMAT)))
  def _writeLog(self,data):
    self.logFile.write("%s%s"%(data,CR)) 
  def logUpdate(self,fname):
    self.updateLogFile.write("%s,%s%s"%(fname,datetime.now().strftime(TIME_FORMAT),CR))

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

  def signal(self,signalName):
    self.transport.signalProcess(signalName.name)
