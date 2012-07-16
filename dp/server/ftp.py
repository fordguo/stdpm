#-*- coding:utf-8 -*- 

from twisted.protocols.ftp import FTPFactory, FTPRealm
from twisted.cred.portal import Portal
from twisted.cred.checkers import FilePasswordDB

from dp.common import getDpDir,checkDir
import os

def initFtpFactory():
  ftpRoot = os.path.join(getDpDir(),'data','ftp','')
  ftpData = os.path.join(ftpRoot,'data')
  checkDir(ftpData)
  passFile = os.path.join(ftpRoot,"userpass.dat")
  if not os.path.exists(passFile) :
    with open(passFile,"w+") as f:
      f.write("user:trunksoft\n")
  with open(passFile) as f:
    for line in f:
      splits = line.split(":")
      if len(splits)>1:
        checkDir(os.path.join(ftpData,splits[0]))
  FTPFactory.allowAnonymous = False
  p = Portal(FTPRealm(ftpData,ftpData),[FilePasswordDB(passFile)])
  f = FTPFactory(p)
  return f
