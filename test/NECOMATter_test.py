#!/usr/bin/python
# coding: UTF-8
# NECOMATter のテスト

import sys
import os
import unittest
import subprocess
import shutil
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter
from py2neo import neo4j, cypher

Neo4JCmd = "./neo4j/bin/neo4j"
Neo4JDataDir = "./neo4j/data"
Neo4JLogDir = "./neo4j/data/log"

gdb = neo4j.GraphDatabaseService("http://localhost:17474/db/data/")

# Neo4J が起動しているかどうかを確認します
def IsNeo4JStarted():
    process = subprocess.Popen([Neo4JCmd, "status"])
    ret = process.wait()
    return ret == 0

def StopNeo4J():
    process = subprocess.Popen([Neo4JCmd, "stop"])
    ret = process.wait()
    return ret == 0

def StartNeo4J():
    # Neo4J が起動しているならそれで良いとします
    if IsNeo4JStarted():
        return True
    # 新しく起動する場合、Neo4J のデータディレクトリを全部吹き飛ばします
    if os.path.exists(Neo4JDataDir):
        shutil.rmtree(Neo4JDataDir)
    # logディレクトリを掘っておきます
    os.makedirs(Neo4JLogDir)
    process = subprocess.Popen([Neo4JCmd, "start"])
    ret = process.wait()
    return ret == 0

def CheckTweet(tweet, text, user_name=None):
    if 'text' not in tweet or 'user_name' not in tweet:
        print "tweet is not formatted? 'text' or 'user_name' field not found"
        return False
    if tweet['text'] != text:
        print "text field not equal: %s <-> %s" % (text, tweet['text'])
        return False
    if user_name is not None:
        if tweet['user_name'] != user_name:
            print "user_name field not equal: %s <-> %s" % (user_name, tweet['user_name'])
            return False
    return True

class NECOMATterTestCase(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")

    def tearDown(self):
        pass

    def test_EscapeForXSS(self):
        q_a = {'"': '&quot;',
                '""': '&quot;&quot;',
                "<A>": "&lt;A&gt;",
                "<<A>": "&lt;&lt;A&gt;",
                "abc 日本語": "abc 日本語"
                }
        for q, a in q_a.items():
            r = self.world.EscapeForXSS(q)
            self.assertEqual(r, a)

    def test_UserList(self):
        self.assertEqual([], self.world.GetUserNameList())
        assert self.world.AddUser("iimura", "test")
        self.assertEqual(["iimura"], self.world.GetUserNameList())
        assert self.world.AddUser(u"いいむら", "test")
        self.assertEqual(["iimura", u"いいむら"], self.world.GetUserNameList())

    def test_AddUser(self):
        # ユーザを作った後、name="iimura" のユーザが自分をfollow していることを確認する
        test_cases = [
                {"user": "iimura", "password": "test", "AddUserResult": True, "search_string": 'iimura', "result": [[u'iimura', u'iimura']]},
                {"user": "<iimura>", "password": "test", "AddUserResult": False, "search_string": "<iimura>", "result": []},
                {"user": 'ii"mura', "password": "test", "AddUserResult": False, "search_string": 'ii\\"mura', "result": []},
                {"user": "iimura", "password": "test", "AddUserResult": False, "search_string": 'iimura', "result": [[u'iimura', u'iimura']]},
                {"user": "iimura", "password": "password change", "AddUserResult": False, "search_string": 'iimura', "result": [[u'iimura', u'iimura']]},
                {"user": "iimura other user name", "password": "test", "AddUserResult": True, "search_string": 'iimura', "result": [[u'iimura', u'iimura']]},
                ]
        for qa in test_cases:
            if qa['AddUserResult']:
                self.assertTrue(self.world.AddUser(qa['user'], qa['password']))
            else:
                self.assertFalse(self.world.AddUser(qa['user'], qa['password']))
            query = ""
            query += 'START user=node:user(name="%s") ' % qa['search_string']
            query += 'MATCH node -[:FOLLOW]-> user '
            query += 'RETURN user.name, node.name '
            result_list, metadata = cypher.execute(gdb, query)
            self.assertEqual(qa['result'], result_list)

    # 何もしていないユーザが削除できることを確認
    def test_DelUser(self):
        # ユーザが最初は誰も居ないことを確認
        self.assertEqual([], self.world.GetUserNameList())
        # ユーザの作成はしておく
        self.assertTrue(self.world.AddUser("iimura", "password"))
        self.assertEqual([u'iimura'], self.world.GetUserNameList())
        # 関係ない名前のユーザは削除できない
        self.assertFalse(self.world.DelUser("not defined user"))
        self.assertEqual([u'iimura'], self.world.GetUserNameList())
        # 正しい名前のユーザは削除できる
        self.assertTrue(self.world.DelUser("iimura"))
        self.assertEqual([], self.world.GetUserNameList())
        # 二回目の削除は失敗する
        self.assertFalse(self.world.DelUser("iimura"))
        self.assertEqual([], self.world.GetUserNameList())

    # フォロー関係にあるユーザを削除した場合、フォローがなくなることを確認
    def test_DelUser_Followed(self):
        # ユーザが最初は誰も居ないことを確認
        self.assertEqual([], self.world.GetUserNameList())
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password"))
        self.assertTrue(self.world.AddUser("limura", "password"))
        # 二人でフォローしあう
        self.assertTrue(self.world.FollowUserByName("iimura", "limura"))
        self.assertTrue(self.world.FollowUserByName("limura", "iimura"))
        # フォローされている事を確認します
        iimura_node = self.world.GetUserNode("iimura")
        limura_node = self.world.GetUserNode("limura")
        self.assertTrue(self.world.IsFollowed(iimura_node, limura_node))
        self.assertTrue(self.world.IsFollowed(limura_node, iimura_node))
        # ユーザを削除します
        self.assertTrue(self.world.DelUser("iimura"))
        # follow が自分だけしか残っていないことを確認します
        query = ""
        query += 'START user=node(*) '
        query += 'MATCH user -[:FOLLOW]-> node '
        query += 'RETURN node.name '
        query += 'ORDER BY node.name '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual([[u'limura']], result_list)

    def test_FollowUserByName(self):
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password"))
        self.assertTrue(self.world.AddUser("limura", "password"))
        # iimura -> limura のフォロー関係を作る
        self.assertTrue(self.world.FollowUserByName("iimura", "limura"))
        # フォロー関係が上で作ったフォロー関係だけであることを確認
        query = ""
        query += 'START user=node(*) '
        query += 'MATCH user -[:FOLLOW]-> node '
        query += 'WHERE user.name <> node.name '
        query += 'RETURN node.name '
        query += 'ORDER BY node.name '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual([[u'limura']], result_list)
        # limura -> iimura のフォロー関係を作る
        self.assertTrue(self.world.FollowUserByName("limura", "iimura"))
        # 新しくフォロー関係が増えている事を確認
        query = ""
        query += 'START user=node(*) '
        query += 'MATCH user -[:FOLLOW]-> node '
        query += 'WHERE user.name <> node.name '
        query += 'RETURN node.name '
        query += 'ORDER BY node.name '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual([[u'iimura'], [u'limura']], result_list)
        
    def test_IsFollowed(self):
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password"))
        self.assertTrue(self.world.AddUser("limura", "password"))
        iimura_node = self.world.GetUserNode("iimura")
        limura_node = self.world.GetUserNode("limura")
        # フォローされていないとされることを確認
        self.assertFalse(self.world.IsFollowed(iimura_node, limura_node))
        self.assertFalse(self.world.IsFollowed(limura_node, iimura_node))
        # iimura -> limura のフォロー関係を作る
        self.assertTrue(self.world.FollowUserByName("iimura", "limura"))
        # フォローされているとされることを確認
        self.assertTrue(self.world.IsFollowed(iimura_node, limura_node))
        self.assertFalse(self.world.IsFollowed(limura_node, iimura_node))
        # limura -> iimura のフォロー関係を作る
        self.assertTrue(self.world.FollowUserByName("limura", "iimura"))
        # フォローされているとされることを確認
        self.assertTrue(self.world.IsFollowed(iimura_node, limura_node))
        self.assertTrue(self.world.IsFollowed(limura_node, iimura_node))
        # 二重にフォローはできないことを確認
        self.assertFalse(self.world.FollowUserByName("iimura", "limura"))
        self.assertFalse(self.world.FollowUserByName("limura", "iimura"))
        # 存在しないユーザのフォローはできないことを確認
        self.assertFalse(self.world.FollowUserByName("iimura", "undefined user"))

    def test_UnFollowUserByName(self):
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password"))
        self.assertTrue(self.world.AddUser("limura", "password"))
        iimura_node = self.world.GetUserNode("iimura")
        limura_node = self.world.GetUserNode("limura")
        # フォローされていないとされることを確認
        self.assertFalse(self.world.IsFollowed(iimura_node, limura_node))
        self.assertFalse(self.world.IsFollowed(limura_node, iimura_node))
        # フォローしていないユーザのフォローを外すことは失敗するのを確認
        self.assertFalse(self.world.UnFollowUserByName("limura", "iimura"))
        # iimura -> limura のフォロー関係を作る
        self.assertTrue(self.world.FollowUserByName("iimura", "limura"))
        self.assertTrue(self.world.FollowUserByName("limura", "iimura"))
        # フォローされているとされることを確認
        self.assertTrue(self.world.IsFollowed(iimura_node, limura_node))
        self.assertTrue(self.world.IsFollowed(limura_node, iimura_node))
        # フォローを外す
        self.assertTrue(self.world.UnFollowUserByName("limura", "iimura"))
        # フォローされてなくなったとされることを確認
        self.assertTrue(self.world.IsFollowed(iimura_node, limura_node))
        self.assertFalse(self.world.IsFollowed(limura_node, iimura_node))
        # 既にフォローを外したユーザのフォローを外すことは失敗するのを確認
        self.assertFalse(self.world.UnFollowUserByName("limura", "iimura"))
        # 存在しないユーザのフォローを外すことは失敗するのを確認
        self.assertFalse(self.world.UnFollowUserByName("limura", "undefined user"))

    def test_Tweet(self):
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password"))
        iimura_node = self.world.GetUserNode("iimura")
        # タイムラインにはまだ何も無い事を確認
        self.assertEqual([], self.world.GetUserTimeline(iimura_node))
        # tweet する
        tweetText = u"test tweet 日本語も入れる"
        tweet_node = self.world.Tweet(iimura_node, tweetText)
        self.assertIsNotNone(tweet_node)
        # tweet が書き込んだ文字列を持っている事を確認する
        self.assertEqual(tweetText, tweet_node['text'])
        # tweet がユーザへのリレーションシップを持っていることを確認する
        query = ""
        query += 'START tweet=node(%d) ' % tweet_node._id
        query += 'MATCH tweet -[:TWEET]-> user '
        query += 'RETURN user.name '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual([[u'iimura']], result_list)

if __name__ == '__main__':
    assert StartNeo4J()
    unittest.main()
    assert StopNeo4J()
