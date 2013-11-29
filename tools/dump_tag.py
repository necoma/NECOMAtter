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
    print "Usage: %s TagName" % sys.argv[0]
    exit(1)

tag_name = sys.argv[1]
limit = None
if len(sys.argv) >= 3:
    limit = int(sys.argv[2])

tweet_list = world.GetTweetFromTag(tag_name, limit)
for tweet in tweet_list:
    print "%s at %s from %s" % (tweet[0].encode('utf-8'), time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tweet[1])), tweet[2].encode('utf-8'))


