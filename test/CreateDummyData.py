#!/usr/bin/python
# coding: UTF-8
# NECOMAtter のテスト

import sys
import os
import unittest
import subprocess
import shutil
import time
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from NECOMAtter import NECOMAtter
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


# ダミーデータを突っ込むためのテストケース
class NECOMAtter_CreateDummyData(unittest.TestCase):
    def setUp(self):
        # 全てのノードやリレーションシップを削除します
        gdb.clear()
        self.world = NECOMAtter("http://localhost:17474")
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
        self.user_node_list = []
        for user_name in ['iimura', 'hadoop team', u"NECOMAtter System", u"tarou", u"AAACorpRouter"]:
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
        tweet_node = self.Tweet("iimura", u"""Some signal on #ZEUS-DGA, I found similer signal on Agurim. Is it attack?  
--iframe[http//mawi.wide.ad.jp/members_only/aguri2/agurim/detail.html?&criteria=packet&duration=64800&endTimeStamp=2014-01-15]--""")
        self.Sleep(4)
        self.Tweet("NECOMAtter System", """node link summary:  
--iframe[/static/img/Neo4J.png]--""")
        self.Sleep(43)
        self.Reply("tarou", u"""@iimura Check it:  
--iframe[http//hadoop-master.sekiya-lab.info/matatabi/zeus-dga/query_count/?time.min=20140101&time.max=20141231]--""", tweet_node)
        self.Sleep(72)
        self.Tweet("iimura", u"""I create NECOMAtome    
http://necomatter.necoma-project.jp/matome/85""")
        self.Sleep(31)
        self.Tweet("iimura", u"""ok. mitigate it.  
#AAACorp-Request block from:  
f528764d624db129b32c21fbca0cb8d6.com  
gcqsjy2111ybiibq96yxixixduny7tdf6f94czn.com  
rotzfrech360grad24hnonstopshoutcastradio.net  
eef795a4eddaf1e7bd79212acc9dde16.net  
www.gan24ql0lf558kn66l376079sy9qxr6bs.org  

detail:
http://necomatter.necoma-project.jp/matome/85""")
        self.Sleep(5)
        self.Tweet("AAACorpRouter", u"""@iimura mitigated.  
block:

f528764d624db129b32c21fbca0cb8d6.com  
gcqsjy2111ybiibq96yxixixduny7tdf6f94czn.com  
rotzfrech360grad24hnonstopshoutcastradio.net  
eef795a4eddaf1e7bd79212acc9dde16.net  
www.gan24ql0lf558kn66l376079sy9qxr6bs.org""")


if __name__ == '__main__':
    assert StartNeo4J()
    unittest.main()
    assert StopNeo4J()






