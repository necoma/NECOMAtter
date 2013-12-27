#!/usr/bin/python
# coding: UTF-8
# NECOMATter のテスト

import sys
import os
import unittest
import subprocess
import shutil
import logging
import json
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMATter import NECOMATter
import index
from py2neo import neo4j, cypher

# このファイルのある場所でないと動かないので chdir します
os.chdir(os.path.dirname(os.path.abspath(__file__)))

Neo4JCmd = "./neo4j/bin/neo4j"
Neo4JDataDir = "./neo4j/data"
Neo4JLogDir = "./neo4j/data/log"

DummyDBURL = "http://localhost:17474"
gdb = neo4j.GraphDatabaseService("%s/db/data/" % DummyDBURL)

logging.basicConfig(level=logging.INFO)

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

class IndexTestCase(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.app = index.app.test_client()
        # 怪しくapp の world object を別のNECOMATter object で上書きします
        index.world = NECOMATter(DummyDBURL)

    def tearDown(self):
        pass

    def signin(self, user_name, password):
        return self.post("/signin", data=dict(user_name=user_name, password=password), follow_redirects=True)

    def signout(self):
        return self.get("/signout", follow_redirects=True)

class IndexTestCase_Simple(IndexTestCase):
    # /usr_name_list.json の取得(ユーザが居ない場合)
    def test_user_name_list_json_no_user(self):
        rv = self.app.get('/user_name_list.json')
        data = json.loads(rv.data)
        self.assertEqual([], data)

    # /usr_name_list.json の取得(ユーザがいる場合)
    def test_user_name_list_json_with_user(self):
        # ユーザを作成する
        user_name = "iimura"
        password = "password"
        self.assertTrue(index.world.AddUser(user_name, password))
        # 取得してみる
        rv = self.app.get('/user_name_list.json')
        data = json.loads(rv.data)
        self.assertEqual([user_name], data)

    # /user/<user_name>.json の取得(ユーザが居ない場合)
    def test_user_name_json_no_user(self):
        rv = self.app.get('/user/iimura.json')
        data = json.loads(rv.data)
        self.assertEqual([], data)

    # /user/<user_name>.json の取得(ユーザがいる場合)
    def test_user_name_json_with_user(self):
        # ユーザを作成する
        user_name = "iimura"
        password = "password"
        self.assertTrue(index.world.AddUser(user_name, password))
        # 取得する
        rv = self.app.get('/user/%s.json' % user_name)
        data = json.loads(rv.data)
        self.assertEqual([], data)

    # /user/<user_name>.json の取得(ユーザがいて、tweetもある場合)
    def test_user_name_json_with_user_with_tweet(self):
        # ユーザを作成する
        user_name = "iimura"
        password = "password"
        self.assertTrue(index.world.AddUser(user_name, password))
        user_node = index.world.GetUserNode(user_name)
        self.assertIsNotNone(user_node)
        # tweet する
        tweet_text = "hello world"
        self.assertTrue(index.world.Tweet(user_node, tweet_text))
        # 取得する
        rv = self.app.get('/user/%s.json' % user_name)
        data = json.loads(rv.data)
        self.assertEqual(1, len(data))
        self.assertEqual(tweet_text, data[0]['text'])
        self.assertEqual(user_name, data[0]['user_name'])

    # /tweet/tweetID.json の取得(存在しないtweet)
    def test_tweet_tweetID_json(self):
        rv = self.app.get('/tweet/%d.json' % 1)
        data = json.loads(rv.data)
        self.assertEqual(0, len(data))
        
    # /tweet/<tweetID>_tree.json の取得(存在しないものの場合)
    def test_tweet_tweetID_tree_json(self):
        rv = self.app.get('/tweet/%d_tree.json' % 1)
        data = json.loads(rv.data)
        self.assertEqual(0, len(data))

    # /tweet/<tweetID>_parent.json の取得(存在しないものの場合)
    def test_tweet_tweetID_parent_json(self):
        rv = self.app.get('/tweet/%d_parent.json' % 1)
        data = json.loads(rv.data)
        self.assertEqual(0, len(data))

    # /tweet/<tweetID>_child.json の取得(存在しないものの場合)
    def test_tweet_tweetID_child_json(self):
        rv = self.app.get('/tweet/%d_child.json' % 1)
        data = json.loads(rv.data)
        self.assertEqual(0, len(data))

# 最初からユーザが何人かとtweetがいくつかある状態でテストを開始するテストケースです
class IndexTestCase_SomeUserAndTweet(IndexTestCase):
    def setUp(self):
        IndexTestCase.setUp(self)
        self.user_node = []
        self.user_password = "password"
        # ユーザを作ります
        # ユーザ名は user_name0, user_name1, ..., user_name9 です
        for n in range(0, 10):
            user_name = "user_name%d" % n
            self.assertTrue(index.world.AddUser(user_name, self.user_password))
            user_node = index.world.GetUserNode(user_name)
            self.assertIsNotNone(user_node)
            self.user_node.append(user_node)
        # follow させます
        # 0 は、1, 2, 3, 4, 5, 6 7, 8, 9 をfollow している(つまり全員)
        # 1 は、誰もfollowしていない(timeline には1が出る)
        # 2 は、0, 1, 3, 4, 5 をfollowしている(timeline には 0～5 が出る)
        # 3 は、6, 7, 8, 9 をfollow している(timeline には3, 6～9 が出る)
        # 後は誰もfollowしていない(timeline には自分だけが出る)
        for n in range(1, 10):
            self.assertTrue(index.world.FollowUserByNode(self.user_node[0], self.user_node[n]))
        for n in range(0, 6):
            if n != 2:
                self.assertTrue(index.world.FollowUserByNode(self.user_node[2], self.user_node[n]))
        for n in range(6, 10):
            self.assertTrue(index.world.FollowUserByNode(self.user_node[3], self.user_node[n]))
        # tweet させます
        # 0 は、tweet を5回 します。タグとして'#0' をつけます
        user_node = self.user_node[0]
        self.user_tweet = []
        tweet_list = []
        for n in range(0, 5):
            tweet_text = "hello from 0:%d #0" % n
            tweet_node = index.world.Tweet(user_node, tweet_text)
            self.assertIsNotNone(tweet_node)
            tweet_list.append(tweet_node)
        self.user_tweet.append(tweet_list)
        # 1と2 は、0 のtweet に対して返事を一通づつ書きます。タグとして '#12' をつけます
        for n in range(1, 3):
            user_node = self.user_node[n]
            tweet_list = []
            i = 0
            for parent_tweet in self.user_tweet[0]:
                target_id = parent_tweet._id
                tweet_text = "reply from %d to 0:%d #12" % (n, i)
                tweet_node = index.world.Tweet(user_node, tweet_text, target_id)
                self.assertIsNotNone(tweet_node)
                tweet_list.append(tweet_node)
                i += 1
            self.user_tweet.append(tweet_list)
        # 3 は、1 のtweetに対して返事を一通づつ書きます。タグとして '#3' をつけます
        user_node = self.user_node[3]
        tweet_list = []
        i = 0
        for parent_tweet in self.user_tweet[1]:
            target_id = parent_tweet._id
            tweet_text = "reply from %d to 1:%d #3" % (3, i)
            tweet_node = index.world.Tweet(user_node, tweet_text, target_id)
            self.assertIsNotNone(tweet_node)
            tweet_list.append(tweet_node)
            i += 1
        self.user_tweet.append(tweet_list)
        # ここまでで、以下のようなtweetのリストになるはずです。
        #
        # 0:0 <- 1:0 <- 3:0
        #   ^--- 2:0
        # 0:1 <- 1:1 <- 3:1
        #   ^--- 2:1
        # 0:2 <- 1:2 <- 3:2
        #   ^--- 2:2
        # 0:3 <- 1:3 <- 3:3
        #   ^--- 2:3
        # 0:4 <- 1:4 <- 3:4
        #   ^--- 2:4
        #
        # で、フォロー関係が怪しい事になっているので、
        # ユーザごとのタイムラインは
        # 0: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 1: 1:0, 1:1, 1:2, 1:3, 1:4
        # 2: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 3: 0:0, 0:1, 0:2, 0:3, 0:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # になるはず。

    def tearDown(self):
        IndexTestCase.tearDown(self)

    def test_user_name_json_user_name0(self):
        # 0 のユーザのtweet を確認します
        user_name = "user_name0"
        rv = self.app.get('/user/%s.json' % user_name)
        data = json.loads(rv.data)
        self.assertEqual(5, len(data))
        for n in range(0, 5):
            tweet_text = "hello from 0:%d #0" % (4-n)
            self.assertEqual(tweet_text, data[n]['text'])
            self.assertEqual(user_name, data[n]['user_name'])

    def test_user_name_json_user_name1(self):
        # 1 のユーザのtweet を確認します
        user_name = "user_name1"
        rv = self.app.get('/user/%s.json' % user_name)
        data = json.loads(rv.data)
        self.assertEqual(5, len(data))
        target_no = 0
        for tweet in reversed(data):
            tweet_text = "reply from %d to 0:%d #12" % (1, target_no)
            self.assertEqual(tweet_text, tweet['text'])
            self.assertEqual(user_name, tweet['user_name'])
            target_no += 1

    def test_user_name_json_user_name2(self):
        # 2 のユーザのtweet を確認します
        user_name = "user_name2"
        rv = self.app.get('/user/%s.json' % user_name)
        data = json.loads(rv.data)
        self.assertEqual(5, len(data))
        target_no = 0
        for tweet in reversed(data):
            tweet_text = "reply from %d to 0:%d #12" % (2, target_no)
            self.assertEqual(tweet_text, tweet['text'])
            self.assertEqual(user_name, tweet['user_name'])
            target_no += 1

    def test_user_name_json_user_name3(self):
        # 3 のユーザのtweet を確認します
        user_name = "user_name3"
        rv = self.app.get('/user/%s.json' % user_name)
        data = json.loads(rv.data)
        self.assertEqual(5, len(data))
        target_no = 0
        for tweet in reversed(data):
            tweet_text = "reply from %d to 1:%d #3" % (3, target_no)
            self.assertEqual(tweet_text, tweet['text'])
            self.assertEqual(user_name, tweet['user_name'])
            target_no += 1

    # /usr_name_list.json の取得
    def test_user_name_list_json(self):
        rv = self.app.get('/user_name_list.json')
        data = json.loads(rv.data)
        answer = []
        for n in range(0, 10):
            user_name = "user_name%d" % n
            answer.append(user_name)
        self.assertEqual(answer, data)

    # /tweet/<tweetID>.json の取得
    def test_tweet_tweetID_json(self):
        answer_tweet = self.user_tweet[0][0]
        rv = self.app.get('/tweet/%d.json' % answer_tweet._id)
        data = json.loads(rv.data)
        self.assertEqual(1, len(data))
        got_tweet = data[0]
        self.assertEqual(answer_tweet['text'], got_tweet['text'])
        self.assertEqual(answer_tweet._id, got_tweet['id'])

    # /tweet/<tweetID>_tree.json の取得
    def test_tweet_tweetID_tree_json(self):
        # 1:0 を取得すると、0:0 <- 1:0 <- 2:0 のtreeが得られる
        answer_tweet = self.user_tweet[1][0]
        answer_user_id_list = [0, 1, 3]
        rv = self.app.get('/tweet/%d_tree.json' % answer_tweet._id)
        data = json.loads(rv.data)
        self.assertEqual(len(answer_user_id_list), len(data))
        for i in answer_user_id_list:
            text, id = (self.user_tweet[i][0]['text'], self.user_tweet[i][0]._id)
            got_tweet = data.pop(0)
            self.assertEqual(text, got_tweet['text'],
                    "user #%d tweet is not collect: %s <-> %s" %
                    (i, text, got_tweet['text']))
            self.assertEqual(id, got_tweet['id'],
                    "user #%d tweet is not collect: %d <-> %d" %
                    (i, id, got_tweet['id']))

    # /tweet/<tweetID>_parent.json の取得
    def test_tweet_tweetID_parent_json_case1(self):
        # 3:0 を取得すると、0:0 <- 1:0 が得られる
        answer_tweet = self.user_tweet[3][0]
        answer_user_id_list = [0, 1]
        rv = self.app.get('/tweet/%d_parent.json' % answer_tweet._id)
        data = json.loads(rv.data)
        self.assertEqual(len(answer_user_id_list), len(data))
        for i in answer_user_id_list:
            text, id = (self.user_tweet[i][0]['text'], self.user_tweet[i][0]._id)
            got_tweet = data.pop(0)
            self.assertEqual(text, got_tweet['text'],
                    "user #%d tweet is not collect: %s <-> %s" %
                    (i, text, got_tweet['text']))
            self.assertEqual(id, got_tweet['id'],
                    "user #%d tweet is not collect: %d <-> %d" %
                    (i, id, got_tweet['id']))
        
    # /tweet/<tweetID>_parent.json の取得
    def test_tweet_tweetID_parent_json_case2(self):
        # 2:0 を取得すると、0:0 が得られる
        answer_tweet = self.user_tweet[2][0]
        answer_user_id_list = [0]
        rv = self.app.get('/tweet/%d_parent.json' % answer_tweet._id)
        data = json.loads(rv.data)
        self.assertEqual(len(answer_user_id_list), len(data))
        for i in answer_user_id_list:
            text, id = (self.user_tweet[i][0]['text'], self.user_tweet[i][0]._id)
            got_tweet = data.pop(0)
            self.assertEqual(text, got_tweet['text'],
                    "user #%d tweet is not collect: %s <-> %s" %
                    (i, text, got_tweet['text']))
            self.assertEqual(id, got_tweet['id'],
                    "user #%d tweet is not collect: %d <-> %d" %
                    (i, id, got_tweet['id']))
        
    # /tweet/<tweetID>_child.json の取得
    def test_tweet_tweetID_child_json(self):
        # 0:0 を取得すると、1:0, 2:0, 3:0 が得られる
        answer_tweet = self.user_tweet[0][0]
        answer_user_id_list = [1, 2, 3]
        rv = self.app.get('/tweet/%d_child.json' % answer_tweet._id)
        data = json.loads(rv.data)
        self.assertEqual(len(answer_user_id_list), len(data))
        for i in answer_user_id_list:
            text, id = (self.user_tweet[i][0]['text'], self.user_tweet[i][0]._id)
            got_tweet = data.pop(0)
            self.assertEqual(text, got_tweet['text'],
                    "user #%d tweet is not collect: %s <-> %s" %
                    (i, text, got_tweet['text']))
            self.assertEqual(id, got_tweet['id'],
                    "user #%d tweet is not collect: %d <-> %d" %
                    (i, id, got_tweet['id']))

    # /user/<user_name>/followed_user_name_list.json の取得(全員フォローしている)
    def test_user_userName_followed_user_name_list_json_user0(self):
        # follow 関係は
        # 0 は、1, 2, 3, 4, 5, 6 7, 8, 9 をfollow している(つまり全員)
        # 1 は、誰もfollowしていない(timeline には1が出る)
        # 2 は、0, 1, 3, 4, 5 をfollowしている(timeline には 0～5 が出る)
        # 3 は、6, 7, 8, 9 をfollow している(timeline には3, 6～9 が出る)
        # 後は誰もfollowしていない(timeline には自分だけが出る)
        target_user_name = self.user_node[0]['name']
        rv = self.app.get('/user/%s/followed_user_name_list.json' % target_user_name)
        data = json.loads(rv.data)
        self.assertEqual([
            self.user_node[1]['name'],
            self.user_node[2]['name'],
            self.user_node[3]['name'],
            self.user_node[4]['name'],
            self.user_node[5]['name'],
            self.user_node[6]['name'],
            self.user_node[7]['name'],
            self.user_node[8]['name'],
            self.user_node[9]['name'],
            self.user_node[0]['name'] # 自分の情報も最後につきます
            ], data)
        
    # /user/<user_name>/followed_user_name_list.json の取得(誰もフォローしていない)
    def test_user_userName_followed_user_name_list_json_user1(self):
        # follow 関係は
        # 0 は、1, 2, 3, 4, 5, 6 7, 8, 9 をfollow している(つまり全員)
        # 1 は、誰もfollowしていない(timeline には1が出る)
        # 2 は、0, 1, 3, 4, 5 をfollowしている(timeline には 0～5 が出る)
        # 3 は、6, 7, 8, 9 をfollow している(timeline には3, 6～9 が出る)
        # 後は誰もfollowしていない(timeline には自分だけが出る)
        target_user_name = self.user_node[1]['name']
        rv = self.app.get('/user/%s/followed_user_name_list.json' % target_user_name)
        data = json.loads(rv.data)
        self.assertEqual([
            self.user_node[1]['name']
            ], data)

    # /user/<user_name>/followed_user_name_list.json の取得(一部フォローしている)
    def test_user_userName_followed_user_name_list_json_user2(self):
        # follow 関係は
        # 0 は、1, 2, 3, 4, 5, 6 7, 8, 9 をfollow している(つまり全員)
        # 1 は、誰もfollowしていない(timeline には1が出る)
        # 2 は、0, 1, 3, 4, 5 をfollowしている(timeline には 0～5 が出る)
        # 3 は、6, 7, 8, 9 をfollow している(timeline には3, 6～9 が出る)
        # 後は誰もfollowしていない(timeline には自分だけが出る)
        target_user_name = self.user_node[2]['name']
        rv = self.app.get('/user/%s/followed_user_name_list.json' % target_user_name)
        data = json.loads(rv.data)
        self.assertEqual([
            self.user_node[0]['name'],
            self.user_node[1]['name'],
            self.user_node[3]['name'],
            self.user_node[4]['name'],
            self.user_node[5]['name'],
            self.user_node[2]['name'] # 自分の情報も最後につきます
            ], data)

    # /user/<user_name>/followed_user_name_list.json の取得(一部フォローしている)
    def test_user_userName_followed_user_name_list_json_user3(self):
        # follow 関係は
        # 0 は、1, 2, 3, 4, 5, 6 7, 8, 9 をfollow している(つまり全員)
        # 1 は、誰もfollowしていない(timeline には1が出る)
        # 2 は、0, 1, 3, 4, 5 をfollowしている(timeline には 0～5 が出る)
        # 3 は、6, 7, 8, 9 をfollow している(timeline には3, 6～9 が出る)
        # 後は誰もfollowしていない(timeline には自分だけが出る)
        target_user_name = self.user_node[3]['name']
        rv = self.app.get('/user/%s/followed_user_name_list.json' % target_user_name)
        data = json.loads(rv.data)
        self.assertEqual([
            self.user_node[6]['name'],
            self.user_node[7]['name'],
            self.user_node[8]['name'],
            self.user_node[9]['name'],
            self.user_node[3]['name'] # 自分の情報も最後につきます
            ], data)

    # /timeline/<user_name>.json の取得
    def test_timeline_userName_user0(self):
        # ユーザごとのタイムラインは
        # 0: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 1: 1:0, 1:1, 1:2, 1:3, 1:4
        # 2: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 3: 0:0, 0:1, 0:2, 0:3, 0:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # のはず。(これが逆向きに(時間sortで古い物順に)返ってくる)
        target_user_name = self.user_node[0]['name']
        rv = self.app.get('/timeline/%s.json' % target_user_name)
        data = json.loads(rv.data)
        for user_index, tweet_index in reversed([
                (0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                (1, 0), (1, 1), (1, 2), (1, 3), (1, 4),
                (2, 0), (2, 1), (2, 2), (2, 3), (2, 4),
                (3, 0), (3, 1), (3, 2), (3, 3), (3, 4)
                ]):
            tweet_data = data.pop(0)
            answer_tweet = self.user_tweet[user_index][tweet_index]
            self.assertEqual(answer_tweet['text'], tweet_data['text'])
            self.assertEqual(answer_tweet._id, tweet_data['id'])
            
    # /timeline/<user_name>.json の取得
    def test_timeline_userName_user1(self):
        # ユーザごとのタイムラインは
        # 0: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 1: 1:0, 1:1, 1:2, 1:3, 1:4
        # 2: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 3: 0:0, 0:1, 0:2, 0:3, 0:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # のはず。(これが逆向きに(時間sortで古い物順に)返ってくる)
        target_user_name = self.user_node[1]['name']
        rv = self.app.get('/timeline/%s.json' % target_user_name)
        data = json.loads(rv.data)
        for user_index, tweet_index in reversed([
                (1, 0), (1, 1), (1, 2), (1, 3), (1, 4)
                ]):
            tweet_data = data.pop(0)
            answer_tweet = self.user_tweet[user_index][tweet_index]
            self.assertEqual(answer_tweet['text'], tweet_data['text'])
            self.assertEqual(answer_tweet._id, tweet_data['id'])
            
    # /timeline/<user_name>.json の取得
    def test_timeline_userName_user2(self):
        # ユーザごとのタイムラインは
        # 0: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 1: 1:0, 1:1, 1:2, 1:3, 1:4
        # 2: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 3: 0:0, 0:1, 0:2, 0:3, 0:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # のはず。(これが逆向きに(時間sortで古い物順に)返ってくる)
        target_user_name = self.user_node[2]['name']
        rv = self.app.get('/timeline/%s.json' % target_user_name)
        data = json.loads(rv.data)
        for user_index, tweet_index in reversed([
                (0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                (1, 0), (1, 1), (1, 2), (1, 3), (1, 4),
                (2, 0), (2, 1), (2, 2), (2, 3), (2, 4),
                (3, 0), (3, 1), (3, 2), (3, 3), (3, 4)
                ]):
            tweet_data = data.pop(0)
            answer_tweet = self.user_tweet[user_index][tweet_index]
            self.assertEqual(answer_tweet['text'], tweet_data['text'])
            self.assertEqual(answer_tweet._id, tweet_data['id'])
            
    # /timeline/<user_name>.json の取得
    def test_timeline_userName_user3(self):
        # ユーザごとのタイムラインは
        # 0: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 1: 1:0, 1:1, 1:2, 1:3, 1:4
        # 2: 0:0, 0:1, 0:2, 0:3, 0:4, 1:0, 1:1, 1:2, 1:3, 1:4, 2:0, 2:1, 2:2, 2:3, 2:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # 3: 0:0, 0:1, 0:2, 0:3, 0:4, 3:0, 3:1, 3:2, 3:3, 3:4
        # のはず。(これが逆向きに(時間sortで古い物順に)返ってくる)
        target_user_name = self.user_node[3]['name']
        rv = self.app.get('/timeline/%s.json' % target_user_name)
        data = json.loads(rv.data)
        for user_index, tweet_index in reversed([
                (0, 0), (0, 1), (0, 2), (0, 3), (0, 4),
                (3, 0), (3, 1), (3, 2), (3, 3), (3, 4)
                ]):
            tweet_data = data.pop(0)
            answer_tweet = self.user_tweet[user_index][tweet_index]
            self.assertEqual(answer_tweet['text'], tweet_data['text'])
            self.assertEqual(answer_tweet._id, tweet_data['id'])
            
        
        
if __name__ == '__main__':
    assert StartNeo4J()
    unittest.main()
    assert StopNeo4J()

