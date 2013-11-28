#!/usr/bin/python
# coding: UTF-8

# tweet ID に纏わるtweetを取得します

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")

if len(sys.argv) != 2:
    print "Usage: %s TweetID" % sys.argv[0]
    exit(1)

tweet_id = int(sys.argv[1])

print world.GetOneTweetData(tweet_id)



