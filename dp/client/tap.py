
from twisted.python import usage
from dp.client import main

class Options(usage.Options):
  optParameters = [
    ['server', 'h','localhost'],
    ['port', 'p',56024],
    ['ftpPort', 'f',56021],
    ['dataDir','d','.'],
    ['confDir','c','conf']
  ]

  optFlags = []

def makeService(config):
    return main.makeService(config)