#!/usr/bin/env python

from distutils.core import setup

setup(name='sdpm',
      version='1.0',
      description='Smart Distributed Process Management',
      author='Ford Guo',
      author_email='agile.guo@gmail.com',
      url='https://github.com/fordguo/sdpm',
      package_dir = {'sdmp': 'dp'},
      packages=find_packages('dp'),
      install_requires=['setuptools','Twisted'],
      scripts=['tools/sdp-client', 'tools/sdp-server'],
     )
