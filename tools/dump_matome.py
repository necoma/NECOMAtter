#!/usr/bin/python
# coding: UTF-8

# まとめを表示します。

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter

world = NECOMAtter("http://localhost:7474")

if len(sys.argv) < 2:
    print "Usage: %s matome_node_id" % sys.argv[0]
    exit(1)

matome_node_id = int(sys.argv[1])
print world.GetNECOMAtomeTweetListByIDFormatted(matome_node_id)

