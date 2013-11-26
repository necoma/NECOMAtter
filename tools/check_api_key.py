#!/usr/bin/python
# coding: UTF-8

# $B%f!<%6$,(BAPI$B%-!<$r;}$C$F$$$k$+$r3NG'$7$^$9!#(B

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 3:
    print "Usage: %s UserName API_Key" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
key_name = sys.argv[2]

if not world.CheckUserAPIKeyByName(user_name, key_name):
    print "%s not have this API Key" % user_name
    exit(1)

print "%s have this API Key" % user_name



