#!/usr/bin/python
# coding: UTF-8

# $B%f!<%6$rDI2C$7$^$9!#(B

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 3:
    print "Usage: %s UserName Password" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
password = sys.argv[2]

if not world.AddUser(user_name, password):
    print "add user failed."
    exit(1)

user_node = world.GetUserNode(user_name)
print "user created: ", user_node



