#-*- coding:utf-8 -*- 

from twisted.python import usage
from dp.client import main

class Options(usage.Options):
  optParameters = [
    ['server', 'h','localhost'],
    ['port', 'p',56024],
    ['dataDir','d','.'],
    ['ftpPort', 'f',56021],
    ['ftpUser','u','user'],
    ['ftpPassword','P','trunksoft']
  ]

  optFlags = []

def makeService(config):
  import sys
  reload(sys)
  sys.setdefaultencoding("utf-8")
  return main.makeService(config)