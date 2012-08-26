#-*- coding:utf-8 -*- 

from twisted.python.constants import NamedConstant, Names
import os,platform

_datarootDir = "."

JSON = 'json:'
JSON_LEN = len(JSON)

import dp
dpDir = os.path.dirname(dp.__file__)
selfFileSet = [
  {'local':{'dir':dpDir},'remote':{'dir':'selfupdate','filters':['*.py']}},
  {'local':{'dir':os.path.join(dpDir,'client')},'remote':{'dir':'selfupdate/client','filters':['*.py']}},
  ]

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CR = '\r\n' if platform.platform().find("Windows")==0 else '\n'

PS_BASIC = ['executable','args','path','user','group','usePTY','childFDs']

SEP = '_-_'

def changeDpDir(newDir):
  global _datarootDir
  checkDir(newDir)
  _datarootDir = newDir
def getDatarootDir():
  return _datarootDir

def checkDir(dstDir):
  if not os.path.exists(dstDir):
    os.makedirs(dstDir)

class PROC_STATUS(Names):
    """
    Constants representing various process status.
    """
    STARTING = NamedConstant()
    RUN = NamedConstant()
    STOPPING = NamedConstant()
    STOP = NamedConstant()
class SIGNAL_NAME(Names):
  """Constants representing signal names"""
  KILL = NamedConstant()
  TERM = NamedConstant()
  INT = NamedConstant()

class LPConfig(object):
  """the local process configure information"""
  def __init__(self, confDict):
    super(LPConfig, self).__init__()
    self.confDict = confDict.copy()
    self.executable = self.confDict.pop('executable')
    self.args = self.confDict.pop("args",())
    self.execArgs = [self.executable]+[str(x) for x in self.args]
    self.usePTY = self.confDict.pop('usePTY',False)
    self.path = self.confDict.pop('path','.')
    monValue = self.monitorValue()
    self.monEnable = monValue[0][1]
    self.monLog = None
    self.logFullName = None
    self.monKeyword = None
    if len(monValue)>1:
      self.monLog = monValue[1][1][0][1]
      self.monKeyword = monValue[1][1][1][1]
  def monKeywords(self):
    if not self.monKeyword :return None
    if isinstance(self.monKeyword,basestring):
      return [self.monKeyword]
    else:
      return self.monKeyword
  def verifyLog(self):
    if not self._existFile(self.monLog):
      self.monLog = None
  def _existFile(self,fname):
    if fname is None: return False
    if not os.path.exists(fname):
      fullPath = os.path.join(self.path,fname)
      if os.path.exists(fullPath):
        self.logFullName = fullPath
        return True
      else:
        return False
    else:
      self.logFullName = fname
      return True
  def __getattr__(self, name):
    if self.__dict__.has_key(name):
      return self.__dict__[name]
    else:
      return self.confDict.get(name)
  def baseValue(self):
    result = []
    for k in PS_BASIC:
      v = self.__getattr__(d)
      if v is not None:
        result.append((k,v))
    return result
  def restartValue(self):
    return self.confDict.get('restart',{'enable':True,'periodMinutes':5}).iteritems()
  def getPeriod(self):
    restartInfo =  self.confDict.get('restart')
    if restartInfo is None:return 5
    if restartInfo.get('enable',True):
      return int(restartInfo.get('periodMinutes',5))
    else:
      return None

  def monitorValue(self):
    result = []
    mValue =  self.confDict.get('monitor',{'enable':False})
    result.append(('enable',mValue.get('enable')))
    if mValue.has_key('log'):
      lDict = mValue.get('log')
      if lDict.get('file') is not None :
        result.append(('log',[('file',lDict.get('file')),('keyword',lDict.get('keyword'))]))
    return result
  def fileUpdateInfo(self):
    result = []
    fValue =  self.confDict.get('fileUpdate')
    if fValue:
      fileSet = fValue.get('fileSet')
      if fileSet :
        result.append(('restart',fValue.get('restart',{'enable':True})))
        result.append(('fileSet',fileSet))
    return result

