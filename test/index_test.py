#!/usr/bin/python
# coding: UTF-8
# NECOMATter のテスト

import sys
import os
import unittest
import tempfile
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import index

class NECOMATterIndexTestCase(unittest.TestCase):
    def setUp(self):
        self.app = index.app.test_client()
        pass
    def tearDown(self):
        pass

    def test_add_user(self):
        pass

if __name__ == '__main__':
    unittest.main()
