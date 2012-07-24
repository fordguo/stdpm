#!/usr/bin/env python

import sys,os
import glob
import ConfigParser
from distutils.util import get_platform

pyver = "py"+sys.version[:3]
platform = get_platform()

eggs = ['zope.interface','Twisted','setuptools','PyYAML','Mako','MarkupSafe']
dpHome = os.path.dirname(os.path.realpath(__file__))
sysPath = [dpHome]
config = ConfigParser.ConfigParser()

def autoCheckEggs():
  global eggs
  dpEggPath = os.path.join(dpHome,'eggs','')#sys.path[0]
  dpEggs = [glob.glob("%s%s*%s*egg"%(dpEggPath,name,pyver)) for name in eggs]
  for eggs in dpEggs:
    bestEgg = None
    for egg in eggs:
      basename = os.path.basename(egg)
      spLen = len(basename.split("-"))
      if spLen==3 or (spLen>4 and basename.find(platform)>0):
        bestEgg = egg
    if bestEgg :    
      sysPath.append(bestEgg)

autoCheckEggs()
sys.path[0:0] = sysPath
if __name__ == '__main__':
  import twisted.scripts.twistd
  config.read(os.path.join(dpHome,'conf','serverd.cfg'))

  sys.argv = sys.argv[:1]+['-l','serverd.log','--pidfile','serverd.pid','dpserver','-m',config.get('basic','mainPort'),\
    '-f',config.getint('basic','ftpPort'),'-h',config.getint('basic','httpPort')]
  twisted.scripts.twistd.run()