#!/usr/bin/python
# coding: UTF-8

# ユーザにツイートさせます。

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter

world = NECOMAtter("http://localhost:7474")

if len(sys.argv) != 3:
    print "Usage: %s UserName tweet_string" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
tweet_string = sys.argv[2]

user_node = world.GetUserNode(user_name)
if user_node is None:
    print "user %s is not created." % user_name
    exit(1)

tweet_node = world.Tweet(user_node, tweet_string)
if tweet_node is None:
    print "tweet failed."
    exit(1)

for node in tweet_node:
    print tweet_node[node]


