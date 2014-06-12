#!/usr/bin/python
# coding: UTF-8
# NECOMATter のテスト

import sys
import os
import unittest
import subprocess
import shutil
import time
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
        assert self.world.AddUser("iimura", "test")[0]
        self.assertEqual(["iimura"], self.world.GetUserNameList())
        assert self.world.AddUser(u"いいむら", "test")[0]
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
                self.assertTrue(self.world.AddUser(qa['user'], qa['password'])[0])
            else:
                self.assertFalse(self.world.AddUser(qa['user'], qa['password'])[0])
            query = ""
            query += 'START user=node:user(name="%s") ' % qa['search_string']
            query += 'MATCH node -[:FOLLOW]-> user '
            query += 'WHERE node.name <> "<ForAllUser>" '
            query += 'RETURN user.name, node.name '
            result_list, metadata = cypher.execute(gdb, query)
            self.assertEqual(qa['result'], result_list)

    # 何もしていないユーザが削除できることを確認
    def test_DeleteUser(self):
        # ユーザが最初は誰も居ないことを確認
        self.assertEqual([], self.world.GetUserNameList())
        # ユーザの作成はしておく
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        self.assertEqual([u'iimura'], self.world.GetUserNameList())
        # 関係ない名前のユーザは削除できない
        self.assertFalse(self.world.DeleteUser("not defined user"))
        self.assertEqual([u'iimura'], self.world.GetUserNameList())
        # 正しい名前のユーザは削除できる
        self.assertTrue(self.world.DeleteUser("iimura"))
        self.assertEqual([], self.world.GetUserNameList())
        # 二回目の削除は失敗する
        self.assertFalse(self.world.DeleteUser("iimura"))
        self.assertEqual([], self.world.GetUserNameList())

    # フォロー関係にあるユーザを削除した場合、フォローがなくなることを確認
    def test_DeleteUser_Followed(self):
        # ユーザが最初は誰も居ないことを確認
        self.assertEqual([], self.world.GetUserNameList())
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        self.assertTrue(self.world.AddUser("takuji", "password")[0])
        # 二人でフォローしあう
        self.assertTrue(self.world.FollowUserByName("iimura", "takuji"))
        self.assertTrue(self.world.FollowUserByName("takuji", "iimura"))
        # フォローされている事を確認します
        iimura_node = self.world.GetUserNode("iimura")
        limura_node = self.world.GetUserNode("takuji")
        self.assertTrue(self.world.IsFollowed(iimura_node, limura_node))
        self.assertTrue(self.world.IsFollowed(limura_node, iimura_node))
        # ユーザを削除します
        self.assertTrue(self.world.DeleteUser("iimura"))
        # follow が自分だけしか残っていないことを確認します
        query = ""
        query += 'START user=node(*) '
        query += 'MATCH user -[:FOLLOW]-> node '
        query += 'WHERE user.name <> "<ForAllUser>" '
        query += 'RETURN user.name '
        query += 'ORDER BY user.name '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual([[u'takuji']], result_list)

    # ユーザを削除した場合、API_KEYも消えることを確認します
    def test_DeleteUser_APIKey(self):
        user_name = "iimura"
        password = "password"
        # ユーザを作成する
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        # API_KEY を作る
        api_key_node = self.world.CreateUserAPIKeyByName(user_name)
        self.assertIsNotNone(api_key_node)
        api_key = api_key_node['key']
        # API_KEY が存在することを確認する
        result_list = []
        try:
            query = ""
            query += 'START api_key_node=node:api_key(key="%s") ' %api_key
            query += 'RETURN api_key_node.key'
            result_list, metadata = cypher.execute(gdb, query)
        except neo4j.ClientError:
            result_list = []
        self.assertEqual([[api_key]], result_list)
        # ユーザを削除する
        self.assertTrue(self.world.DeleteUser(user_name))
        # API_KEY が存在しなくなったことを確認する
        result_list = []
        try:
            query = ""
            query += 'START api_key_node=node:api_key(key="%s") ' %api_key
            query += 'RETURN api_key_node.key'
            result_list, metadata = cypher.execute(gdb, query)
        except neo4j.ClientError:
            result_list = []
        self.assertEqual([], result_list)

    # ユーザを削除した場合、tweetは消えないことを確認します
    def test_DeleteUser_Tweet(self):
        pass

    def test_FollowUserByName(self):
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        self.assertTrue(self.world.AddUser("limura", "password")[0])
        # iimura -> limura のフォロー関係を作る
        self.assertTrue(self.world.FollowUserByName("iimura", "limura"))
        # フォロー関係が上で作ったフォロー関係だけであることを確認
        query = ""
        query += 'START user=node(*) '
        query += 'MATCH user -[:FOLLOW]-> node '
        query += 'WHERE user.name <> node.name '
        query += 'AND user.name <> "<ForAllUser>" '
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
        query += 'AND user.name <> "<ForAllUser>" '
        query += 'RETURN node.name '
        query += 'ORDER BY node.name '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual([[u'iimura'], [u'limura']], result_list)
        
    def test_IsFollowed(self):
        # 二人ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        self.assertTrue(self.world.AddUser("limura", "password")[0])
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
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        self.assertTrue(self.world.AddUser("limura", "password")[0])
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
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        iimura_node = self.world.GetUserNode("iimura")
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

    def test_Tweet_DeleteUser(self):
        # 一度tweetしたユーザがユーザを消された場合どうなるかのテスト
        user_name = "iimura"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, "password")[0])
        iimura_node = self.world.GetUserNode(user_name)
        # tweet する
        tweetText = u"test tweet 日本語も入れる"
        tweet_node = self.world.Tweet(iimura_node, tweetText)
        self.assertIsNotNone(tweet_node)
        tweet_id = tweet_node._id
        # ツイートを取得します
        tweet = self.world.GetTweetNodeFromIDFormatted(tweet_node._id, query_user_name=user_name)[0]
        self.assertEqual(tweet_id, tweet['id'])
        self.assertEqual(user_name, tweet['user_name'])
        # ユーザを消します
        self.assertTrue(self.world.DeleteUser(user_name))
        # ツイートを取得します。
        # ユーザが消されるとPERMIT のリンクが辿れなくなるのでツイートは見えなくなります
        self.assertEqual([], self.world.GetTweetNodeFromIDFormatted(tweet_node._id, query_user_name=user_name))

    def test_Tweet_ReplyTo(self):
        # reply-to をつけた tweet ができることを確認する
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        iimura_node = self.world.GetUserNode("iimura")
        # tweet する
        tweetText = u"test tweet"
        tweet_node = self.world.Tweet(iimura_node, tweetText)
        self.assertIsNotNone(tweet_node)
        # tweet が他のtweetへの REPLY リレーションシップを持っていないことを確認する
        query = ""
        query += 'START tweet=node(%d) ' % tweet_node._id
        query += 'MATCH tweet -[:REPLY]-> target_tweet '
        query += 'RETURN target_tweet '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual(0, len(result_list))
        # tweet が他のtweetからの REPLY リレーションシップを持っていないことを確認する
        query = ""
        query += 'START tweet=node(%d) ' % tweet_node._id
        query += 'MATCH from_tweet -[:REPLY]-> tweet '
        query += 'RETURN from_tweet '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual(0, len(result_list))
        # 新しく tweet する。これは前のtweetへの返事とする
        # tweet する
        tweetText = u"test reply tweet to: %d" % tweet_node._id
        reply_tweet_node = self.world.Tweet(iimura_node, tweetText, tweet_node._id)
        self.assertIsNotNone(reply_tweet_node)
        # 前の tweet が他のtweetへの REPLY リレーションシップを持っていないことを確認する(前と変わらない)
        query = ""
        query += 'START tweet=node(%d) ' % tweet_node._id
        query += 'MATCH tweet -[:REPLY]-> target_tweet '
        query += 'RETURN target_tweet '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual(0, len(result_list))
        # 前の tweet が他のtweetからの REPLY リレーションシップを持っていることを確認する(前と違う)
        query = ""
        query += 'START tweet=node(%d) ' % tweet_node._id
        query += 'MATCH from_tweet -[:REPLY]-> tweet '
        query += 'RETURN from_tweet '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual(1, len(result_list))
        self.assertEqual(reply_tweet_node._id, result_list[0][0]._id)
        # 新しい tweet(reply_tweet) がreply-to先のtweet への REPLY リレーションシップを持っていることを確認する
        query = ""
        query += 'START tweet=node(%d) ' % reply_tweet_node._id
        query += 'MATCH tweet -[:REPLY]-> target_tweet '
        query += 'RETURN target_tweet '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node._id, result_list[0][0]._id)
        # reply_tweet が他のtweetからの REPLY リレーションシップを持っていないことを確認する
        query = ""
        query += 'START tweet=node(%d) ' % reply_tweet_node._id
        query += 'MATCH from_tweet -[:REPLY]-> tweet '
        query += 'RETURN from_tweet '
        result_list, metadata = cypher.execute(gdb, query)
        self.assertEqual(0, len(result_list))

    def test_Timeline(self):
        # タイムラインが正しく扱われるかのテスト
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        iimura_node = self.world.GetUserNode("iimura")
        self.assertTrue(self.world.AddUser("tarou", "password")[0])
        tarou_node = self.world.GetUserNode("tarou")
        self.assertTrue(self.world.AddUser("abe", "password")[0])
        abe_node = self.world.GetUserNode("abe")
        # タイムラインにはまだ何も無い事を確認
        self.assertEqual([], self.world.GetUserTimeline(iimura_node, iimura_node))
        self.assertEqual([], self.world.GetUserTimeline(tarou_node, tarou_node))
        self.assertEqual([], self.world.GetUserTimeline(abe_node, abe_node))
        # iimura は tarou と abe をフォローします
        self.assertTrue(self.world.FollowUserByName("iimura", "tarou"))
        self.assertTrue(self.world.FollowUserByName("iimura", "abe"))
        # iimura が tweet します
        tweet_node = self.world.Tweet(iimura_node, "hello world")
        self.assertIsNotNone(tweet_node)
        # iimura のタイムラインにだけ入っていることを確認
        self.assertEqual(1, len(self.world.GetUserTimeline(iimura_node, iimura_node)))
        self.assertEqual(0, len(self.world.GetUserTimeline(tarou_node, tarou_node)))
        self.assertEqual(0, len(self.world.GetUserTimeline(abe_node, abe_node)))
        # abe が tweet します
        tweet_node = self.world.Tweet(abe_node, "hello world")
        self.assertIsNotNone(tweet_node)
        # iimura と abe のタイムラインに入っていることを確認
        self.assertEqual(2, len(self.world.GetUserTimeline(iimura_node, iimura_node)))
        self.assertEqual(0, len(self.world.GetUserTimeline(tarou_node, tarou_node)))
        self.assertEqual(1, len(self.world.GetUserTimeline(abe_node, abe_node)))
        # tarou が tweet します
        tweet_node = self.world.Tweet(tarou_node, "hello world")
        self.assertIsNotNone(tweet_node)
        # iimura と tarou のタイムラインに入っていることを確認
        self.assertEqual(3, len(self.world.GetUserTimeline(iimura_node, iimura_node)))
        self.assertEqual(1, len(self.world.GetUserTimeline(tarou_node, tarou_node)))
        self.assertEqual(1, len(self.world.GetUserTimeline(abe_node, abe_node)))

    def test_GetUserTimeline_Limit(self):
        # limit が効くことを確認します
        # ユーザを作成
        user_name = "iimura"
        password = "password"
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # タイムラインにはまだ何も無い事を確認
        self.assertEqual([], self.world.GetUserTimeline(iimura_node, iimura_node))
        # iimura が 10回 tweet します
        for i in range(1, 11):
            tweet_node = self.world.Tweet(iimura_node, "tweet no: %d" % i)
            self.assertIsNotNone(tweet_node)
        # iimura のタイムラインが10個になっていることを確認
        self.assertEqual(10, len(self.world.GetUserTimeline(iimura_node, iimura_node)))
        # limit=5 にして取得した場合に、5個になっていることを確認
        tweet_list = self.world.GetUserTimeline(iimura_node, iimura_node, limit=5)
        self.assertEqual(5, len(tweet_list))
        # 中身が「最新の5個」になっていることを確認します
        for i in range(0, 5):
            tweet_node = tweet_list[i]
            target_tweet_text = "tweet no: %d" % (10-i)
            self.assertEqual(target_tweet_text, tweet_node[0])

    def test_GetUserTimeline_SinceTime(self):
        # since_time が効くことを確認します
        # ユーザを作成
        user_name = "iimura"
        password = "password"
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # タイムラインにはまだ何も無い事を確認
        self.assertEqual([], self.world.GetUserTimeline(iimura_node, iimura_node))
        no7_tweet = None
        # iimura が 10回 tweet します
        for i in range(1, 11):
            tweet_node = self.world.Tweet(iimura_node, "tweet no: %d" % i)
            self.assertIsNotNone(tweet_node)
            # 7番目のtweetは覚えておきます
            if i == 7:
                no7_tweet = tweet_node
                # since_time を使うので、少しだけ待ちます
                time.sleep(0.1)
        # iimura のタイムラインが10個になっていることを確認
        self.assertEqual(10, len(self.world.GetUserTimeline(iimura_node, iimura_node)))
        # since_time に no7_tweet の時間を指定して取得した場合に、7個になっていることを確認
        tweet_list = self.world.GetUserTimeline(iimura_node, iimura_node, since_time=no7_tweet['time'])
        self.assertEqual(6, len(tweet_list))
        # 中身が「1, 2, 3, 4, 5, 6, 7番目のtweet、の7個」になっていることを確認します
        for i in range(0, 6):
            tweet_node = tweet_list[i]
            target_tweet_text = "tweet no: %d" % (6-i)
            self.assertEqual(target_tweet_text, tweet_node[0])

    def test_GetTagList(self):
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        iimura_node = self.world.GetUserNode("iimura")
        # GetTagList ではまだ何も無い事を確認
        self.assertEqual([], self.world.GetTagList())
        # 特にtagの無いtweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "normal tweet")
        self.assertIsNotNone(tweet_node)
        # GetTagList ではまだ何も無い事を確認
        self.assertEqual([], self.world.GetTagList())
        # tagのあるtweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "tweet with tag #tag")
        self.assertIsNotNone(tweet_node)
        # GetTagList に "tag" が含まれていることを確認
        self.assertEqual([u"#tag"], self.world.GetTagList())
        # 同じ tagのあるtweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "another tweet with tag #tag")
        self.assertIsNotNone(tweet_node)
        # GetTagList のリストが増えていないことを確認
        self.assertEqual([u"#tag"], self.world.GetTagList())
        # 違う tagのあるtweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "tweet with another tag #tag2")
        # GetTagList のリストが増えていることを確認
        self.assertEqual(sorted([u"#tag", u"#tag2"]), sorted(self.world.GetTagList()))

    def test_Tweet_Tag_Create(self):
        # タグつきで tweet した場合にタグが生成されることを確認します
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        iimura_node = self.world.GetUserNode("iimura")
        # tagリストにはまだ何も無い事を確認
        self.assertEqual([], self.world.GetTagList())
        # tagのあるtweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "tweet with tag #tag\n")
        self.assertIsNotNone(tweet_node)
        # tagリストに新しく "#tag" が現れることを確認("#tag\n" では無いことを確認します)
        self.assertEqual(sorted([u"#tag"]), self.world.GetTagList())

    def test_GetTagTweetFormatted(self):
        # タグに関連するtweetを取り出せることを確認します
        # ユーザを作成
        user_name = "iimura"
        password = "password"
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        target_tag_string = "#tag"
        # #tag にはまだ何も無い事を確認
        self.assertEqual([], self.world.GetTagTweetFormatted(target_tag_string, user_name))
        # tagのあるtweetをおこないます
        tweet_string = "is tag %s apple?\n" % target_tag_string
        tweet_node = self.world.Tweet(iimura_node, tweet_string)
        self.assertIsNotNone(tweet_node)
        # tagリストに新しく target_tag_string が現れることを確認
        formatted_tag_tweet_list = self.world.GetTagTweetFormatted(target_tag_string, user_name)
        self.assertEqual(1, len(formatted_tag_tweet_list))
        tag_tweet = formatted_tag_tweet_list[0]
        self.assertEqual(tweet_string, tag_tweet['text'])
        self.assertEqual(tweet_node._id, tag_tweet['id'])
        self.assertEqual("iimura", tag_tweet['user_name'])
        # 同じ tag を使った別の tweet を投げる
        tweet_string = "no! tag %s\nis not apple." % target_tag_string
        tweet_node = self.world.Tweet(iimura_node, tweet_string)
        self.assertIsNotNone(tweet_node)
        # tagリストに新しく target_tag_string が現れることを確認
        formatted_tag_tweet_list = self.world.GetTagTweetFormatted(target_tag_string, user_name)
        self.assertEqual(2, len(formatted_tag_tweet_list))
        tag_tweet = formatted_tag_tweet_list[0]
        self.assertEqual(tweet_string, tag_tweet['text'])
        self.assertEqual(tweet_node._id, tag_tweet['id'])

    def test_GetUserAPIKeyListByName(self):
        # ユーザのAPI keyが取得できることを確認します
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        # API key はまだ何も無いことを確認します
        self.assertEqual([], self.world.GetUserAPIKeyListByName("iimura"))
        # API key を新しく生成します
        key_node = self.world.CreateUserAPIKeyByName("iimura")
        self.assertIsNotNone(key_node)
        # API key が取得できるようになったことを確認します
        key_list = self.world.GetUserAPIKeyListByName("iimura")
        self.assertEqual(1, len(key_list))
        key_name = key_list[0]
        self.assertEqual(key_node['key'], key_name)

    def test_GetTweetNodeFromID(self):
        # tweet の ID からtweet nodeを取得できることを確認します
        # 最初は何もノードが無いはずです
        self.assertIsNone(self.world.GetTweetNodeFromID(0))
        # ユーザを作成
        self.assertTrue(self.world.AddUser("iimura", "password")[0])
        iimura_node = self.world.GetUserNode("iimura")
        # iimura_node のidをtweetとして取得しようとしても失敗することを確認します
        self.assertIsNone(self.world.GetTweetNodeFromID(iimura_node._id))
        # tweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "normal tweet")
        self.assertIsNotNone(tweet_node)
        # IDでtweetを取得してみます
        get_tweet_node = self.world.GetTweetNodeFromID(tweet_node._id)
        # 取得できているはずです。
        self.assertIsNotNone(get_tweet_node)
        # id 等も同じ値になっているはずです
        self.assertEqual(tweet_node._id, get_tweet_node._id)
        self.assertEqual(tweet_node['text'], get_tweet_node['text'])

    def test_GetTweetFromID(self):
        # tweet の ID から tweet を取得できることを確認します
        # 最初は何もノードが無いはずです
        self.assertEqual([], self.world.GetTweetFromID(0, None))
        # ユーザを作成
        user_name = "iimura"
        password = "password"
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # ユーザがいても、ID 0 では取得できないはずです
        self.assertEqual([], self.world.GetTweetFromID(0, iimura_node))
        # iimura_node のidをtweetとして取得しようとしても失敗することを確認します
        self.assertEqual([], self.world.GetTweetFromID(iimura_node._id, iimura_node))
        # tweetをおこないます
        tweet_node = self.world.Tweet(iimura_node, "normal tweet")
        self.assertIsNotNone(tweet_node)
        # IDでtweetを取得してみます
        get_tweet = self.world.GetTweetFromID(tweet_node._id, iimura_node)
        # 一つだけ取得できているはずです。
        self.assertEqual(1, len(get_tweet))
        # 取得された値は text, time, user_name, node の順の配列になっているはずです
        (tweet_text, time, user_name, icon_url, node_id
         , my_star_r, my_retweet_r
         , retweet_time, retweeet_unix_time
         , retweet_type, list_name, list_owner_name) = get_tweet[0]
        # id 等も同じ値になっているはずです
        self.assertEqual(tweet_node['text'], tweet_text)
        self.assertEqual(iimura_node['name'], user_name)
        self.assertEqual(tweet_node._id, node_id)
        self.assertIsNone(my_star_r)
        self.assertIsNone(my_retweet_r)
        self.assertEqual("TWEET", retweet_type)
        self.assertEqual("<ForAllUser>", list_name)
        self.assertIsNone(list_owner_name)

    def test_CheckUserPasswordIsValid(self):
        # パスワードのチェックが正しく行えることを確認します
        user_name = "iimura"
        password = "password"
        # 誰もユーザが居ない時には失敗することを確認します
        self.assertFalse(self.world.CheckUserPasswordIsValid(user_name, password))
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        # 正しいパスワードの場合は成功することを確認します
        self.assertTrue(self.world.CheckUserPasswordIsValid(user_name, password))
        # 間違えたパスワードの場合は失敗することを確認します
        self.assertFalse(self.world.CheckUserPasswordIsValid(user_name, password + "append text"))

    def test_UpdateUserPassword(self):
        # パスワードの変更ができることを確認します
        user_name = "iimura"
        password = "password"
        wrong_password = "wrong password"
        new_password = "new password"
        # ユーザが存在しない場合はパスワードが変更できないことを確認します。
        self.assertFalse(self.world.UpdateUserPassword(user_name, password, new_password))
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        # パスワードが正しく設定されていることを CheckUserPasswordIsValid() で確認します
        self.assertTrue(self.world.CheckUserPasswordIsValid(user_name, password))
        # 間違えたパスワードではパスワードが変更できないことを確認します。
        self.assertFalse(self.world.UpdateUserPassword(user_name, wrong_password, new_password))
        # パスワードが変更されていないことを確認します
        self.assertTrue(self.world.CheckUserPasswordIsValid(user_name, password))
        # パスワードを変更します
        self.assertTrue(self.world.UpdateUserPassword(user_name, password, new_password))
        # パスワードが変更されていることを確認します
        self.assertTrue(self.world.CheckUserPasswordIsValid(user_name, new_password))
        # 古いパスワードでは認証が通らなくなっていることを確認します。
        self.assertFalse(self.world.CheckUserPasswordIsValid(user_name, password))

    def test_CheckUserAPIKeyByName(self):
        # ユーザのAPIキーのチェックが正しく動作することを確認します
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        # APIキーを作ります
        api_key_node = self.world.CreateUserAPIKeyByName(user_name)
        self.assertIsNotNone(api_key_node)
        api_key = api_key_node['key']
        # 正しい APIキー であればチェックを通る事を確認します
        self.assertTrue(self.world.CheckUserAPIKeyByName(user_name, api_key))
        # 間違えた APIキー であればチェックが通らないことを確認します
        self.assertFalse(self.world.CheckUserAPIKeyByName(user_name, api_key + "wrong"))

    def test_DeleteUserAPIKeyByName(self):
        # ユーザのAPIキーを削除できることを確認します
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        # APIキーを作ります
        api_key_node = self.world.CreateUserAPIKeyByName(user_name)
        self.assertIsNotNone(api_key_node)
        api_key = api_key_node['key']
        # APIキーが存在することを確認します
        self.assertEqual([api_key], self.world.GetUserAPIKeyListByName(user_name))
        # APIキー のチェックが通る事を確認します
        self.assertTrue(self.world.CheckUserAPIKeyByName(user_name, api_key))
        # APIキーを削除します
        self.assertTrue(self.world.DeleteUserAPIKeyByName(user_name, api_key))
        # APIキーが存在しなくなったことを確認します
        self.assertEqual([], self.world.GetUserAPIKeyListByName(user_name))
        # APIキーのチェックも通らなくなったことを確認しておきます
        self.assertFalse(self.world.CheckUserAPIKeyByName(user_name, api_key))

    def test_GetParentTweetAboutTweetIDFormatted_same_user(self):
        # 返事の関係にあるtweetの親を辿ることができるのを確認します(同じユーザ版)
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # tweetします
        tweet_node_1 = self.world.Tweet(iimura_node, "normal tweet")
        self.assertIsNotNone(tweet_node_1)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_2 = self.world.Tweet(iimura_node, "normal tweet", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_2)
        # tweet_node_2 に対して返事の形式でtweetします。
        tweet_node_3 = self.world.Tweet(iimura_node, "normal tweet", tweet_node_2._id)
        self.assertIsNotNone(tweet_node_3)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_4 = self.world.Tweet(iimura_node, "normal tweet", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_4)
        # ここまでで、
        # 1 <--+-- 2 <-- 3
        #      | 
        #      +-- 4 
        # という形のtreeができているはずです。 
        #
        # tweet_node_2 の親を辿ります
        # 1 だけが取得できるはずです
        result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_2._id, user_name)
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node_1._id, result_list[0]['id'])
        # tweet_node_3 の親を辿ります
        # 1 と2が取得できるはずです(順番は時間sortされるので、1,2の順のはずです)
        result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_3._id, user_name)
        self.assertEqual(2, len(result_list))
        self.assertEqual(tweet_node_1._id, result_list[0]['id'])
        self.assertEqual(tweet_node_2._id, result_list[1]['id'])
        # tweet_node_4 の親を辿ります
        # 1 だけが取得できるはずです
        result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_4._id, user_name)
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node_1._id, result_list[0]['id'])

    def test_GetParentTweetAboutTweetIDFormatted_other_user(self):
        # 返事の関係にあるtweetの親を辿ることができるのを確認します(違うユーザ版)
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        user_node = []
        for n in range(1, 5):
            name = "%s:%d" % (user_name, n)
            self.assertTrue(self.world.AddUser(name, password)[0])
            user_node.append(self.world.GetUserNode(name))
        # tweetします
        tweet_node_1 = self.world.Tweet(user_node[0], "normal tweet")
        self.assertIsNotNone(tweet_node_1)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_2 = self.world.Tweet(user_node[1], "normal tweet", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_2)
        # tweet_node_2 に対して返事の形式でtweetします。
        tweet_node_3 = self.world.Tweet(user_node[2], "normal tweet", tweet_node_2._id)
        self.assertIsNotNone(tweet_node_3)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_4 = self.world.Tweet(user_node[3], "normal tweet", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_4)
        # ここまでで、
        # 1 <--+-- 2 <-- 3
        #      | 
        #      +-- 4 
        # という形のtreeができているはずです。 
        #
        # tweet_node_2 の親を辿ります
        # 1 だけが取得できるはずです
        result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_2._id, user_node[1]['name'])
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node_1._id, result_list[0]['id'])
        # tweet_node_3 の親を辿ります
        # 1 と2が取得できるはずです(順番は時間sortされるので、1,2の順のはずです)
        result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_3._id, user_node[2]['name'])
        self.assertEqual(2, len(result_list))
        self.assertEqual(tweet_node_1._id, result_list[0]['id'])
        self.assertEqual(tweet_node_2._id, result_list[1]['id'])
        # tweet_node_4 の親を辿ります
        # 1 だけが取得できるはずです
        result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_4._id, user_node[3]['name'])
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node_1._id, result_list[0]['id'])

    def test_GetParentTweetAboutTweetIDFormatted_limit(self):
        # 返事の関係にあるtweetの親を辿ることができるのを確認します(limitの確認)
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # 1 <- 2 <- 3 <- 4 <- ... という形でtweetの連鎖を作ります。
        prev_tweet_node_id = None
        tweet_node_list = []
        for n in range(0, 10):
            tweet_node = self.world.Tweet(iimura_node, "normal tweet %d" % n, prev_tweet_node_id)
            self.assertIsNotNone(tweet_node)
            tweet_node_list.append(tweet_node)
            prev_tweet_node_id = tweet_node._id
       
        # n: 連鎖の開始点, limit: limitの指定数, answer: 答えとなるtweet_nodeのインデックス値
        # という条件で、テストを行います。
        for n, limit, answer in [
                (0, 10, []),
                (1, 10, [0]),
                (5, 10, [0, 1, 2, 3, 4]),
                (9, 10, [0, 1, 2, 3, 4, 5, 6, 7, 8]),
                (9, 5, [4, 5, 6, 7, 8]),
                (7, 5, [2, 3, 4, 5, 6])
                ]:
            result_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_node_list[n]._id, user_name, limit=limit)
            self.assertEqual(len(answer), len(result_list), "answer required: %s(count: %d) -> got result: %s(count: %d)" % (str(answer), len(answer), str(result_list), len(result_list)))
            for i in range(0, len(answer)):
                self.assertEqual(tweet_node_list[answer[i]]._id, result_list[i]['id'], "no %d check failed. n: %d, limit: %d, answer: %s %s" % (i, n, limit, str(answer), str(result_list)))

    def test_GetChildTweetAboutTweetIDFormatted_same_user(self):
        # 返事の関係にあるtweetの子を辿ることができるのを確認します(同じユーザ版)
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # tweetします
        tweet_node_1 = self.world.Tweet(iimura_node, "normal tweet 0")
        self.assertIsNotNone(tweet_node_1)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_2 = self.world.Tweet(iimura_node, "normal tweet 1", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_2)
        # tweet_node_2 に対して返事の形式でtweetします。
        tweet_node_3 = self.world.Tweet(iimura_node, "normal tweet 2", tweet_node_2._id)
        self.assertIsNotNone(tweet_node_3)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_4 = self.world.Tweet(iimura_node, "normal tweet 3", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_4)
        # ここまでで、
        # 1 <--+-- 2 <-- 3
        #      | 
        #      +-- 4 
        # という形のtreeができているはずです。 
        #
        # tweet_node_2 の子を辿ります
        # 3 だけが取得できるはずです
        result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_2._id, user_name)
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node_3._id, result_list[0]['id'])
        # tweet_node_3 の子を辿ります
        # 空リストが取得できるはずです
        result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_3._id, user_name)
        self.assertEqual(0, len(result_list))
        # tweet_node_1 の子を辿ります
        # 2, 3, 4 が取得できるはずです(順番は時間sortされるので、2,3,4 の順のはずです)
        result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_1._id, user_name)
        self.assertEqual(3, len(result_list))
        self.assertEqual(tweet_node_2._id, result_list[0]['id'])
        self.assertEqual(tweet_node_3._id, result_list[1]['id'])
        self.assertEqual(tweet_node_4._id, result_list[2]['id'])

    def test_GetChildTweetAboutTweetIDFormatted_other_user(self):
        # 返事の関係にあるtweetの子を辿ることができるのを確認します(違うユーザ版)
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        user_node = []
        for n in range(1, 5):
            name = "%s:%d" % (user_name, n)
            self.assertTrue(self.world.AddUser(name, password)[0])
            user_node.append(self.world.GetUserNode(name))
        # tweetします
        tweet_node_1 = self.world.Tweet(user_node[0], "normal tweet")
        self.assertIsNotNone(tweet_node_1)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_2 = self.world.Tweet(user_node[1], "normal tweet", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_2)
        # tweet_node_2 に対して返事の形式でtweetします。
        tweet_node_3 = self.world.Tweet(user_node[2], "normal tweet", tweet_node_2._id)
        self.assertIsNotNone(tweet_node_3)
        # tweet_node_1 に対して返事の形式でtweetします。
        tweet_node_4 = self.world.Tweet(user_node[3], "normal tweet", tweet_node_1._id)
        self.assertIsNotNone(tweet_node_4)
        # ここまでで、
        # 1 <--+-- 2 <-- 3
        #      | 
        #      +-- 4 
        # という形のtreeができているはずです。 
        #
        # tweet_node_2 の子を辿ります
        # 3 だけが取得できるはずです
        result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_2._id, user_node[0]['name'])
        self.assertEqual(1, len(result_list))
        self.assertEqual(tweet_node_3._id, result_list[0]['id'])
        # tweet_node_3 の子を辿ります
        # 空リストが取得できるはずです
        result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_3._id, user_node[0]['name'])
        self.assertEqual(0, len(result_list))
        # tweet_node_1 の子を辿ります
        # 2, 3, 4 が取得できるはずです(順番は時間sortされるので、2,3,4 の順のはずです)
        result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_1._id, user_node[0]['name'])
        self.assertEqual(3, len(result_list))
        self.assertEqual(tweet_node_2._id, result_list[0]['id'])
        self.assertEqual(tweet_node_3._id, result_list[1]['id'])
        self.assertEqual(tweet_node_4._id, result_list[2]['id'])

    def test_GetChildTweetAboutTweetIDFormatted_limit(self):
        # 返事の関係にあるtweetの子を辿ることができるのを確認します(limitの確認)
        user_name = "iimura"
        password = "password"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # 1 <- 2 <- 3 <- 4 <- ... という形でtweetの連鎖を作ります。
        prev_tweet_node_id = None
        tweet_node_list = []
        for n in range(0, 10):
            tweet_node = self.world.Tweet(iimura_node, "normal tweet %d" % n, prev_tweet_node_id)
            self.assertIsNotNone(tweet_node)
            tweet_node_list.append(tweet_node)
            prev_tweet_node_id = tweet_node._id
       
        # n: 連鎖の開始点, limit: limitの指定数, answer: 答えとなるtweet_nodeのインデックス値
        # という条件で、テストを行います。
        for n, limit, answer in [
                (9, 10, []),
                (8, 10, [9]),
                (5, 10, [6, 7, 8, 9]),
                (0, 10, [1, 2, 3, 4, 5, 6, 7, 8, 9]),
                (0, 5, [5, 6, 7, 8, 9]),
                (2, 5, [5, 6, 7, 8, 9]) # 新しい順に取り出されるので、これでよいです
                ]:
            result_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_node_list[n]._id, user_name, limit=limit)
            self.assertEqual(len(answer), len(result_list), "answer required: %s(count: %d) -> got result: %s(count: %d)" % (str(answer), len(answer), str(result_list), len(result_list)))
            for i in range(0, len(answer)):
                self.assertEqual(tweet_node_list[answer[i]]._id, result_list[i]['id'], "no %d check failed. n: %d, limit: %d, answer: %s %s" % (i, n, limit, str(answer), str(result_list)))

    def test_GetTweetNodeFromIDFormatted(self):
        # tweet を取得できることを確認します
        user_name = "iimura"
        password = "password"
        tweet_text = "tweet text 1"
        # ユーザを作成
        self.assertTrue(self.world.AddUser(user_name, password)[0])
        iimura_node = self.world.GetUserNode(user_name)
        # tweetします
        tweet_node_1 = self.world.Tweet(iimura_node, tweet_text)
        self.assertIsNotNone(tweet_node_1)
        # 取得します
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_node_1._id, user_name)
        self.assertIsNotNone(tweet_list)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_node_1._id, tweet_list[0]['id'])
        self.assertEqual(user_name, tweet_list[0]['user_name'])

# list関連のテストケースはここにまとめます
class NECOMATter_list_TestCase(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")
        # ユーザ A, B, C を作っておきます。
        self.user_node_list = []
        for user_name in ['A', 'B', u"しー"]:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
            user_node = self.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node_list.append(user_node)

    def tearDown(self):
        pass

    def test_AddNodeToListByName(self):
        # 今回のテスト対象のlist名
        list_name = "testりすと"
        # まずリストに何も無い事を確認します。
        for user_node in self.user_node_list:
            result = self.world.GetListUserListByNode(user_node, list_name, user_node)
            self.assertEqual([], result)
        # A がリストに B, C を追加します。
        A_name = self.user_node_list[0]["name"]
        B_name = self.user_node_list[1]["name"]
        C_name = self.user_node_list[2]["name"]
        self.assertTrue(self.world.AddNodeToListByName(A_name, list_name, B_name))
        self.assertTrue(self.world.AddNodeToListByName(A_name, list_name, C_name))
        # リストに追加されていることを確認します
        list_user_node_list = self.world.GetListUserListByName(A_name, list_name, A_name)
        self.assertEqual(2, len(list_user_node_list))
        self.assertEqual([B_name, C_name], [list_user_node_list[0], list_user_node_list[1]])

    def test_DeleteAllListByNode(self):
        # 追加されるリスト名
        list_name_list = ["list A", "list B", "りすと しー"]
        # リストを全て削除されるユーザ名
        owner_user_name = "alpha"
        # ユーザを作成します。
        for user_name in [owner_user_name]:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
        owner_user_node = self.world.GetUserNode(owner_user_name)
        # リストを作成します
        for list_name in list_name_list:
            for target_user_node in self.user_node_list:
                self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_node['name']))
        # 一応リストが作成されていることは確認しておきます
        for list_name in list_name_list:
            self.assertNotEqual([], self.world.GetListUserListByName(owner_user_name, list_name, owner_user_name))
        # リストを全て削除します。
        self.assertTrue(self.world.DeleteAllListByNode(owner_user_node))
        # リストが全て消えていることを確認します
        for list_name in list_name_list:
            self.assertEqual([], self.world.GetListUserListByName(owner_user_name, list_name, owner_user_name))

    def CheckListName(self, answer_list_name_list, target_list):
        self.assertEqual(len(answer_list_name_list), len(target_list))
        for n in range(0, len(answer_list_name_list)):
            self.assertEqual(answer_list_name_list[n], target_list[n]['name'])

    def test_GetUserOwnedListListFormatted(self):
        # 追加されるリスト名
        list_name_list = [u"list A", u"list B", u"りすと しー"]
        # リストを追加するノード
        owner_node = self.user_node_list[0]
        owner_node_name = owner_node['name']
        # リストを追加されるノードの名前
        target_node_name = self.user_node_list[1]['name']
        # 最初は何もリストが無い事を確認します
        self.assertEqual([], self.world.GetUserOwnedListListFormatted(owner_node_name))
        # リストを生成します。
        for list_name in list_name_list:
            self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, target_node_name))
        # 取得されるリストの辞書を生成しておきます
        result_list_list = []
        for list_name in list_name_list:
            result_list_list.append({
                "name": list_name,
                "owner_node_name": owner_node_name,
                })
        # リストが生成されて名前のリストが取得できることを確認します
        result_list = self.world.GetUserOwnedListListFormatted(owner_node_name)
        self.CheckListName(list_name_list, result_list)

    def test_GetListUserListByName(self):
        # リスト名
        list_name = "list"
        # 追加を行うユーザ名
        owner_node_name = self.user_node_list[0]['name']
        # 追加されるユーザ名
        list_user_name_list = [self.user_node_list[1]['name'], self.user_node_list[2]['name']]
        # リストにメンバを追加します
        for user_name in list_user_name_list:
            self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, user_name))
        # ユーザ名が取得できることを確認します
        self.assertEqual(list_user_name_list, self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))

    def test_UnfollowUserFromListByName(self):
        # リスト名
        list_name = "list"
        # 追加を行うユーザ名
        owner_node_name = self.user_node_list[0]['name']
        # 追加されるユーザ名
        list_user_name_list = [self.user_node_list[1]['name'], self.user_node_list[2]['name']]
        # リストにメンバを追加します
        for user_name in list_user_name_list:
            self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, user_name))
        # ユーザ名が取得できることを確認します
        self.assertEqual(list_user_name_list, self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))
        # リストから一人目を削除します
        self.assertTrue(self.world.UnfollowUserFromListByName(owner_node_name, list_name, list_user_name_list[0]))
        # リストから削除されていることを確認します
        self.assertEqual(list_user_name_list[1:], self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))

    def test_UnfollowUserFromListByName_other_user(self):
        # 追加されていないユーザをリストから削除しようとした場合のテスト
        # リスト名
        list_name = "list"
        # 追加を行うユーザ名
        owner_node_name = self.user_node_list[0]['name']
        # 追加されるユーザ名
        add_user_name = self.user_node_list[1]['name']
        # 追加はされないが、存在するユーザ名
        other_user_name = self.user_node_list[2]['name']
        # リストにメンバを追加します
        self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, add_user_name))
        # ユーザ名が取得できることを確認します
        self.assertEqual([add_user_name], self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))
        # リストから未登録のユーザを削除しようとしてみます
        self.assertFalse(self.world.UnfollowUserFromListByName(owner_node_name, list_name, other_user_name))
        # リストが破壊されていないことを確認します
        self.assertEqual([add_user_name], self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))

    def test_UnfollowUserFromListByName_undefined_user(self):
        # 存在しないユーザをリストから削除しようとした場合のテスト
        # リスト名
        list_name = "list"
        # 追加を行うユーザ名
        owner_node_name = self.user_node_list[0]['name']
        # 追加されるユーザ名
        add_user_name = self.user_node_list[1]['name']
        # 存在しないユーザ名
        undefined_user_name = "undefined user"
        # リストにメンバを追加します
        self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, add_user_name))
        # ユーザ名が取得できることを確認します
        self.assertEqual([add_user_name], self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))
        # リストから存在しない名前ののユーザを削除しようとしてみます
        self.assertFalse(self.world.UnfollowUserFromListByName(owner_node_name, list_name, undefined_user_name))
        # リストが破壊されていないことを確認します
        self.assertEqual([add_user_name], self.world.GetListUserListByName(owner_node_name, list_name, owner_node_name))

    def test_DeleteListByName(self):
        # リスト名
        list_name_list = [u"list A", u"list B"]
        # 追加を行うユーザ名
        owner_node_name = self.user_node_list[0]['name']
        # 追加されるユーザ名
        add_user_name = self.user_node_list[1]['name']
        # リストにメンバを追加します
        for list_name in list_name_list:
            self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, add_user_name))
        # リスト名が取得できることを確認します
        self.CheckListName(list_name_list, self.world.GetUserOwnedListListFormatted(owner_node_name))
        # 2つ目のリストを削除します
        self.assertTrue(self.world.DeleteListByName(owner_node_name, list_name_list[1], owner_node_name))
        # リスト名が減っていることを確認します
        self.CheckListName(list_name_list[:1], self.world.GetUserOwnedListListFormatted(owner_node_name))

    def test_DeleteListByName_undefined_name(self):
        # 未定義の名前のリストを消そうとした場合
        # リスト名
        list_name_list = [u"list A", u"list B"]
        # 消そうとされる未定義のリスト名
        target_undefined_list_name = "undefined list name"
        # 追加を行うユーザ名
        owner_node_name = self.user_node_list[0]['name']
        # 追加されるユーザ名
        add_user_name = self.user_node_list[1]['name']
        # リストにメンバを追加します
        for list_name in list_name_list:
            self.assertTrue(self.world.AddNodeToListByName(owner_node_name, list_name, add_user_name))
        # リスト名が取得できることを確認します
        self.CheckListName(list_name_list, self.world.GetUserOwnedListListFormatted(owner_node_name))
        # 存在しない名前のリストを削除します(存在しなかったとしてもTrueが帰るはずです)
        self.assertTrue(self.world.DeleteListByName(owner_node_name, target_undefined_list_name, owner_node_name))
        # リスト名が変わっていないことを確認します
        self.CheckListName(list_name_list, self.world.GetUserOwnedListListFormatted(owner_node_name))

    def test_DeleteListByName_same_list_name(self):
        # 別ユーザが同じ名前のlistを作っていた場合に
        # 片方がリストを消してももう片方には影響しないことを確認します
        # リスト名
        list_name_list = [u"list A", u"list B", u"りすとしー"]
        # 消そうとされるリスト名
        target_list_name = list_name_list[0]
        # 消された後に残るリスト名のリスト
        delete_result_list_name_list = list_name_list[1:]
        # リストを消すノード
        delete_owner_node = self.user_node_list[0]
        # リストを消さないノードのリスト
        no_delete_user_node_list = self.user_node_list[1:]
        # 全てのメンバで全てのメンバについて同じ名前のリストを作ります
        for owner_user_node in self.user_node_list:
            for target_user_node in self.user_node_list:
                if target_user_node == owner_user_node:
                    continue
                for list_name in list_name_list:
                    self.assertTrue(self.world.AddNodeToListByNode(owner_user_node, list_name, target_user_node))
        # 一応、全員同じリストを持っていることを確認します
        for user_node in self.user_node_list:
            self.CheckListName(list_name_list, self.world.GetUserOwnedListListFormatted(user_node['name']))
        # 一つのノードからターゲットリストを削除します
        self.assertTrue(self.world.DeleteListByNode(delete_owner_node, target_list_name, delete_owner_node))
        # 消したノードからはリストが削除されていることを確認します
        self.CheckListName(delete_result_list_name_list, self.world.GetUserOwnedListListFormatted(delete_owner_node['name']))
        # 消していないノードからはリストが削除されていないことを確認します
        for user_node in no_delete_user_node_list:
            self.CheckListName(list_name_list, self.world.GetUserOwnedListListFormatted(user_node['name']))

    def test_DeleteListByName_undefined_list_name(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストを登録するユーザ名
        owner_user_name = self.user_node_list[0]['name']
        # リストに登録されるユーザ名
        target_user_name = self.user_node_list[1]['name']
        # 消そうとする未定義のリスト名
        undefined_list_name = "undefined list"
        # リストが無い事を確認します
        self.CheckListName([], self.world.GetUserOwnedListListFormatted(owner_user_name))
        # 何もリストが無い状態で未定義のリストを消そうとしてみます(存在しなくてもエラーにはなりません)
        self.assertTrue(self.world.DeleteListByName(owner_user_name, undefined_list_name, owner_user_name))
        # リストを作成します
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # もう一度、未定義のリストを消そうとしてみます
        self.assertTrue(self.world.DeleteListByName(owner_user_name, undefined_list_name, owner_user_name))
        # 既存のリストが消されていないことを確認します
        self.CheckListName([list_name], self.world.GetUserOwnedListListFormatted(owner_user_name))

    def test_GetListTimelineFormatted(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # tweetする文字列
        tweet_text = u"tweet"
        # 何もリストを作っていない時にリストのタイムラインを取得してみます。
        # (何も取得できないだけでエラーはしないはずです)
        self.assertEqual([], self.world.GetListTimelineFormatted(owner_user_name, list_name, owner_user_name))
        # リストを作成します
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # リストのタイムラインにはまだ何も無い事を確認します。
        self.assertEqual([], self.world.GetListTimelineFormatted(owner_user_name, list_name, owner_user_name))
        # リストに入っていないメンバ(owner_user_node)がtweetします
        owner_tweet_node = self.world.Tweet(owner_user_node, tweet_text)
        self.assertIsNotNone(owner_tweet_node)
        # リストのタイムラインにはまだ何も無い事を確認します。
        self.assertEqual([], self.world.GetListTimelineFormatted(owner_user_name, list_name, owner_user_name))
        # リストに入ってるメンバ(target_user_node)がtweetします
        target_tweet_node = self.world.Tweet(target_user_node, tweet_text)
        self.assertIsNotNone(target_tweet_node)
        # リストのタイムラインにtweetが追加されていることを確認します。
        formatted_tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, owner_user_name)
        self.assertEqual(1, len(formatted_tweet_list))
        self.assertEqual(tweet_text, formatted_tweet_list[0]['text'])
        self.assertEqual(target_tweet_node._id, formatted_tweet_list[0]['id'])

    def test_AddOtherUserListByNode(self):
        # 作成されるリスト名
        list_name = u"list"
        # 存在しないリスト名
        undefined_list_name = u"undefined list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストをフォローするユーザのノード
        follower_user_node = self.user_node_list[2]
        # リストをフォローするユーザのユーザ名
        follower_user_name = follower_user_node['name']
        # 存在しないユーザ名
        undefined_user_name = "undefined user name"
        # オーナがリストを作成します
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # フォロアはまだ自分のlistのリストには何も無いはずです
        self.assertEqual([], self.world.GetUserListListFormatted(follower_user_name))
        # 作成されたリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(follower_user_name, owner_user_name, list_name))
        # フォロアのリストに新しく追加されるはずです
        list_dic_list = self.world.GetUserListListFormatted(follower_user_name)
        self.assertEqual(1, len(list_dic_list))
        self.assertEqual(list_name, list_dic_list[0]['name'])
        self.assertEqual(owner_user_name, list_dic_list[0]['owner_name'])
        # 存在しないリストを指定するとフォローできないはずです
        self.assertFalse(self.world.AddOtherUserListByName(follower_user_name, owner_user_name, undefined_list_name))
        # 存在しないユーザを指定するとフォローできないはずです
        self.assertFalse(self.world.AddOtherUserListByName(follower_user_name, undefined_user_name, list_name))
        # フォロアのリストは特に代わりが無いはずです
        new_list_dic_list = self.world.GetUserListListFormatted(follower_user_name)
        self.assertEqual(list_dic_list, new_list_dic_list)

    def test_DeleteOtherUserListByNode(self):
        # 作成されるリスト名
        list_name = u"list"
        # 存在しないリスト名
        undefined_list_name = u"undefined list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストをフォローするユーザのノード
        follower_user_node = self.user_node_list[2]
        # リストをフォローするユーザのユーザ名
        follower_user_name = follower_user_node['name']
        # 存在しないユーザ名
        undefined_user_name = "undefined user name"
        # オーナがリストを作成します
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # フォロアはまだ自分のlistのリストには何も無いはずです
        self.assertEqual([], self.world.GetUserListListFormatted(follower_user_name))
        # 作成されたリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(follower_user_name, owner_user_name, list_name))
        # フォロアのリストに新しく追加されるはずです
        list_dic_list = self.world.GetUserListListFormatted(follower_user_name)
        self.assertEqual(1, len(list_dic_list))
        self.assertEqual(list_name, list_dic_list[0]['name'])
        self.assertEqual(owner_user_name, list_dic_list[0]['owner_name'])
        # 存在しないリストへのフォローを削除しようとすると、失敗するはずです
        self.assertFalse(self.world.DeleteOtherUserListByName(follower_user_name, owner_user_name, undefined_list_name))
        # 存在しないユーザを指定すると失敗するはずです
        self.assertFalse(self.world.DeleteOtherUserListByName(follower_user_name, undefined_user_name, list_name))
        # フォロアのリストは特に代わりが無いはずです
        new_list_dic_list = self.world.GetUserListListFormatted(follower_user_name)
        self.assertEqual(list_dic_list, new_list_dic_list)
        # 通常のリストのフォローの削除
        self.assertTrue(self.world.DeleteOtherUserListByName(follower_user_name, owner_user_name, list_name))
        # フォロアのlistのリストには何も無くなっているはずです
        self.assertEqual([], self.world.GetUserListListFormatted(follower_user_name))
        # フォロアがリストを作成します
        self.assertTrue(self.world.AddNodeToListByName(follower_user_name, list_name, target_user_name))
        # 自分のリストへのフォローの削除は、それが存在していても失敗します
        self.assertFalse(self.world.DeleteOtherUserListByName(follower_user_name, follower_user_name, list_name))
        # 自分のリストへのフォローの削除は、存在していなければもちろん失敗します
        self.assertFalse(self.world.DeleteOtherUserListByName(follower_user_name, follower_user_name, undefined_list_name))

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(Timeline版)
    def test_TweetToList_Timeline(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # 全員オーナを自分のタイムラインに登録します
        self.assertTrue(self.world.FollowUserByName(target_user_name, owner_user_name))
        self.assertTrue(self.world.FollowUserByName(unlisted_user_name, owner_user_name))

        # 全体に向かってtweetします
        tweet_dic = self.world.TweetByName(owner_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic['text'])
        # リストに向かってtweetします
        tweet_dic = self.world.TweetByName(owner_user_name, tweet_text, target_list=list_name, list_owner_name=owner_user_name)
        self.assertEqual(tweet_text, tweet_dic['text'])

        # リストに登録されているユーザからタイムラインで全て観測できます。
        tweet_list = self.world.GetUserTimelineFormatted(target_user_name, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザのタイムラインでは全体向けのものしか観測できません。
        tweet_list = self.world.GetUserTimelineFormatted(unlisted_user_name, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(list版)
    def test_TweetToList_List(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # 全員オーナを自分のタイムラインに登録します
        self.assertTrue(self.world.FollowUserByName(target_user_name, owner_user_name))
        self.assertTrue(self.world.FollowUserByName(unlisted_user_name, owner_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic['text'])
        # 同じくリストに向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic['text'])

        # リストに登録されているユーザからListを見ると観測できます。
        tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザではlistからの観測では全体向けのものしか観測できません。
        tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetUserTweet版)
    def test_TweetToList_GetUserTweet(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic['text'])
        # 同じくリストに向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic['text'])

        # リストに登録されているユーザから見ると観測できます。
        tweet_list = self.world.GetUserTweetFormatted(target_user_name, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetUserTweetFormatted(target_user_name, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetUserTweetFormatted(target_user_name, query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetAllUserTimeline版)
    def test_TweetToList_GetAllUserTimeline(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic['text'])
        # 同じくリストに向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic['text'])

        # リストに登録されているユーザから見ると観測できます。
        tweet_list = self.world.GetAllUserTimelineFormatted(query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetAllUserTimelineFormatted(query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetAllUserTimelineFormatted(query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetTagTweet版)
    def test_TweetToList_GetTagTweet(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # タグ
        tag_name = "#TAG"
        # tweetされる文書
        tweet_text = "hello world " + tag_name
        # tweetされる文書
        tweet_text_to_all = "hello world to all " + tag_name

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic['text'])
        # 同じくリストに向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic['text'])

        # リストに登録されているユーザから見ると観測できます。
        tweet_list = self.world.GetTagTweetFormatted(tag_name, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetTagTweetFormatted(tag_name, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetTagTweetFormatted(tag_name, query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetParentTweetAboutTweetID版)
    def test_TweetToList_GetParentTweetAboutTweetID(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # 親tweetを手繰るもののテストのため、
        # 全体向け ←[返事]- リスト向け ←[返事]- 全体向け ←[返事]- リスト向け←[返事]- 全体向け
        # というtweet　tree を生成します

        # target_user が 全体に向かってtweetします
        tweet_dic_1 = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic_1['text'])
        # 同じくリストに向かってtweetします。この時、元のtweetへの返信とします
        tweet_dic_2 = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name, reply_to=tweet_dic_1['id'])
        self.assertEqual(tweet_text, tweet_dic_2['text'])
        # target_user が 全体に向かってtweetします
        tweet_dic_3 = self.world.TweetByName(target_user_name, tweet_text_to_all, reply_to=tweet_dic_2['id'])
        self.assertEqual(tweet_text_to_all, tweet_dic_3['text'])
        # 同じくリストに向かってtweetします。この時、元のtweetへの返信とします
        tweet_dic_4 = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name, reply_to=tweet_dic_3['id'])
        self.assertEqual(tweet_text, tweet_dic_4['text'])
        # target_user が 全体に向かってtweetします
        tweet_dic_5 = self.world.TweetByName(target_user_name, tweet_text_to_all, reply_to=tweet_dic_4['id'])
        self.assertEqual(tweet_text_to_all, tweet_dic_5['text'])

        # これについて真ん中の tweet_dic_3['id'] を起点に読み出そうとします

        # リストに登録されているユーザから見ると全てを観測できます。
        tweet_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_dic_3['id'], query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])
        self.assertEqual(tweet_text, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_dic_3['id'], query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetParentTweetAboutTweetIDFormatted(tweet_dic_3['id'], query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetChildTweetAboutTweetID版)
    def test_TweetToList_GetChildTweetAboutTweetID(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # 親tweetを手繰るもののテストのため、
        # 全体向け ←[返事]- リスト向け ←[返事]- 全体向け ←[返事]- リスト向け←[返事]- 全体向け
        # というtweet　tree を生成します

        # target_user が 全体に向かってtweetします
        tweet_dic_1 = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic_1['text'])
        # 同じくリストに向かってtweetします。この時、元のtweetへの返信とします
        tweet_dic_2 = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name, reply_to=tweet_dic_1['id'])
        self.assertEqual(tweet_text, tweet_dic_2['text'])
        # target_user が 全体に向かってtweetします
        tweet_dic_3 = self.world.TweetByName(target_user_name, tweet_text_to_all, reply_to=tweet_dic_2['id'])
        self.assertEqual(tweet_text_to_all, tweet_dic_3['text'])
        # 同じくリストに向かってtweetします。この時、元のtweetへの返信とします
        tweet_dic_4 = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name, reply_to=tweet_dic_3['id'])
        self.assertEqual(tweet_text, tweet_dic_4['text'])
        # target_user が 全体に向かってtweetします
        tweet_dic_5 = self.world.TweetByName(target_user_name, tweet_text_to_all, reply_to=tweet_dic_4['id'])
        self.assertEqual(tweet_text_to_all, tweet_dic_5['text'])

        # これについて真ん中の tweet_dic_3['id'] を起点に読み出そうとします

        # リストに登録されているユーザから見ると全てを観測できます。
        tweet_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_dic_3['id'], query_user_name=target_user_name)

        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_dic_3['id'], query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetChildTweetAboutTweetIDFormatted(tweet_dic_3['id'], query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetTweetNodeFromID版)
    def test_TweetToList_GetTweetNodeFromID(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # タグ
        tag_name = "#TAG"
        # tweetされる文書
        tweet_text = "hello world " + tag_name
        # tweetされる文書
        tweet_text_to_all = "hello world to all " + tag_name

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic_to_all = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic_to_all['text'])
        # 同じくリストに向かってtweetします
        tweet_dic_to_list = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic_to_list['text'])

        # リストに登録されているユーザから見ると観測できます。
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_dic_to_all['id'], query_user_name=target_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_dic_to_list['id'], query_user_name=target_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_dic_to_all['id'], query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_dic_to_list['id'], query_user_name=unlisted_user_name)
        self.assertEqual(0, len(tweet_list))

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_dic_to_all['id'], query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_dic_to_list['id'], query_user_name=owner_user_name)
        self.assertEqual(0, len(tweet_list))

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetListTimeline版)
    def test_TweetToList_GetListTimeline(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic['text'])
        # 同じくリストに向かってtweetします
        tweet_dic = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic['text'])

        # リストに登録されているユーザから見ると全てを観測できます。
        tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetListTimelineFormatted(owner_user_name, list_name, query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(GetNECOMAtomeTweetListByID版)
    def test_TweetToList_GetNECOMAtomeTweetListByID(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"
        # まとめの要約
        matome_description = "matome description"

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic_1 = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic_1['text'])
        # 同じくリストに向かってtweetします
        tweet_dic_2 = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic_2['text'])
       
        # NECOMAtome を作ります
        matome_id = self.world.CreateNewNECOMAtomeByName(owner_user_name, [tweet_dic_1['id'], tweet_dic_2['id']], matome_description)
        self.assertTrue(matome_id >= 0)

        # リストに登録されているユーザから見ると全てを観測できます。
        tweet_list = self.world.GetNECOMAtomeTweetListByIDFormatted(matome_id, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.GetNECOMAtomeTweetListByIDFormatted(matome_id, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.GetNECOMAtomeTweetListByIDFormatted(matome_id, query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

    # リスト向けにtweetした場合、そのリストに入っているユーザ以外は観測できないことを確認する(SearchTweet版)
    def test_TweetToList_SearchTweet(self):
        # 作成されるリスト名
        list_name = u"list"
        # リストオーナーのノード
        owner_user_node = self.user_node_list[0]
        # リストオーナのユーザ名
        owner_user_name = owner_user_node['name']
        # リストに登録されるユーザのノード
        target_user_node = self.user_node_list[1]
        # リストに登録されるユーザ名
        target_user_name = target_user_node['name']
        # リストに登録されていないユーザのノード
        unlisted_user_node = self.user_node_list[2]
        # リストに登録されていないユーザ名
        unlisted_user_name = unlisted_user_node['name']
        # tweetされる文書
        tweet_text = "hello world"
        # tweetされる文書
        tweet_text_to_all = "hello world to all"
        # 検索される文字列のリスト
        search_string_list = ['hello']

        # オーナがリストを作成します(target_user_nameの一人だけが入ったリストになります)
        self.assertTrue(self.world.AddNodeToListByName(owner_user_name, list_name, target_user_name))
        # そのオーナーの作ったリストをフォローします
        self.assertTrue(self.world.AddOtherUserListByName(target_user_name, owner_user_name, list_name))
        self.assertTrue(self.world.AddOtherUserListByName(unlisted_user_name, owner_user_name, list_name))

        # target_user が 全体に向かってtweetします
        tweet_dic_1 = self.world.TweetByName(target_user_name, tweet_text_to_all)
        self.assertEqual(tweet_text_to_all, tweet_dic_1['text'])
        # 同じくリストに向かってtweetします
        tweet_dic_2 = self.world.TweetByName(target_user_name, tweet_text, list_owner_name=owner_user_name, target_list=list_name)
        self.assertEqual(tweet_text, tweet_dic_2['text'])
       
        # リストに登録されているユーザから見ると全てを観測できます。
        tweet_list = self.world.SearchTweetFormatted(search_string_list, query_user_name=target_user_name)
        self.assertEqual(2, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0]['text'])
        self.assertEqual(tweet_text_to_all, tweet_list[1]['text'])

        # リストに登録されていないユーザでは全体向けのものしか観測できません。
        tweet_list = self.world.SearchTweetFormatted(search_string_list, query_user_name=unlisted_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

        # リストのオーナも、リストには登録されていないユーザなので、全体向けのものしか観測できません。
        tweet_list = self.world.SearchTweetFormatted(search_string_list, query_user_name=owner_user_name)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text_to_all, tweet_list[0]['text'])

class NECOMATter_Retweet_TestCase(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")
        # ユーザ A, B, C を作っておきます。
        self.user_node_list = []
        for user_name in ['A', 'B', u"しー"]:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
            user_node = self.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node_list.append(user_node)

    def tearDown(self):
        pass

    def test_RetweetMany(self):
        # ユーザを増やします
        for user_name in [u'D']:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
            user_node = self.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node_list.append(user_node)
        # tweetするノード
        tweet_node = self.user_node_list[0]
        # tweetするノードの名前
        tweet_node_name = tweet_node['name']
        # tweet される文章
        tweet_text = "tweet"
        # tweetします
        target_tweet_node = self.world.TweetByName(tweet_node_name, tweet_text)
        self.assertIsNotNone(target_tweet_node)
        target_tweet_node_id = target_tweet_node['id']
        # 残りの全員でretweetします
        for retweet_node in self.user_node_list:
            retweet_node_name = retweet_node['name']
            if retweet_node_name == tweet_node_name:
                continue
            self.assertTrue(self.world.RetweetByName(retweet_node_name, target_tweet_node_id))
        # 同じくその全員をフォローしているノードを指定します(retweetしたノードの一つにします)
        follow_user_node = self.user_node_list[len(self.user_node_list) - 1]
        follow_user_name = follow_user_node['name']
        self.assertIsNotNone(follow_user_node)
        # そのノードで全員をフォローします
        for node in self.user_node_list:
            if node['name'] == follow_user_name:
                continue
            self.assertTrue(self.world.FollowUserByName(follow_user_name, node['name']))
        # 全員をフォローしたユーザのタイムラインを取得します
        tweet_list = self.world.GetUserTimelineFormatted(follow_user_name, query_user_name=follow_user_name)
        # 全員分の数だけ見えるはずです
        self.assertEqual(len(self.user_node_list), len(tweet_list))
        # tweetした人はもう一回tweetします
        tweet_text_2nd = '2nd tweet'
        target_tweet_node = self.world.TweetByName(tweet_node_name, tweet_text_2nd)
        # tweet は全員分+1個見えるはずです
        tweet_list = self.world.GetUserTimelineFormatted(follow_user_name, query_user_name=follow_user_name)
        self.assertEqual(len(self.user_node_list) + 1, len(tweet_list))

        
    def test_RetweetByName(self):
        # tweetするノード
        tweet_node = self.user_node_list[0]
        # tweetするノードの名前
        tweet_node_name = tweet_node['name']
        # retweet するノード
        retweet_node = self.user_node_list[1]
        # retweet するノードの名前
        retweet_node_name = retweet_node['name']
        # tweet される文章
        tweet_text = "tweet"
        # retweetするノードをfollowするノード
        follow_node = self.user_node_list[2]
        # followするノードの名前
        follow_node_name = follow_node['name']
        # tweetします
        target_tweet_node = self.world.TweetByName(tweet_node_name, tweet_text)
        self.assertIsNotNone(target_tweet_node)
        target_tweet_node_id = target_tweet_node['id']
        # retweetするノードのtimelineにはまだ何も無いはずです
        self.assertEqual([], self.world.GetUserTimelineFormatted(retweet_node_name, query_user_name=retweet_node_name))
        # retweetします。
        self.assertTrue(self.world.RetweetByName(retweet_node_name, target_tweet_node_id))
        # timelineに増えるはずです
        timeline_tweet_list = self.world.GetUserTimelineFormatted(retweet_node_name, query_user_name=retweet_node_name)
        self.assertEqual(1, len(timeline_tweet_list))
        self.assertEqual(False, timeline_tweet_list[0]['own_stard'])
        self.assertEqual(True, timeline_tweet_list[0]['own_retweeted'])
        self.assertEqual(tweet_node_name, timeline_tweet_list[0]['user_name'])
        self.assertEqual(retweet_node_name, timeline_tweet_list[0]['retweet_user_name'])
        self.assertEqual(True, timeline_tweet_list[0]['is_retweet'])
        # followするノードはまだfollowしていないので、timelineには何も無いはずです
        self.assertEqual([], self.world.GetUserTimelineFormatted(follow_node_name, query_user_name=follow_node_name))
        # followします
        self.assertTrue(self.world.FollowUserByName(follow_node_name, retweet_node_name))
        # followしたのでtimelineが増えるはずです
        timeline_tweet_list = self.world.GetUserTimelineFormatted(follow_node_name, query_user_name=follow_node_name)
        self.assertEqual(1, len(timeline_tweet_list))
        self.assertEqual(False, timeline_tweet_list[0]['own_stard'])
        self.assertEqual(False, timeline_tweet_list[0]['own_retweeted'])
        self.assertEqual(tweet_node_name, timeline_tweet_list[0]['user_name'])
        self.assertEqual(retweet_node_name, timeline_tweet_list[0]['retweet_user_name'])
        self.assertEqual(True, timeline_tweet_list[0]['is_retweet'])
        # unfollow すると消えるはずです
        self.assertTrue(self.world.UnFollowUserByName(follow_node_name, retweet_node_name))
        self.assertEqual([], self.world.GetUserTimelineFormatted(follow_node_name, query_user_name=follow_node_name))
        # followしなおします
        self.assertTrue(self.world.FollowUserByName(follow_node_name, retweet_node_name))
        # followしたのでtimelineが増えるはずです(二度目の確認になります)
        timeline_tweet_list = self.world.GetUserTimelineFormatted(follow_node_name, query_user_name=follow_node_name)
        self.assertEqual(1, len(timeline_tweet_list))
        self.assertEqual(False, timeline_tweet_list[0]['own_stard'])
        self.assertEqual(False, timeline_tweet_list[0]['own_retweeted'])
        self.assertEqual(tweet_node_name, timeline_tweet_list[0]['user_name'])
        self.assertEqual(retweet_node_name, timeline_tweet_list[0]['retweet_user_name'])
        self.assertEqual(True, timeline_tweet_list[0]['is_retweet'])
        # 最初にtweetした人をfollowします
        self.assertTrue(self.world.FollowUserByName(follow_node_name, tweet_node_name))
        # followしたのでtimelineが増えるはずです(retweetとtweetは別エントリとして取得されます)
        timeline_tweet_list = self.world.GetUserTimelineFormatted(follow_node_name, query_user_name=follow_node_name)
        # --
        self.assertEqual(2, len(timeline_tweet_list))
        self.assertEqual(False, timeline_tweet_list[0]['own_stard'])
        self.assertEqual(False, timeline_tweet_list[0]['own_retweeted'])
        self.assertEqual(tweet_node_name, timeline_tweet_list[0]['user_name'])
        self.assertEqual(retweet_node_name, timeline_tweet_list[0]['retweet_user_name'])
        self.assertEqual(True, timeline_tweet_list[0]['is_retweet'])
        # --
        self.assertEqual(False, timeline_tweet_list[1]['own_stard'])
        self.assertEqual(False, timeline_tweet_list[1]['own_retweeted'])
        self.assertEqual(tweet_node_name, timeline_tweet_list[1]['user_name'])
        self.assertIsNone(timeline_tweet_list[1]['retweet_user_name'])
        self.assertEqual(False, timeline_tweet_list[1]['is_retweet'])
        # followされたユーザがユーザ登録を消します
        self.assertTrue(self.world.DeleteUser(retweet_node_name))
        # retweetしたユーザが消えたので、timelineから減るはずです
        timeline_tweet_list = self.world.GetUserTimelineFormatted(follow_node_name, query_user_name=follow_node_name)
        self.assertEqual(1, len(timeline_tweet_list))
        self.assertEqual(False, timeline_tweet_list[0]['own_stard'])
        self.assertEqual(False, timeline_tweet_list[0]['own_retweeted'])
        self.assertEqual(tweet_node_name, timeline_tweet_list[0]['user_name'])
        self.assertIsNone(timeline_tweet_list[0]['retweet_user_name'])
        self.assertEqual(False, timeline_tweet_list[0]['is_retweet'])

class NECOMATter_Star_TestCase(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")
        # ユーザ A, B, C, D を作っておきます。
        self.user_node_list = []
        for user_name in ['A', 'B', u"しー", u"でぃー"]:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
            user_node = self.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node_list.append(user_node)

    def tearDown(self):
        pass

    def test_AddStarByName(self):
        # tweet するノード
        tweet_user_node = self.user_node_list[0]
        # tweet するノードの名前
        tweet_user_node_name = tweet_user_node['name']
        # tweet の内容
        tweet_text = "tweet"
        # (tweet_node)がtweetします
        tweet_result = self.world.TweetByName(tweet_user_node_name, tweet_text)
        self.assertIsNotNone(tweet_result)
        tweet_node_id = tweet_result['id']
        # 最初はtweet_node にはstarがついていないはずです
        tweet_list = self.world.GetTweetNodeFromIDFormatted(tweet_node_id, tweet_user_node_name)
        self.assertEqual(1, len(tweet_list))
        tweet_dic = tweet_list[0]
        self.assertEqual(tweet_node_id, tweet_dic['id'])
        self.assertFalse(tweet_dic['own_stard'])
        tweet_dic = self.world.GetTweetAdvancedInfoFormatted(tweet_node_id, tweet_user_node_name)
        self.assertEqual(tweet_node_id, tweet_dic['id'])
        self.assertEqual(tweet_text, tweet_dic['text'])
        self.assertEqual(tweet_result['unix_time'], tweet_dic['unix_time'])
        self.assertEqual(tweet_result['time'], tweet_dic['time'])
        self.assertEqual(tweet_user_node_name, tweet_dic['user_name'])
        self.assertEqual(0, tweet_dic['stard_count'])
        self.assertEqual(0, tweet_dic['retweeted_count'])
        # star をつけます
        self.assertTrue(self.world.AddStarByName(self.user_node_list[1]['name'], tweet_node_id))
        self.assertTrue(self.world.AddStarByName(self.user_node_list[2]['name'], tweet_node_id))
        self.assertTrue(self.world.AddStarByName(self.user_node_list[3]['name'], tweet_node_id))
        # star の数が増えているはずです
        tweet_dic = self.world.GetTweetAdvancedInfoFormatted(tweet_node_id, tweet_user_node_name)
        self.assertEqual(3, tweet_dic['stard_count'])
        # star を減らします
        self.assertTrue(self.world.DeleteStarByName(self.user_node_list[1]['name'], tweet_node_id))
        # star の数が減っているはずです
        tweet_dic = self.world.GetTweetAdvancedInfoFormatted(tweet_node_id, tweet_user_node_name)
        self.assertEqual(2, tweet_dic['stard_count'])
        # 二重にstar をつけようとすると失敗します
        self.assertFalse(self.world.AddStarByName(self.user_node_list[2]['name'], tweet_node_id))
        # 二重にstarを外そうとしても失敗します
        self.assertFalse(self.world.DeleteStarByName(self.user_node_list[1]['name'], tweet_node_id))
        # star の数に変化は無いはずです
        tweet_dic = self.world.GetTweetAdvancedInfoFormatted(tweet_node_id, tweet_user_node_name)
        self.assertEqual(2, tweet_dic['stard_count'])


# 検索のテストケース
class NECOMATter_Search_TestCase(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")
        # ユーザ A, B, C, D を作っておきます。
        self.user_node_list = []
        for user_name in ['A', 'B', u"しー", u"でぃー"]:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
            user_node = self.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node_list.append(user_node)

    def tearDown(self):
        pass

    def test_SearchTweet(self):
        # tweet するノード
        tweet_user_node = self.user_node_list[0]
        # tweet するノードの名前
        tweet_user_node_name = tweet_user_node['name']
        # tweet の内容
        tweet_text = u"tweet ついーと 日本語 1x*#tag() "
        # (tweet_node)がtweetします
        tweet_result = self.world.TweetByName(tweet_user_node_name, tweet_text)
        tweet_list = self.world.SearchTweet([".*"], tweet_user_node)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0][0])

        tweet_list = self.world.SearchTweet([".*", "tweet.*"], tweet_user_node)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0][0])

        tweet_list = self.world.SearchTweet([".*", ".*ついーと.*"], tweet_user_node)
        self.assertEqual(1, len(tweet_list))
        self.assertEqual(tweet_text, tweet_list[0][0])

# ダミーデータを突っ込むためのテストケース
class NECOMATter_CreateDummyData(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")
        # それらしく寝る時間の倍率。
        self.sleep_mag = 1

    def tearDown(self):
        pass

    def Tweet(self, name, text):
        tweet_result = self.world.TweetByName(name, text)
        self.assertIsNotNone(tweet_result)
        return tweet_result

    def Reply(self, name, text, tweet_result):
        tweet_result = self.world.TweetByName(name, text, tweet_result['id'])
        self.assertIsNotNone(tweet_result)
        return tweet_result

    # 指定された秒だけ寝て、logをそれらしく並べます。
    def Sleep(self, second):
        time.sleep(second * self.sleep_mag)

    def test_Scenario1(self):
        for user_name in ['iimura', 'hadoop team', u"NECOMATter System", u"tarou"]:
            self.assertTrue(self.world.AddUser(user_name, "password")[0])
            user_node = self.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node_list.append(user_node)

        self.Tweet("hadoop team", """hadoop team discovered a sign of #ZEUS-DGA filter on dns query.

date: from 2014/04/20 to 2014/04/22
```
f528764d624db129b32c21fbca0cb8d6.com
gcqsjy2111ybiibq96yxixixduny7tdf6f94czn.com
rotzfrech360grad24hnonstopshoutcastradio.net
eef795a4eddaf1e7bd79212acc9dde16.net
www.gan24ql0lf558kn66l376079sy9qxr6bs.org
```""")
        self.Sleep(63)
        self.Tweet("hadoop team", """hadoop team discovered a sign of the phishing.

date: from 2014/04/20 to 2014/04/22

paypal #phishing :
```
paypal.com.cgi.bin.webscr.cmd.login.submit.dispatch.c13c0dn63663d3faee8db2b24f7
paypal.com.ddcfa29tjh8dna9.gcqsjy2111ybiibq96yxixixduny7tdf6f94czn.com
paypal.com.de.bin.webscr.cmd.login.submit.dispatch.c13c0dn63663d3faee8db2b24f7l
paypal.com.verify.securearea.billing.confirm.update.information.service.5885d80
paypal.fr.cgi.bin.webscr.cmd.login.submit.dispatch.5885d80a13c0db1f8e263663d3fa
paypal-update.848cdd7e94f206f9de2ab99f072709fb91461cb553bde1e86ae4d.com.techice
paypal-update.848cdd7e94f206f9de2ab99f072709fb91461cb553bde1e86ae4d.com.techice
www.paypal.com.verify.securearea.billing.confirm.update.information.service.588
```""")
        self.Sleep(32)
        tweet_node = self.Tweet("iimura", u"""#ZEUS-DGA 周りで何か出ているね。Agurim 側で出てるこれって何かの兆候？
--iframe[http//mawi.wide.ad.jp/members_only/aguri2/agurim/detail.html?&criteria=packet&duration=64800&endTimeStamp=2014-01-15]--""")
        self.Sleep(4)
        self.Tweet("NECOMATter System", """node link summary:
--iframe[/static/img/Neo4J.png]--""")
        self.Sleep(43)
        self.Reply("tarou", u"""@iimura #ZEUS-DGA でヒットした結果を見ると前に比べて最近は落ち着いているみたいに見えるけれど、どうなのかなこれ。
--iframe[http//hadoop-master.sekiya-lab.info/matatabi/zeus-dga/query_count/?time.min=20140101&time.max=20141231]--""", tweet_node)
        self.Sleep(23)
        self.Reply("tarou", u"""@limura PhishTank のこれとかが近いかも。
https://www.phishtank.com/phish_detail.php?phish_id=2431357""", tweet_node)
        self.Sleep(72)
        self.Tweet("iimura", u"""とりあえずまとめを作ってみたよ。
http://necomatter.necoma-project.jp/matome/85""")

        
# テストのひな形
class NECOMATter_TestSkelton(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMATter("http://localhost:17474")
        # それらしく寝る時間の倍率。
        self.sleep_mag = 1

    def tearDown(self):
        pass

    # 書き込みます
    def mew(self, name, text, reply_to=None, target_list=None, list_owner_name=None):
        tweet_result = self.world.TweetByName(name, text, reply_to=reply_to, target_list=target_list, list_owner_name=list_owner_name)
        self.assertIsNotNone(tweet_result)
        self.assertEqual(text, tweet_result['text'])
        return tweet_result

    # 指定された秒だけ寝て、logをそれらしく並べます。
    def sleep(self, second):
        time.sleep(second * self.sleep_mag)

    # ユーザを作成します
    def addUser(self, user_name, password):
        result = self.world.AddUser(user_name, password)
        self.assertTrue(result[0])

    # リストにユーザを追加します
    def addUserToList(self, user_name, target_list, append_user_name):
        self.assertTrue(self.world.AddNodeToListByName(user_name, target_list, append_user_name))

    # 全てのユーザのtweetを参照します
    def getAllUserTimeline(self, query_user_name):
        return self.world.GetAllUserTimelineFormatted(query_user_name)

# 検閲済みのテスト
class NECOMATter_CensordMew(NECOMATter_TestSkelton):
    # ユーザを検閲権限ありに設定します
    def pullUpCert(self, user_name):
        self.assertTrue(self.world.AssignCensorshipAuthorityToUserByName(user_name))
    
    # 検閲ありに設定してtweetするとadminにしか読めない
    def test_CanReadAdmin(self):
        # 検閲ありに設定します
        self.world.EnableCensorshipAuthorityFeature()
        # 新しくユーザを作ります
        user_name = "iimura"
        password = "password"
        self.addUser(user_name, password)
        # 作ったユーザの権限を検閲できる人間に変更します
        self.pullUpCert(user_name)

        # 別のユーザを作ります
        normal_user_name = "normal user"
        self.addUser(normal_user_name, password)

        # mewします
        mew_msg = "hello world from admin."
        self.mew(normal_user_name, mew_msg)

        # admin は読めます
        result = self.getAllUserTimeline(user_name)
        self.assertEqual(1, len(result))
        self.assertEqual(mew_msg, result[0]['text'])
        self.assertEqual("<ForCensorshipAuthority>", result[0]['list_name'])
        self.assertIsNone(result[0]['list_owner_name'])
        # 通常ユーザは読めません
        result = self.getAllUserTimeline(normal_user_name)
        self.assertEqual(0, len(result))
        
    
    # 検閲ありに設定してtweetするとadminにしか読めない(通常ユーザのtweet版)
    def test_CanReadAdminFromNormalUser(self):
        # 検閲ありに設定します
        self.world.EnableCensorshipAuthorityFeature()
        # 新しくユーザを作ります
        user_name = "iimura"
        password = "password"
        self.addUser(user_name, password)
        # 作ったユーザの権限を検閲できる人間に変更します
        self.pullUpCert(user_name)

        # 別のユーザを作ります
        normal_user_name = "normal user"
        self.addUser(normal_user_name, password)

        # mewします
        mew_msg = "hello world from normal user."
        self.mew(normal_user_name, mew_msg)

        # admin は読めます
        result = self.getAllUserTimeline(user_name)
        self.assertEqual(1, len(result))
        self.assertEqual(mew_msg, result[0]['text'])
        self.assertEqual("<ForCensorshipAuthority>", result[0]['list_name'])
        self.assertIsNone(result[0]['list_owner_name'])
        # 通常ユーザは読めません
        result = self.getAllUserTimeline(normal_user_name)
        self.assertEqual(0, len(result))

    # 検閲ありに設定してtweetしたものを、検閲解除すると誰からでも読める
    def test_CanReadPublishedMew(self):
        # 検閲ありに設定します
        self.world.EnableCensorshipAuthorityFeature()
        # 新しくユーザを作ります
        user_name = "iimura"
        password = "password"
        self.addUser(user_name, password)
        # 作ったユーザの権限を検閲できる人間に変更します
        self.pullUpCert(user_name)

        # 別のユーザを作ります
        normal_user_name = "normal user"
        self.addUser(normal_user_name, password)

        # mewします
        mew_msg = "hello world from admin."
        mew = self.mew(normal_user_name, mew_msg)

        # 検閲を解除します
        self.world.OpenToPublicCensordMew(mew['id'])

        # admin は読めます
        result = self.getAllUserTimeline(user_name)
        self.assertEqual(1, len(result))
        self.assertEqual(mew_msg, result[0]['text'])
        # 通常ユーザも読めます
        result = self.getAllUserTimeline(normal_user_name)
        self.assertEqual(1, len(result))
        self.assertEqual(mew_msg, result[0]['text'])
        
    # 検閲ありに設定してtweetしたものを、検閲解除すると誰からでも読める(通常ユーザのtweet版)
    def test_CanReadPublishedMewNormalUser(self):
        # 検閲ありに設定します
        self.world.EnableCensorshipAuthorityFeature()
        # 新しくユーザを作ります
        user_name = "iimura"
        password = "password"
        self.addUser(user_name, password)
        # 作ったユーザの権限を検閲できる人間に変更します
        self.pullUpCert(user_name)

        # 別のユーザを作ります
        normal_user_name = "normal user"
        self.addUser(normal_user_name, password)

        # mewします
        mew_msg = "hello world from normal user."
        mew = self.mew(normal_user_name, mew_msg)

        # 検閲を解除します
        self.world.OpenToPublicCensordMew(mew['id'])

        # admin は読めます
        result = self.getAllUserTimeline(user_name)
        self.assertEqual(1, len(result))
        self.assertEqual(mew_msg, result[0]['text'])
        # 通常ユーザも読めます
        result = self.getAllUserTimeline(normal_user_name)
        self.assertEqual(1, len(result))
        self.assertEqual(mew_msg, result[0]['text'])
        
       
if __name__ == '__main__':
    assert StartNeo4J()
    unittest.main()
    assert StopNeo4J()






