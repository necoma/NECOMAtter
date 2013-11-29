#!/usr/bin/python
# coding: UTF-8

# ユーザのツイートを表示します。

import sys
import os
import time
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) < 2:
    print "Usage: %s UserName" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
limit = None
if len(sys.argv) >= 3:
    limit = int(sys.argv[2])

user_node = world.GetUserNode(user_name)
if user_node is None:
    print "user %s is not created." % user_name
    exit(1)

tweet_list = world.GetUserTweet(user_node, limit)
for tweet in tweet_list:
    print "%s at %s" % (tweet[0].encode('utf-8'), time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tweet[1])))


