#-*- coding:utf-8 -*- 


from twisted.internet import reactor,protocol
from twisted.python.logfile import DailyLogFile,LogFile
from datetime import datetime
from dp.common import SIGNAL_NAME,PROC_STATUS,getDpDir,LPConfig

import os
import yaml
import glob

PS_BASIC = ['executable','args','path','user','group','usePTY','childFDs']

procGroupDict = {}

def initYaml(yamlDir=None):
  if yamlDir is None:
    yamlDir = os.path.join(getDpDir(),'conf','')
  files = glob.glob(yamlDir+'*.yaml')
  for f in files:
    pg = ProcessGroup(f)
    procGroupDict[pg.name] = pg
    pg.start()

class ProcessGroup:
  def __init__(self,yamlFile):
    fileName = os.path.basename(yamlFile)
    self.name = os.path.splitext(fileName)[0]
    self.groupDir = dirName= os.path.join(getDpDir(),'data','ps',self.name)
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
        localProc.signal(SIGNAL_NAME.KILL)  
  def stopProc(self,procName):
    localProc = self.locals[procName]
    if localProc and localProc.isRunning():
      localProc.status = PROC_STATUS.STOPPING
      localProc.signal(SIGNAL_NAME.KILL)
    else:
      print 'process '+procName +' have not found or have been stopped.'
  def restartProc(self,procName):
    self.stopProc(procName)
    self.startProc(procName)

    
class LocalProcess(protocol.ProcessProtocol):
  def __init__(self, name,group):
    self.name = "".join([x for x in name if x.isalnum()])
    self.group = group
    self.logFile = LogFile(self.name+".log",group.groupDir,maxRotatedFiles=10)
    self.status = PROC_STATUS.STOP
    self.endTime = None

  def connectionMade(self):
    self.status = PROC_STATUS.RUN
    self._writeLog("[processStarted] at:%s\n"%(datetime.now()))
  def _writeLog(self,data):
    self.logFile.write(data) 
  def outReceived(self, data):
    self._writeLog(data)
  def errReceived(self, data):
    self._writeLog("[ERROR DATA]:"+data)
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

  def processExited(self, reason):
    pass
  def processEnded(self, reason):
    self.endTime = datetime.now()
    if reason.value.exitCode is None:
      self._writeLog("[processEnded] code is None,info:%s\n"% (reason)) 
    elif reason.value.exitCode != 0 :
      self._writeLog("[processEnded] code:%d,info:%s\n"% (reason.value.exitCode,reason)) 
    self.status = PROC_STATUS.STOP
    self._writeLog("[processEnded] at:%s\n"%(self.endTime))

  def signal(self,signalName):
    self.transport.signalProcess(signalName.name)
