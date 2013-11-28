#!/usr/bin/python
# coding: UTF-8

# tweet ID $B$KE;$o$k(Btweet$B$r<hF@$7$^$9(B

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



