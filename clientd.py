#!/usr/bin/env python

import sys,os
import glob
import ConfigParser
from distutils.util import get_platform

pyver = "py"+sys.version[:3]
platform = get_platform()

eggs = ['zope.interface','Twisted','setuptools','PyYAML']
dpHome = os.path.dirname(os.path.realpath(__file__))
sysPath = [dpHome]
config = ConfigParser.ConfigParser()

def autoCheckEggs():
  global eggs
  dpEggPath = os.path.join(dpHome,'eggs','')#sys.path[0]
  dpEggs = [glob.glob("%s%s-*%s*egg"%(dpEggPath,name,pyver)) for name in eggs]
  for eggs in dpEggs:
    bestEgg = None
    for egg in eggs:
      basename = os.path.basename(egg)
      spLen = len(basename.split("-"))
      if spLen==3 or (spLen>=4 and basename.find(platform)>0):
        bestEgg = egg
    if bestEgg :    
      sysPath.append(bestEgg)

autoCheckEggs()
sys.path[0:0] = sysPath
if __name__ == '__main__':
  import twisted.scripts.twistd
  config.read(os.path.join(dpHome,'conf','clientd.cfg'))
  loginfo = ''
  if platform.find('Windows') == -1:
    logdir = os.path.join(dpHome,'data','log')
    if not os.path.exists(logdir):
      os.makedirs(logdir)
    loginfo = ",'--logfile','data/log/clientd.log','--pidfile','data/log/clientd.pid'"

  args = "sys.path[0:0]=%s;import twisted.scripts.twistd;sys.argv=sys.argv[:1]+['-n'%s,'dpclient','-h','%s','-p',%d,'-f',%d]"%(
    sysPath,loginfo,config.get('basic','server'),config.getint('basic','port'),config.getint('basic','ftpPort'))
  sys.argv=sys.argv[:1]+['procmon','-M',60,sys.executable,'-c','import sys;%s;twisted.scripts.twistd.run()'%args]
  twisted.scripts.twistd.run()