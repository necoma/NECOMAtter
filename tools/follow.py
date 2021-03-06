#!/usr/bin/python
# coding: UTF-8

# ユーザをフォローします。

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter

world = NECOMAtter("http://localhost:7474")

if len(sys.argv) != 3:
    print "Usage: %s UserName(follower) UserName(target)" % sys.argv[0]
    exit(1)

follower_user_name = sys.argv[1]
target_user_name = sys.argv[2]

if not world.FollowUserByName(follower_user_name, target_user_name):
    print "failed."
    exit(1)

print "success."
    



