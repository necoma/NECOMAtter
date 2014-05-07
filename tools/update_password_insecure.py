#!/usr/bin/python
# coding: UTF-8

# ユーザのパスワードを変更します。

import sys
import os
import getpass

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter
import time

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 2:
    print "Usage: %s UserName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]

#print "input old password" 
#old_password = getpass.getpass()
#if not world.CheckUserPasswordIsValid(user_name, old_password):
#    print "password invalid."
#    exit(1)

print "input new password."
new_password_1 = getpass.getpass()
print "re-input new password."
new_password_2 = getpass.getpass()
if new_password_1 != new_password_2:
    print "not same input."
    exit(1)

if not world.UpdateUserPasswordForce(user_name, new_password_1):
    print "password update failed."
    exit(1)

user_node = world.GetUserNode(user_name)
print "user %s password updated: " % user_name, user_node



