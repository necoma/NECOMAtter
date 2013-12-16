#!/usr/bin/python
# coding: UTF-8

# ユーザにツイートさせるようなtwitterもどきの事をさせる時の
# DB を叩くフロントエンドクラスです


import logging
import time
import hashlib
import random
import re
from xml.sax.saxutils import *
from py2neo import neo4j, cypher


class NECOMATter():
    def __init__(self, url=None):
        if url is None:
            url = "http://localhost:7474"
        self.db_url = url
        self.gdb = neo4j.GraphDatabaseService(url + "/db/data/")
        self.UserIndex = None
        self.TweetIndex = None
        self.TagIndex = None
        self.APIKeyIndex = None
        self.SessionExpireSecond = 60*60*24*7
        # Cypher transactions are not supported by this server version
        # と言われたのでとりあえずの所はtransaction は封印します
        #self.CypherSession = cypher.Session(url)

    # HTML でXSSさせないようなエスケープをします。
    def EscapeForXSS(self, text):
        return escape(text, {'"': '&quot;'})

    # ユーザ用のインデックスを取得します
    def GetUserIndex(self):
        if self.UserIndex is None:
            self.UserIndex = self.gdb.get_or_create_index(neo4j.Node, "user")
        return self.UserIndex

    # tweet用のインデックスを取得します
    def GetTweetIndex(self):
        if self.TweetIndex is None:
            self.TweetIndex = self.gdb.get_or_create_index(neo4j.Node, "tweet")
        return self.TweetIndex

    # tag用のインデックスを取得します
    def GetTagIndex(self):
        if self.TagIndex is None:
            self.TagIndex = self.gdb.get_or_create_index(neo4j.Node, "tag")
        return self.TagIndex

    # API Key用のインデックスを取得します
    def GetAPIKeyIndex(self):
        if self.APIKeyIndex is None:
            self.APIKeyIndex = self.gdb.get_or_create_index(neo4j.Node, "api_key")
        return self.APIKeyIndex

    # tweet のクエリ結果からフォーマットされた辞書の配列にして返します
    def FormatTweet(self, tweet_list):
        if tweet_list is None:
            logging.warning("can not get tweet list from tag.")
            return []
        result_list = []
        for tweet in tweet_list:
            result_list.append({'text': tweet[0],
                "time": time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tweet[1])),
                "user_name": tweet[2],
                "unix_time": tweet[1],
                "id": tweet[3]._id})
        return result_list

    # ユーザのノードを取得します。
    # 何か問題があった場合はNone を返します。
    def GetUserNode(self, user_name):
        user_index = self.GetUserIndex()
        # 取得する
        user_list = user_index.get("name", user_name)
        if len(user_list) != 1:
            if len(user_list) == 0:
                return None
            else:
                logging.warning("user %s have multiple node: %s" % (user_name, str(user_list)))
                return None
        return user_list[0]

    # ユーザのAPIKeyノードを取得します。存在しなければ作成します
    # 何か問題があった場合はNone を返します。
    def CreateOrGetUserAPIKeyNode(self, key_name):
        api_index = self.GetAPIKeyIndex()
        # 取得する
        api_key_list = api_index.get("key", key_name)
        if len(api_key_list) == 0:
            api_node = api_index.create("key", key_name, {
                "key": key_name
            })
            return api_node
        if len(api_key_list) != 1:
            logging.warning("API key %s have multiple node: %s" % (key_name, str(user_list)))
            return None
        return api_key_list[0]

    # text からタグのような文字列を取り出してリストにして返します
    def GetTagListFromText(self, text):
        return re.findall(r"(#[^\s\r\n]+)", text)

    # tweet_node を、text から抽出したタグへと関連付けます
    def Tweet_LinkToTag(self, tweet_node, text):
        tag_list = self.GetTagListFromText(text)
        #tag_index = self.GetTagIndex()
        for tag in tag_list:
            tag_node = self.gdb.get_or_create_indexed_node("tag", "tag", tag, {"tag": tag})
            tweet_node.create_path("TAG", tag_node)

    # tweet_node をid から取得します
    def GetTweetNodeFromID(self, tweet_id):
        tweet_node = self.gdb.node(tweet_id)
        try:
            if 'text' not in tweet_node:
                return None
        except neo4j.ClientError:
            return None
        return tweet_node

    # ユーザにtweet させます。Tweetに成功したら、tweet_node を返します
    def Tweet(self, user_node, tweet_string, reply_to=None):
        if user_node is None:
            logging.error("Tweet owner is not defined.")
            return None
        tweet_index = self.GetTweetIndex()
        text = self.EscapeForXSS(tweet_string)
        reply_to_tweet_node = None
        if reply_to is not None:
            reply_to_tweet_node = self.GetTweetNodeFromID(reply_to)
            if reply_to_tweet_node is None:
                logging.error("ID %d tweet is not found." % reply_to)
                return None
        tweet_node = tweet_index.create("text", text, {
            "text": self.EscapeForXSS(tweet_string), 
            "time": time.time()
            })
        # user_node がtweet したということで、path をtweet_node から繋げます
        tweet_node.create_path("TWEET", user_node)
        # タグがあればそこに繋ぎます
        self.Tweet_LinkToTag(tweet_node, text)
        # 返事先のtweetがあるならば、リレーションシップを繋ぎます
        if reply_to_tweet_node is not None:
            tweet_node.create_path("REPLY", reply_to_tweet_node)
        return tweet_node

    # ユーザのtweet を取得して、{"text": 本文, "time": UnixTime} のリストとして返します
    def GetUserTweet(self, user_node, limit=None, since_time=None):
        if user_node is None:
            logging.error("User is undefined.")
            return []
        # ユーザのID を取得します
        user_id = user_node._id
        # クエリを作ります
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (tweet) -[:TWEET]-> (user) "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name, tweet "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # tweet_node を{"text": 本文, "time": 日付文字列, "user_name": ユーザ名} の形式の辞書にします
    def ConvertTweetNodeToHumanReadableDictionary(self, tweet_node):
        if tweet_node is None:
            logging.error("tweet_node is None")
            return None
        result_dic = {}
        result_dic['text'] = tweet_node['text']
        result_dic['time'] = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tweet_node['time']))
        return result_dic

    # ユーザのtweet を{"text": 本文, "time": 日付文字列}のリストにして返します
    def GetUserTweetFormated(self, user_name, limit=None, since_time=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return []
        tweet_list = self.GetUserTweet(user_node, limit=limit, since_time=since_time)
        return self.FormatTweet(tweet_list)

    # ユーザのタイムラインを取得します。
    # 取得されるのは text, time, user_name, tweet_node のリストです。
    def GetUserTimeline(self, user_node, limit=None, since_time=None):
        if user_node is None:
            logging.error("User is undefined.")
            return []
        user_id = user_node._id
        # クエリを作ります
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (tweet) -[:TWEET]-> (target) <-[:FOLLOW]- (user) "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, target.name, tweet "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # ユーザのタイムライン を{"text": 本文, "time": 日付文字列, "user_name": ユーザ名}のリストにして返します
    def GetUserTimelineFormated(self, user_name, limit=None, since_time=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return []
        tweet_list = self.GetUserTimeline(user_node, limit, since_time)
        return self.FormatTweet(tweet_list)

    # ユーザ名とセッションキーから、そのセッションが有効かどうかを判定します。
    def CheckUserSessionKeyIsValid(self, user_name, session_key):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return False
        if session_key != user_node['session_key'] or session_key is None:
            logging.warning("User %s session_key is not same." % user_name)
            return False
        expire_time = user_node['session_expire_time']
        now_time = time.time()
        if expire_time < now_time:
            logging.info("session expired. %f > %f" % (expire_time, now_time))
            return False
        return True

    # ユーザセッションを新規作成して返します
    def UpdateUserSessionKey(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return None
        # 怪しくセッションキー文字列を生成します
        session_key = self.GetPasswordHash(user_name,
            str(time.time() + random.randint(0, 100000000)))
        user_node['session_key'] = session_key
        user_node['session_expire_time'] = time.time() + self.SessionExpireSecond
        return session_key

    # DBに登録されるパスワードのハッシュ値を取得します
    def GetPasswordHash(self, user_name, password):
        if isinstance(user_name, unicode):
            user_name = user_name.encode('utf-8')
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        return hashlib.sha256("%s/%s" % (password, user_name)).hexdigest()

    # ユーザのパスワードを確認します
    def CheckUserPasswordIsValid(self, user_name, password):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return False
        if self.GetPasswordHash(user_name, password) != user_node['password_hash']:
            return False
        return True

    # ユーザのパスワードを更新します
    def UpdateUserPassword(self, user_name, old_password, new_password):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return False
        if not self.CheckUserPasswordIsValid(user_name, old_password):
            logging.warning("User %s password authenticate failed." % user_name)
            return False
        user_node['password_hash'] = self.GetPasswordHash(user_name, new_password)
        user_node['session_expire_time'] = 0.0
        return True

    # ユーザを登録します
    def AddUser(self, user_name, password):
        # ユーザ名はいちいちエスケープするのがめんどくさいので
        # 登録時にエスケープされないことを確認するだけにします(いいのかなぁ)
        escaped_user_name = self.EscapeForXSS(user_name)
        if escaped_user_name != user_name:
            logging.error("User %s has escape string. please user other name" % user_name)
            return False
        user_node = self.GetUserNode(user_name)
        if user_node is not None:
            logging.warning("User %s is already registerd." % user_name)
            return False
        user_index = self.GetUserIndex()
        hash_value = self.GetPasswordHash(user_name, password)
        user_node = user_index.create("name", user_name, {
            "name": user_name, "password_hash": hash_value
        })
        # 自分をフォローしていないと自分のタイムラインに自分が出ません
        self.FollowUserByNode(user_node, user_node)
        return True

    # ユーザを削除します
    def DelUser(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.info("User %s is not registered." % user_name)
            return False
        user_id = user_node._id
        # このユーザに纏わるリレーションシップを全部消します
        # トランザクションではできないのかなぁ……
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH () <-[r:FOLLOW]- (user) "
        query += "DELETE r " # フォローを外します(消えるユーザ→他のユーザ)
        result_list, metadata = cypher.execute(self.gdb, query)
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (user) <-[r:FOLLOW]- () "
        query += "DELETE r " # フォローを外します(他のユーザ→消えるユーザ)
        result_list, metadata = cypher.execute(self.gdb, query)
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (user) <-[r:TWEET]- () "
        query += "DELETE r " # tweeet については残しておきます(ただ、tweetを辿ることができなくなるはずです)
        result_list, metadata = cypher.execute(self.gdb, query)
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (user) <-[r:API_KEY]- (api_key) "
        query += "DELETE r, api_key " # API_KEY はリレーションシップとAPI_KEYそのものの両方を消します
        result_list, metadata = cypher.execute(self.gdb, query)
        user_node.delete()
        return True

    # follower がtarget をフォローしているかどうかを確認します
    def IsFollowed(self, follower_user_node, target_user_node):
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        result = self.gdb.match(start_node=follower_user_node,
                rel_type="FOLLOW",
                end_node=target_user_node)
        if result is None:
            logging.error("fatal error. match() return None.")
            return False
        is_followed = False
        for obj in result:
            is_followed = True
        return is_followed

    # ユーザをフォローします
    def FollowUserByNode(self, follower_user_node, target_user_node):
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        if self.IsFollowed(follower_user_node, target_user_node):
            logging.warning("already followed.")
            return False
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        relationship = self.gdb.create((follower_user_node, "FOLLOW", target_user_node))
        if relationship is None:
            return False
        return True

    # ユーザをフォローします
    def FollowUserByName(self, follower_user_name, target_user_name):
        follower_user_node = self.GetUserNode(follower_user_name)
        target_user_node = self.GetUserNode(target_user_name)
        return self.FollowUserByNode(follower_user_node, target_user_node)

    # ユーザをフォローしていたらフォローを外します
    def UnFollowUserByNode(self, follower_user_node, target_user_node):
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        result = self.gdb.match(start_node=follower_user_node, rel_type="FOLLOW", end_node=target_user_node)
        if result is None:
            logging.error("fatal error. match() return None.")
            return False
        unfollow_num = 0
        for relationship in result:
            self.gdb.delete(relationship)
            unfollow_num += 1
        if unfollow_num == 0:
            logging.error("unfollow num is 0. you are no followed.")
            return False
        return True

    # ユーザをフォローしていたらフォローを外します
    def UnFollowUserByName(self, follower_user_name, target_user_name):
        follower_user_node = self.GetUserNode(follower_user_name)
        target_user_node = self.GetUserNode(target_user_name)
        return self.UnFollowUserByNode(follower_user_node, target_user_node)

    # ユーザ名のリストを取得します
    def GetUserNameList(self):
        user_index = self.gdb.get_or_create_index(neo4j.Node, "user")
        query_result = user_index.query("name:*")
        user_name_list = []
        for user_node in query_result:
            if "name" in user_node:
                user_name_list.append(user_node["name"])
        return user_name_list

    # 対象のユーザがフォローしているユーザ名のリストを取得します
    def GetUserFollowedUserNameList(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("user %s is not registered." % user_name)
            return []
        user_id = user_node._id
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (target) <-[:FOLLOW]- (user) "
        query += "RETURN target.name "
        result_list, metadata = cypher.execute(self.gdb, query)
        followed_user_name_list = []
        for name in result_list:
            followed_user_name_list.append(name[0])
        return followed_user_name_list

    # tweetのノードIDから対象のユーザのtweet を取得します。
    def GetTweetFromID(self, tweet_id):
        result_list = []
        try:
            query = ""
            query += "start tweet = node(%d) " % tweet_id
            query += "MATCH (user) <-[:TWEET]- (tweet) "
            query += "RETURN tweet.text, tweet.time, user.name, tweet "
            result_list, metadata = cypher.execute(self.gdb, query)
        except neo4j.CypherError:
            return []
        return result_list

    # tag からtweet を取得します
    def GetTagTweet(self, tag_string, limit=None, since_time=None):
        query = ""
        query += "start tag_node=node:tag(tag=\"%s\") " % tag_string.replace('"', '_')
        query += "MATCH (user) <-[:TWEET]- (tweet) -[:TAG]-> tag_node " 
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name, tweet "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # tag から取得したtweet を{"text": 本文, "time": 日付文字列}のリストにして返します
    def GetTagTweetFormated(self, tag_name, limit=None, since_time=None):
        tweet_list = self.GetTagTweet(tag_name, limit=limit, since_time=since_time)
        return self.FormatTweet(tweet_list)

    # tag のリストを取得します
    def GetTagList(self, limit=None, since_time=None):
        query = ""
        query += "start tag_node=node(*) "
        query += "MATCH () -[:TAG]-> tag_node "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tag_node.tag, count(*) as count "
        query += "ORDER BY count DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        tag_list = []
        for result in result_list:
            if len(result) > 0:
                tag_list.append(result[0])
        return tag_list

    # ユーザのAPIキーのリストを取得します(ノード指定版)
    def GetUserAPIKeyListByNode(self, user_node):
        if user_node is None:
            logging.error("user_node is None")
            return None
        user_id = user_node._id
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (key) -[:API_KEY]-> (user) "
        query += "RETURN key.key "
        query += "ORDER BY key.time DESC "
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # ユーザのAPIキーのリストを取得します(名前指定版)
    def GetUserAPIKeyListByName(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("user %s is not registerd" % user_name)
            return []
        key_list = self.GetUserAPIKeyListByNode(user_node)
        if key_list is None:
            logging.error("query failed.")
            return []
        result_list = []
        for key in key_list:
            result_list.append(key[0])
        return result_list

    # ユーザがAPIキーを持っているかどうかを確認します
    def CheckUserAPIKeyByName(self, user_name, key_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("user %s is not registerd" % user_name)
            return False
        escaped_key_name = key_name.replace('"', '_')
        if escaped_key_name != key_name:
            logging.error("key_name has escape charactor")
            return False
        user_id = user_node._id
        query = ""
        query += "START user=node(%d) " % user_id
        query += "MATCH ( key_node ) -[:API_KEY]-> user "# % key_name
        query += "WHERE key_node.key = '%s' " % key_name
        query += "RETURN key_node "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) != 1:
            return False
        return True

    # ユーザのAPIキーを削除します
    def DeleteUserAPIKeyByName(self, user_name, key_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("user %s is not registerd" % user_name)
            return False
        escaped_key_name = key_name.replace('"', '_')
        if escaped_key_name != key_name:
            logging.error("key_name has escape charactor")
            return False
        user_id = user_node._id
        query = ""
        query += "START user=node(%d) " % user_id
        query += "MATCH ( key_node ) -[r :API_KEY]-> (user) " #% key_name
        query += "WHERE key_node.key = '%s' " % key_name
        query += "DELETE key_node, r" # ノードをdeleteするときは node と リレーションシップを両方deleteする必要があるっぽい
        result_list, metadata = cypher.execute(self.gdb, query)
        # 失敗した時にはちゃんとlistが複数になるの？
        if len(result_list) != 0:
            return False
        return True

    # ユーザにAPIキーを追加します
    def CreateUserAPIKeyByName(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("user %s is not registerd" % user_name)
            return None
        # 怪しくAPIキーを生成します
        key = self.GetPasswordHash(user_name,
            str(time.time() + random.randint(0, 100000000)))
        key_node = self.CreateOrGetUserAPIKeyNode(key)
        key_node['time'] = time.time()
        relationship = self.gdb.create((key_node, "API_KEY", user_node))
        if relationship is None:
            self.gdb.delete(key_node)
            return None
        return key_node

    # 一つのtweetが返事をした親tweetを最上位の親まで辿って取り出します(元のtweetは含まれません)
    def GetParentTweetAboutTweetID(self, tweet_id, limit=None, since_time=None):
        query = ""
        query += "START original_tweet=node(%d) " % tweet_id
        query += "MATCH original_tweet -[:REPLY*1..]-> tweet "
        query += "WITH original_tweet, tweet "
        query += "MATCH tweet -[:TWEET]-> user "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name, tweet "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list[::-1]

    # 一つのtweetについた返事のtweetを、最後の子まで辿って取り出します(元のtweetは含まれません)
    def GetChlidTweetAboutTweetID(self, tweet_id, limit=None, since_time=None):
        query = ""
        query += "START original_tweet=node(%d) " % tweet_id
        query += "MATCH original_tweet <-[:REPLY*1..]- tweet "
        query += "WITH original_tweet, tweet "
        query += "MATCH tweet -[:TWEET]-> user "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name, tweet "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list[::-1]

    # 一つのtweetが返事をした親tweetを最上位の親まで辿って取り出します(フォーマット済み版)
    def GetParentTweetAboutTweetIDFormatted(self, tweet_id, limit=None, since_time=None):
        tweet_list = self.GetParentTweetAboutTweetID(tweet_id, limit, since_time)
        return self.FormatTweet(tweet_list)

    # 一つのtweetについた返事のtweetを、最後の子まで辿って取り出します(フォーマット済み版)
    def GetChildTweetAboutTweetIDFormatted(self, tweet_id, limit=None, since_time=None):
        tweet_list = self.GetChlidTweetAboutTweetID(tweet_id, limit, since_time)
        return self.FormatTweet(tweet_list)

    # 一つのtweet をTweetID から取り出します
    def GetTweetNodeFromIDFormatted(self, tweet_id):
        return self.FormatTweet(self.GetTweetFromID(tweet_id))

