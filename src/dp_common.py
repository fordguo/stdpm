#-*- coding:utf-8 -*- 

from twisted.python.constants import NamedConstant, Names
import os

dpDir = "."

JSON = 'json:'
JSON_LEN = len(JSON)

def changeDpDir(newDir):
  global dpDir
  dpDir = newDir

def checkDir(dstDir):
  if not os.path.exists(dstDir):
    os.makedirs(dstDir)

class PROC_STATUS(Names):
    """
    Constants representing various process status.
    """
    RUN = NamedConstant()
    STOPPING = NamedConstant()
    STOP = NamedConstant()
class SIGNAL_NAME(Names):
  """Constants representing signal names"""
  KILL = NamedConstant()
  TERM = NamedConstant()
  INT = NamedConstant()
