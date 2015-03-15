#!/usr/bin/python
# coding: UTF-8

# ユーザを追加します。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter

world = NECOMAtter("http://localhost:7474")

if len(sys.argv) != 3:
    print "Usage: %s UserName Password" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
password = sys.argv[2]

result = world.AddUser(user_name, password)
if result[0] != True:
    print "add user failed. ", result[1]
    exit(1)

result = world.AssignCreateUserAuthorityToUserByName(user_name)
if result[0] != True:
    print "add user success. but \"create user authority\" append failed."
    exit(1)

user_node = world.GetUserNode(user_name)
print "user created: ", user_node



