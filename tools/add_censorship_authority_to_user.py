#!/usr/bin/python
# coding: UTF-8

# ユーザに公開可能権限を追加します。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter

world = NECOMAtter("http://localhost:7474")

if len(sys.argv) != 2:
    print "Usage: %s UserName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]

result = world.AssignCensorshipAuthorityToUserByName(user_name)
if result[0] != True:
    print "add user failed. ", result[1]
    exit(1)

print "user %s was given censorship authority." % user_name



