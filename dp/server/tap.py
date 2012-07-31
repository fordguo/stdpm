#-*- coding:utf-8 -*- 

from twisted.python import usage
from dp.server import main

class Options(usage.Options):
  optParameters = [
    ['mainPort', 'm',56024],
    ['ftpPort', 'f',56021],
    ['httpPort', 'h',56080],
    ['dataDir','d','.']
	]

  optFlags = []

def makeService(config):
  import sys
  reload(sys)
  sys.setdefaultencoding("utf-8")
  return main.makeService(config)