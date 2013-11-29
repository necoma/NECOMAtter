#!/usr/bin/python
# coding: UTF-8

# ユーザのAPI keyを表示します。

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) < 2:
    print "Usage: %s TagName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]

api_key_list = world.GetUserAPIKeyListByName(user_name)
for api in api_key_list:
    print api


