#-*- coding:utf-8 -*- 

from twisted.internet.protocol import ClientCreator, Protocol
from twisted.internet.error import ConnectionDone
from twisted.internet import reactor
from twisted.protocols.ftp import FTPClient

import os,sys
import zlib
import fnmatch
from datetime import datetime
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from dp.common import dpDir,checkDir

cacheDir = os.path.join(dpDir,'data','filecache','')
checkDir(cacheDir)

class BufferFileTransferProtocol(Protocol):
  def __init__(self,fname):
    self.fname=fname
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
      if os.path.exists(cacheFile):
        if not crcCheck(self.tmpName,cacheFile):
          os.rename(cacheFile,"%s_%s"%(datetime.now().strftime('%Y%m%d-%H%M%S'),cacheFile))
        else:
          os.remove(self.tmpName)
      else:
        os.rename(self.tmpName, cacheFile)

class FilesProtocol(Protocol):
  def __init__(self):
    self.buffer = StringIO()
  def dataReceived(self, data):
    self.buffer.write(data)

def fail(error):
  print 'Ftp failed.  Error was:',error

def echoResult(result):
  print result

def downloadFiles(fileset=[]):
  creator = ClientCreator(reactor, FTPClient,'user','trunksoft')
  creator.connectTCP('localhost',56021).addCallback(connectionMade,fileset).addErrback(fail)

def connectionMade(ftpClient,fileset):
    proto = FilesProtocol()
    path = '.'
    d = ftpClient.nlst(path, proto)
    d.addCallbacks(processFiles, fail, callbackArgs=(ftpClient,proto,path,))

def processFiles(result,ftpClient,proto,path):
  files = proto.buffer.getvalue()
  proto.buffer.close()
  print files
  fname = "slyj_ybsf.pdf"
  #d = ftpClient.retrieveFile("%s/%s"%(path,fname), BufferFileTransferProtocol(fname))
  #d.addCallback(lambda x,y:y.quit().addCallback(echoResult),ftpClient)

def crcCheck(source,target):
  return crc32(source)==crc32(target)

def crc32(file):
  result = 0
  with open(file,'rb') as f:
    for chunk in iter(lambda: f.read(8192), ''): 
      result = zlib.crc32(chunk,result)
  return "%08x"%(result & 0xFFFFFFFF)

