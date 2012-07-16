
from twisted.python import usage
from dp.server import main

class Options(usage.Options):
  optParameters = [
    ['mainPort', 'm',56024],
    ['ftpPort', 'f',56021],
    ['httpPort', 'h',56080],
    ]

  optFlags = []

def makeService(config):
    return main.makeService(config)