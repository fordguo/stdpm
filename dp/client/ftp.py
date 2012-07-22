#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ClientCreator, Protocol
from twisted.internet.error import ConnectionDone
from twisted.internet import reactor
from twisted.protocols.ftp import FTPClient,FTPFileListProtocol

import os,shutil,fnmatch
import zlib
from datetime import datetime
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from dp.common import getDatarootDir,checkDir

cacheDir = os.path.join(getDatarootDir(),'data','filecache','')
checkDir(cacheDir)

class BufferFileTransferProtocol(Protocol):
  def __init__(self,fname,localInfo):
    self.fname=fname
    self.localInfo = localInfo
    self.tmpName=os.path.join(cacheDir,fname+'.tmp')
    self.fileInst=open(self.tmpName,'wb+')
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
        localDir = localInfo['dir']
        checkDir(localDir)
        if localInfo.get('restartRename',False):
          shutil.copy(cacheFile,os.paht.join(localDir,'%s.new'%(cacheFile)))
        else:
          shutil.copy(cacheFile,localDir)

def fail(error):
  print 'Ftp failed.  Error was:',error

def echoResult(result):
  print result

def downloadFiles(config,fileset=[]):
  creator = ClientCreator(reactor, FTPClient,config['ftpUser'],config['ftpPassword'])
  creator.connectTCP(config['server'],config['ftpPort']).addCallback(connectionMade,fileset).addErrback(fail)

def connectionMade(ftpClient,fileset):
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
    d.addCallbacks(processFiles, fail, callbackArgs=(ftpClient,proto,remoteDir,remoteFilters,localInfo,n==lastLen))

def processFiles(result,ftpClient,proto,remoteDir,remoteFilters,localInfo,isLast):
  print proto.files
  d = None
  for f in proto.files:
    if f['filetype']=='-':
      fName = f['filename']
      for fl in remoteFilters:
        if fnmatch.filter(fName,fl):
          d = ftpClient.retrieveFile("%s/%s"%(remoteDir,fName), BufferFileTransferProtocol(fName,localInfo))
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

