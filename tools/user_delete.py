#!/usr/bin/python
# coding: UTF-8

# ユーザを削除します。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 2:
    print "Usage: %s UserName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1].decode('utf-8')

if not world.DelUser(user_name):
    print "delete user failed."
    exit(1)

print "user %s deleted." % user_name

