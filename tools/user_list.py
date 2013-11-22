#!/usr/bin/python
# coding: UTF-8
# ユーザリストを表示します。

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter

world = NECOMATter("http://localhost:7474")
name_list = world.GetUserNameList()
for name in name_list:
    print name
