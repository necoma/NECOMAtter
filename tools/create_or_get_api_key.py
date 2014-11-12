#!/usr/bin/python
# coding: UTF-8

# NECOMAtter.py を直接触って
# 指定されたユーザに API-key を与え、その API-key を出力します。
# 既に API-key を持っていたらそれを使います。

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter

world = NECOMAtter("http://localhost:7474")

if len(sys.argv) < 2:
    print "Usage: %s UserName [description]" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
description = None
if len(sys.argv) > 2:
    description = sys.argv[2]

key_list = world.GetUserAPIKeyListByName(user_name)
if key_list is not None and len(key_list) > 0:
    print key_list[0]
    exit(0)

api_key_node = world.CreateUserAPIKeyByName(user_name)
if api_key_node is None or 'key' not in api_key_node:
    print "crete API-key failed."
    exit(1)

print api_key_node['key']
exit(0)

