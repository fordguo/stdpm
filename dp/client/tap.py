
from twisted.python import usage
from dp.client import main

class Options(usage.Options):
  optParameters = [
    ['server', 'h','localhost'],
    ['port', 'p',56024],
    ['dataDir','d','.'],
    ['confDir','c','conf'],
    ['ftpPort', 'f',56021],
    ['ftpUser','u','user'],
    ['ftpPassword','P','trunksoft']
  ]

  optFlags = []

def makeService(config):
    return main.makeService(config)