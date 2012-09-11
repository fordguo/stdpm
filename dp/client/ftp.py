#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ClientCreator, Protocol
from twisted.internet.error import ConnectionDone
from twisted.internet import reactor
from twisted.protocols.ftp import FTPClient,FTPFileListProtocol

import os,shutil,fnmatch
import zlib,json
import tarfile,zipfile
from datetime import datetime
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from dp.common import getDatarootDir,checkDir,TIME_FORMAT
from dp.client.process import restartProc,getLPConfig,updateLog,clientUpdateLog

cacheDir = os.path.join(getDatarootDir(),'data','filecache','')
checkDir(cacheDir)

class BufferFileTransferProtocol(Protocol):
  def __init__(self,fname,localInfo,psGroup,psName,changeFlagList):
    self.fname=fname
    self.psGroup = psGroup
    self.psName = psName
    self.localInfo = localInfo
    self.tmpName=os.path.join(cacheDir,fname+'.tmp')
    self.fileInst=open(self.tmpName,'wb+')
    self.changeFlagList = changeFlagList
  def dataReceived(self,data):
    self.fileInst.write(data)
  def _processFiles(self,cacheFile,localDir,localInfo):
    extname = os.path.splitext(self.fname)[-1].lower()
    def extract(func):
      tmpF = None
      try:
        tmpF = func(cacheFile,'r')
        tmpF.extractall(localDir)
      except Exception, e:
        print 'extract %s error:%s,just copy it.'%(cacheFile,str(e))
        shutil.copy(cacheFile,localDir)
      finally:
        if tmpF is not None:
          tmpF.close()
    if localInfo.get('extract',False):
      if extname in ('.gz','.tar','.bz2'):
        extract(tarfile.open)
      elif extname=='.zip':
        extract(zipfile.ZipFile)
      else:
        shutil.copy(cacheFile,localDir)
    else:
      shutil.copy(cacheFile,localDir)
  def connectionLost(self,reason=ConnectionDone):
    self.fileInst.close()
    if reason.type is not ConnectionDone:
      print "download:"+self.fname+" error",reason
      os.remove(self.tmpName)
    else:
      cacheFile = os.path.join(cacheDir,self.fname)
      changed = False
      if os.path.exists(cacheFile):
        if not crcCheck(self.tmpName,cacheFile):
          os.rename(cacheFile,os.path.join(cacheDir,"%s_%s"%(datetime.now().strftime('%Y%m%d-%H%M%S'),self.fname)))
          changed = True
        else:
          os.remove(self.tmpName)
      else:
        changed = True
      if changed:
        self.changeFlagList.append(changed)
        os.rename(self.tmpName, cacheFile)
        localDir = self.localInfo['dir']
        checkDir(localDir)
        if self.localInfo.get('restartRename',False):
          shutil.copy(cacheFile,os.paht.join(localDir,'%s.new'%(cacheFile)))
        else:
          self._processFiles(cacheFile,localDir,localInfo)
        if self.psGroup:
          updateLog(self.psGroup,self.psName,self.fname)
        else:
          clientUpdateLog(self.fname)

def fail(error):
  print 'Ftp failed.  Error was:',error

def echoResult(result):
  print "echoResult",result

def downloadFiles(config,fileset=[],psGroup=None,psName=None,restart={},client=None):
  creator = ClientCreator(reactor, FTPClient,config['ftpUser'],config['ftpPassword'])
  creator.connectTCP(config['server'],int(config['ftpPort'])).addCallback(connectionMade,fileset,\
    psGroup,psName,restart,client).addErrback(fail)

def connectionMade(ftpClient,fileset,psGroup,psName,restart,client):
  lastLen = len(fileset)-1
  deferList = ([],[])
  for n,fileInfo in enumerate(fileset):
    remoteInfo = fileInfo.get('remote')
    if remoteInfo is None: continue
    remoteDir = remoteInfo.get('dir')
    if remoteDir is None: continue
    localInfo = fileInfo.get('local')
    if localInfo is None: continue
    localDir = localInfo.get('dir')
    if localDir is None or not os.path.exists(localDir): 
      print 'localDir:%s is None or not exist.'%localDir
      continue
    remoteFilters = remoteInfo.get('filters',['*']) 
    proto = FTPFileListProtocol()
    d = ftpClient.list(remoteDir, proto)
    d.addCallbacks(processFiles, fail, callbackArgs=(ftpClient,proto,remoteDir,remoteFilters,localInfo,\
      n==lastLen,psGroup,psName,restart,client,deferList))

def processFiles(result,ftpClient,proto,remoteDir,remoteFilters,localInfo,isLast,psGroup,psName,restart,client,deferList):
  for f in proto.files:
    if f['filetype']=='-':
      fName = f['filename']
      for fl in remoteFilters:
        if fnmatch.fnmatch(fName,fl):
          transferProtocol = BufferFileTransferProtocol(fName,localInfo,psGroup,psName,deferList[1])
          deferList[0].append(ftpClient.retrieveFile("%s/%s"%(remoteDir,fName),transferProtocol))
  if isLast and len(deferList[0])>0:
    def beforeQuit(result):
      if len(deferList[1])>0 and deferList[1][0]:
          if restart.get('enable',True) and psGroup is not None:
            for cache in restart.get('clearCaches',[]):
              shutil.rmtree(cache)
            restartProc(psGroup,psName,int(restart.get('sleep',10)),memo='update')
          if client is not None:
            client.sendFileUpdate(psGroup,psName,datetime.now().strftime(TIME_FORMAT))
      ftpClient.quit().addCallback(echoResult)
    deferList[0][-1].addCallback(beforeQuit)

def crcCheck(source,target):
  return crc32(source)==crc32(target)

def crc32(file):
  result = 0
  with open(file,'rb') as f:
    for chunk in iter(lambda: f.read(8192), ''): 
      result = zlib.crc32(chunk,result)
  return "%08x"%(result & 0xFFFFFFFF)
