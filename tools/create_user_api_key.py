#!/usr/bin/python
# coding: UTF-8

# ユーザにAPIキーを追加します。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 2:
    print "Usage: %s UserName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]

node = world.CreateUserAPIKeyByName(user_name)
if node is None:
    print "add API Key failed."
    exit(1)

print "API Key created: ", node



