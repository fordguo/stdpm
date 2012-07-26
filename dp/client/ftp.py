#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ClientCreator, Protocol
from twisted.internet.error import ConnectionDone
from twisted.internet import reactor
from twisted.protocols.ftp import FTPClient,FTPFileListProtocol

import os,shutil,fnmatch
import zlib,json
from datetime import datetime
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from dp.common import getDatarootDir,checkDir,TIME_FORMAT
from dp.client.process import restartProc,getLPConfig,updateLog

cacheDir = os.path.join(getDatarootDir(),'data','filecache','')
checkDir(cacheDir)

class BufferFileTransferProtocol(Protocol):
  def __init__(self,fname,localInfo,psGroup,psName,isLast,restart,client):
    self.fname=fname
    self.psGroup = psGroup
    self.psName = psName
    self.restart = restart
    self.isLast = isLast
    self.localInfo = localInfo
    self.tmpName=os.path.join(cacheDir,fname+'.tmp')
    self.fileInst=open(self.tmpName,'wb+')
    self.client = client
  def dataReceived(self,data):
    self.fileInst.write(data)
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
          os.rename(cacheFile,"%s_%s"%(datetime.now().strftime('%Y%m%d-%H%M%S'),cacheFile))
          changed = True
        else:
          os.remove(self.tmpName)
      else:
        changed = True
      if changed:
        os.rename(self.tmpName, cacheFile)
        localDir = self.localInfo['dir']
        checkDir(localDir)
        if self.localInfo.get('restartRename',False):
          shutil.copy(cacheFile,os.paht.join(localDir,'%s.new'%(cacheFile)))
        else:
          shutil.copy(cacheFile,localDir)
        if self.psGroup:
          updateLog(self.psGroup,self.psName,self.fname)
        if self.isLast:
          if self.restart.get('enable',True) and self.psGroup is not None:
            for cache in self.restart.get('clearCaches',[]):
              shutil.rmtree(cache)
            restartProc(self.psGroup,self.psName,int(self.restart.get('sleep',1)),True)
          if self.client is not None:
            self.client.sendJson(json.dumps({'action':'updateFinish','group':self.psGroup,'name':self.psName,\
            'datetime':datetime.now().strftime(TIME_FORMAT)}))


def fail(error):
  print 'Ftp failed.  Error was:',error

def echoResult(result):
  print "echoResult",result

def downloadFiles(config,fileset=[],psGroup=None,psName=None,restart=False,client=None):
  creator = ClientCreator(reactor, FTPClient,config['ftpUser'],config['ftpPassword'])
  creator.connectTCP(config['server'],int(config['ftpPort'])).addCallback(connectionMade,fileset,\
    psGroup,psName,restart,client).addErrback(fail)

def connectionMade(ftpClient,fileset,psGroup,psName,restart,client):
  lastLen = len(fileset)-1
  for n,fileInfo in enumerate(fileset):
    remoteInfo = fileInfo.get('remote')
    if remoteInfo is None: continue
    remoteDir = remoteInfo.get('dir')
    if remoteDir is None: continue
    localInfo = fileInfo.get('local')
    if localInfo is None: continue
    localDir = localInfo.get('dir')
    if localDir is None or not os.path.exists(localDir): continue
    remoteFilters = remoteInfo.get('filters',['*']) 
    proto = FTPFileListProtocol()
    d = ftpClient.list(remoteDir, proto)
    d.addCallbacks(processFiles, fail, callbackArgs=(ftpClient,proto,remoteDir,remoteFilters,localInfo,\
      n==lastLen,psGroup,psName,restart,client))

def processFiles(result,ftpClient,proto,remoteDir,remoteFilters,localInfo,isLast,psGroup,psName,restart,client):
  d = None
  for f in proto.files:
    if f['filetype']=='-':
      fName = f['filename']
      for fl in remoteFilters:
        if fnmatch.fnmatch(fName,fl):
          d = ftpClient.retrieveFile("%s/%s"%(remoteDir,fName), BufferFileTransferProtocol(fName,localInfo,\
            psGroup,psName,isLast,restart,client))
  if isLast and d:
    d.addCallback(lambda x,y:y.quit().addCallback(echoResult),ftpClient)

def crcCheck(source,target):
  return crc32(source)==crc32(target)

def crc32(file):
  result = 0
  with open(file,'rb') as f:
    for chunk in iter(lambda: f.read(8192), ''): 
      result = zlib.crc32(chunk,result)
  return "%08x"%(result & 0xFFFFFFFF)

