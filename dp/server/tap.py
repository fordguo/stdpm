#-*- coding:utf-8 -*- 

from twisted.python import usage
from dp.server import main

class Options(usage.Options):
  optParameters = [
    ['mainPort', 'm',3024],
    ['ftpPort', 'f',3021],
    ['httpPort', 'h',3080],
    ['dataDir','d','.']
	]

  optFlags = []

def makeService(config):
  import sys
  reload(sys)
  sys.setdefaultencoding("utf-8")
  return main.makeService(config)