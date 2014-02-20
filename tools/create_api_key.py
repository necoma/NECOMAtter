#!/usr/bin/python
# coding: UTF-8

# ユーザにAPIキーを発行します。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 2:
    print "Usage: %s UserName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1].decode('utf-8')

api_key_node = world.CreateUserAPIKeyByName(user_name)

if api_key_node is None:
    print "api key create failed."
    exit(1)

print "user %s APIKey created: %s" % (user_name, api_key_node['key'])

