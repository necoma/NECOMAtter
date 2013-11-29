#!/usr/bin/python
# coding: UTF-8

# ユーザを追加します。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 3:
    print "Usage: %s UserName API_Key" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
key = sys.argv[2]

if not world.DeleteUserAPIKeyByName(user_name, key):
    print "delete API Key failed."
    exit(1)

print "key deleted."



