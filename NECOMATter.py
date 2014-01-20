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
        self.ListIndex = None
        self.SessionExpireSecond = 60*60*24*7
        # Cypher transactions are not supported by this server version
        # と言われたのでとりあえずの所はtransaction は封印します
        #self.CypherSession = cypher.Session(url)

    # HTML でXSSさせないようなエスケープをします。
    def EscapeForXSS(self, text):
        return escape(text, {'"': '&quot;'})

    # text がCypher で文字列として入れた時に問題無いことを確認します
    def VaridateCypherString(self, text):
        escaped_text = self.EscapeForXSS(text)
        return escaped_text == text

    # 何かあとで使いそうな文字に関しては使えないことにします
    def VaridateUserNameString(self, text):
        escaped_text = re.sub(r'[#@*&]', '_', text)
        return escaped_text == text

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

    # List用のインデックスを取得します
    def GetListIndex(self):
        if self.ListIndex is None:
            self.ListIndex = self.gdb.get_or_create_index(neo4j.Node, "list")
        return self.ListIndex

    # time.time() で得られたエポックからの時間をフォーマットします
    def FormatTime(self, time_epoc):
        return time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(time_epoc))

    # user_node に設定されている icon_url を取り出します。存在しなければdefault値を返します
    def GetUserAbaterIconURL(self, user_node):
        icon_url = "/static/img/footprint3.2.png"
        if 'icon_url' in user_node:
            icon_url = user_node['icon_url']
        return icon_url

    # tweet のクエリ結果からフォーマットされた辞書の配列にして返します
    def FormatTweet(self, tweet_list):
        if tweet_list is None:
            logging.warning("can not get tweet list from tag.")
            return []
        result_list = []
        for tweet in tweet_list:
            text = tweet[0]
            unix_time = tweet[1]
            tweet_owner_name = tweet[2]
            tweet_id = tweet[4]._id
            own_stard = True if tweet[5] is not None else False
            own_retweeted = True if tweet[6] is not None else False
            icon_url = "/static/img/footprint3.2.png"
            if tweet[3] is not None:
                icon_url = tweet[3]
            is_retweet = False
            if len(tweet) >= 8 and tweet[7] is not None and tweet[7].type == "RETWEET":
                is_retweet = True
            retweet_user_name = None
            if len(tweet) >= 9 and tweet[8] is not None:
                retweet_user_name = tweet[8]
            if is_retweet == False: # retweet されていない場合でもretweet_node_name が存在するようなクエリになっているのでここで回避します
                retweet_user_name = None
            retweet_unix_time = None
            retweet_time = None
            if len(tweet) >= 10 and tweet[9] is not None:
                retweet_unix_time = tweet[9]
                retweet_time = self.FormatTime(retweet_unix_time)
            result_list.append({'text': text
                , "time": self.FormatTime(unix_time)
                , "user_name": tweet_owner_name
                , "unix_time": unix_time
                , "icon_url": icon_url
                , "id": tweet_id
                , "own_stard": own_stard
                , "own_retweeted": own_retweeted
                , "is_retweet": is_retweet
                , "retweet_user_name": retweet_user_name
                , "retweet_time": retweet_time
                , "retweet_unix_time": retweet_unix_time
                })
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
        creation_time = time.time()
        tweet_node = tweet_index.create("text", text, {
            "text": self.EscapeForXSS(tweet_string), 
            "time": creation_time
            })
        # user_node がtweet したということで、path をtweet_node から繋げます
        tweet_node.create_path(("TWEET", {
                "time": creation_time
            }), user_node)
        # タグがあればそこに繋ぎます
        self.Tweet_LinkToTag(tweet_node, text)
        # 返事先のtweetがあるならば、リレーションシップを繋ぎます
        if reply_to_tweet_node is not None:
            tweet_node.create_path(("REPLY", {
                "time": creation_time
            }), reply_to_tweet_node)
        return tweet_node

    # ユーザにtweetさせます。(名前指定版) Tweet に成功したら、一つのtweet辞書を返します
    def TweetByName(self, user_name, tweet_string, reply_to=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return {}
        tweet_node = self.Tweet(user_node, tweet_string, reply_to)
        if tweet_node is None:
            logging.error("tweet failed.")
            return {}
        icon_url = self.GetUserAbaterIconURL(user_node)
        return {'user_name': user_name
                , 'id': tweet_node._id
                , 'text': tweet_node['text']
                , 'time': self.FormatTime(tweet_node['time'])
                , "unix_time": tweet_node['time']
                , "icon_url": icon_url
                , "own_stard": False
                , "own_retweeted": False
                , "is_retweet": False
                , "retweet_user_name": None
                , "retweet_time": None
                , "retweet_unix_time": None
                }

    # ユーザのtweet を取得して、{"text": 本文, "time": UnixTime} のリストとして返します
    def GetUserTweet(self, user_node, limit=None, since_time=None, query_user_node=None):
        if user_node is None:
            logging.error("User is undefined.")
            return []
        # ユーザのID を取得します
        user_id = user_node._id
        query_user_id = 0
        if query_user_node is not None:
            query_user_id = query_user_node._id
        # クエリを作ります
        query = ""
        query += "START user = node(%d) " % user_id
        if query_user_node is not None:
            query += ", query_user = node(%d) " % query_user_id
        query += "MATCH (tweet) -[tweet_r:TWEET|RETWEET]-> (user) "
        query += ", tweet -[?:TWEET]-> (tweet_user) "
        if query_user_node is not None:
            query += ", tweet <-[my_star_r?:STAR]- (query_user) "
            query += ", tweet -[my_retweet_r?:RETWEET]-> (query_user) "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, tweet_user.name?, tweet_user.icon_url?, tweet"
        if query_user_node is not None:
            query += ", my_star_r, my_retweet_r, tweet_r "
        else:
            query += ", null, null, null"
        query += ", user.name, tweet_r.time? "
        query += "ORDER BY tweet_r.time? DESC, tweet.time DESC "
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
        result_dic['time'] = self.FormatTime(tweet_node['time'])
        return result_dic

    # ユーザのtweet を{"text": 本文, "time": 日付文字列}のリストにして返します
    def GetUserTweetFormated(self, user_name, limit=None, since_time=None, query_user_name=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return []
        query_user_node = None
        if query_user_name is not None:
            query_user_node = self.GetUserNode(query_user_name)
        tweet_list = self.GetUserTweet(user_node, limit=limit, since_time=since_time, query_user_node=query_user_node)
        return self.FormatTweet(tweet_list)

    # ユーザのタイムラインを取得します。
    # 取得されるのは text, time, user_name, tweet_node のリストです。
    def GetUserTimeline(self, user_node, limit=None, since_time=None, query_user_node=None):
        if user_node is None:
            logging.error("User is undefined.")
            return []
        user_id = user_node._id
        # クエリを作ります
        query = ""
        query += "START user = node(%d) " % user_id
        if query_user_node is not None:
            query += ", query_user = node(%d) " % query_user_node._id
        query += "MATCH (tweet) -[tweet_r:TWEET|RETWEET]-> (target) <-[:FOLLOW]- (user) "
        query += ", tweet -[?:TWEET]-> (tweet_user) "
        if query_user_node is not None:
            query += ", tweet <-[my_star_r?:STAR]- (query_user) "
            query += ", tweet -[my_retweet_r?:RETWEET]-> (query_user) "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, tweet_user.name?, tweet_user.icon_url?, tweet "
        if query_user_node is not None:
            query += ", my_star_r, my_retweet_r, tweet_r "
        else:
            query += ", null, null, null "
        query += ", target.name?, tweet_r.time? "
        query += "ORDER BY tweet_r.time? DESC, tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # ユーザのタイムライン を{"text": 本文, "time": 日付文字列, "user_name": ユーザ名}のリストにして返します
    def GetUserTimelineFormated(self, user_name, limit=None, since_time=None, query_user_name=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return []
        query_user_node = None
        if query_user_name is not None:
            query_user_node = self.GetUserNode(query_user_name)
        tweet_list = self.GetUserTimeline(user_node, limit, since_time, query_user_node=query_user_node)
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
        if self.VaridateCypherString(user_name) == False:
            logging.error("User %s has escape string. please use other name" % user_name)
            return False
        if self.VaridateUserNameString(user_name) == False:
            logging.error("User %s has permitted character. please use other name" % user_name)
            return False
        user_node = self.GetUserNode(user_name)
        if user_node is not None:
            logging.warning("User %s is already registerd." % user_name)
            return False
        user_index = self.GetUserIndex()
        hash_value = self.GetPasswordHash(user_name, password)
        # 初期のアバターアイコンは肉球アイコンからランダムで設定します
        icon_url = "/static/img/footprint3.%d.png" % (random.randint(1, 5), )
        user_node = user_index.create("name", user_name, {
            "name": user_name, "password_hash": hash_value,
            "icon_url": icon_url
        })
        # 自分をフォローしていないと自分のタイムラインに自分が出ません
        self.FollowUserByNode(user_node, user_node)
        return True

    # ユーザを削除します
    def DeleteUser(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.info("User %s is not registered." % user_name)
            return False
        user_id = user_node._id
        # このユーザに纏わるリレーションシップを全部消します
        # トランザクションではできないのかなぁ……

        # リストについてはリスト自体も消すので先に(user_nodeが消えないうちに)消します
        self.DeleteAllListByNode(user_node)
        # API_KEY についてはノードもいらなくなるので消します
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (user) <-[r:API_KEY]- (api_key) "
        query += "DELETE r, api_key "
        result_list, metadata = cypher.execute(self.gdb, query)
        # TODO: tweet_node については消しません。
        # WARN: そのため、オーナーが居ないtweet_nodeになり得ます
        # その他全てのリレーションシップとuser_nodeを消します
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH () -[r]- (user) "
        query += "DELETE r, user "
        result_list, metadata = cypher.execute(self.gdb, query)
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
        relationship[0]['time'] = time.time()
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
    def GetTweetFromID(self, tweet_id, user_node=None):
        result_list = []
        try:
            query = ""
            query += "start tweet = node(%d) " % tweet_id
            if user_node is not None:
                query += ", query_user = node(%d) " % user_node._id
            query += "MATCH (user) <-[?:TWEET]- (tweet) "
            if user_node is not None:
                query += ", tweet <-[star_r?:STAR]- query_user "
                query += ", tweet -[retweet_r?:RETWEET]-> query_user "
            query += "RETURN tweet.text, tweet.time, user.name?"
            query += ", user.icon_url?, tweet "
            if user_node is not None:
                query += ", star_r, retweet_r"
            else:
                query += ", null, null "
            query += ", null, null "
            result_list, metadata = cypher.execute(self.gdb, query)
        except neo4j.CypherError:
            return []
        return result_list

    # tag からtweet を取得します
    def GetTagTweet(self, tag_string, limit=None, since_time=None, user_node=None):
        query = ""
        query += "start tag_node=node:tag(tag=\"%s\") " % tag_string.replace('"', '_')
        if user_node is not None:
            query += ", query_user = node(%d) " % user_node._id
        query += "MATCH (user) <-[?:TWEET]- (tweet) "
        query += ", (tweet) -[:TAG]-> tag_node " 
        if user_node is not None:
            query += ", tweet <-[star_r?:STAR]- query_user "
            query += ", tweet -[retweet_r?:RETWEET]-> query_user "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name?, user.icon_url?, tweet "
        if user_node is not None:
            query += ", star_r, retweet_r"
        else:
            query += ", null, null "
        query += ", null, null "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # tag から取得したtweet を{"text": 本文, "time": 日付文字列}のリストにして返します
    def GetTagTweetFormated(self, tag_name, limit=None, since_time=None, query_user_name=None):
        user_node = None
        if query_user_name is not None:
            user_node = self.GetUserNode(query_user_name)
        tweet_list = self.GetTagTweet(tag_name, limit=limit, since_time=since_time, user_node=user_node)
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
    def GetParentTweetAboutTweetID(self, tweet_id, limit=None, since_time=None, user_node=None):
        query = ""
        query += "START original_tweet=node(%d) " % tweet_id
        if user_node is not None:
            query += ", query_user = node(%d) " % user_node._id
        query += "MATCH original_tweet -[:REPLY*1..]-> tweet "
        query += "WITH original_tweet, tweet "
        query += "MATCH tweet -[?:TWEET]-> user "
        if user_node is not None:
            query += ", tweet <-[star_r?:STAR]- query_user "
            query += ", tweet -[retweet_r?:RETWEET]-> query_user "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name?, user.icon_url?, tweet "
        if user_node is not None:
            query += ", star_r, retweet_r"
        else:
            query += ", null, null "
        query += ", null, null "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list[::-1]

    # 一つのtweetについた返事のtweetを、最後の子まで辿って取り出します(元のtweetは含まれません)
    def GetChlidTweetAboutTweetID(self, tweet_id, limit=None, since_time=None, user_node=None):
        query = ""
        query += "START original_tweet=node(%d) " % tweet_id
        if user_node is not None:
            query += ", query_user = node(%d) " % user_node._id
        query += "MATCH original_tweet <-[:REPLY*1..]- tweet "
        query += "WITH original_tweet, tweet "
        query += "MATCH tweet -[?:TWEET]-> user "
        if user_node is not None:
            query += ", tweet <-[star_r?:STAR]- query_user "
            query += ", tweet -[retweet_r?:RETWEET]-> query_user "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name?, user.icon_url?, tweet "
        if user_node is not None:
            query += ", star_r, retweet_r"
        else:
            query += ", null, null "
        query += ", null, null "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list[::-1]

    # 一つのtweetが返事をした親tweetを最上位の親まで辿って取り出します(フォーマット済み版)
    def GetParentTweetAboutTweetIDFormatted(self, tweet_id, limit=None, since_time=None, query_user_name=None):
        user_node = None
        if query_user_name is not None:
            user_node = self.GetUserNode(query_user_name)
        tweet_list = []
        try:
            tweet_list = self.GetParentTweetAboutTweetID(tweet_id, limit, since_time, user_node=user_node)
        except neo4j.CypherError:
            return [] 
        return self.FormatTweet(tweet_list)

    # 一つのtweetについた返事のtweetを、最後の子まで辿って取り出します(フォーマット済み版)
    def GetChildTweetAboutTweetIDFormatted(self, tweet_id, limit=None, since_time=None, query_user_name=None):
        user_node = None
        if query_user_name is not None:
            user_node = self.GetUserNode(query_user_name)
        tweet_list = []
        try:
            tweet_list = self.GetChlidTweetAboutTweetID(tweet_id, limit, since_time, user_node=user_node)
        except neo4j.CypherError:
            return [] 
        return self.FormatTweet(tweet_list)

    # 一つのtweet をTweetID から取り出します
    def GetTweetNodeFromIDFormatted(self, tweet_id, query_user_name=None):
        user_node = None
        if query_user_name is not None:
            user_node = self.GetUserNode(query_user_name)
        return self.FormatTweet(self.GetTweetFromID(tweet_id, user_node=user_node))

    # list 機能の実装時メモ
    #
    # list は単にfollowをしているnodeを作る事によって表される。
    # follow しているだけのnode 。name はリストの名前になる
    #
    # (user) -[:LIST]->(follow_node) -[:FOLLOW]-> (other_user)
    #
    # という関係になる。
    # 
    # 最初は -[:FOLLOW]-> のrelationship にattribute として
    # リストの名前を入れたらどうかと思ったけれどそうすると
    # 複数のリストから同じユーザにフォローのrelationshipが張れないので諦めた。

    # owner_node(node) のlist_name(string) 用のノードを取得します
    # なければ作って返します。
    # それでも失敗した場合はNoneを返します。
    def CreateOrGetListNodeFromName(self, owner_node, list_name, description="", hidden=False):
        if owner_node is None:
            return None
        if self.VaridateCypherString(list_name) == False:
            logging.error("list name %s has escape string. please user other name" % list_name)
            return None
        # とりあえずクエリして存在確認をします。
        owner_node_id = owner_node._id
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH list_node -[:OWNER]-> list_owner_node "
        query += ", list_node <-[:LIST]- owner_node "
        query += "WHERE list_owner_node = owner_node "
        query += "AND list_node.name = \"%s\"" % list_name
        query += "RETURN list_node "
        result_list, metadata = cypher.execute(self.gdb, query)
        # 既にある場合はそれを返します
        if len(result_list) == 1:
            return result_list[0][0]

        # TODO: ここでlockしていないので同時に呼び出されると
        # 複数作られる可能性があります。
        # できれば lock して対応するのがいい気がします。

        # 存在しないようなので新しく作ります
        list_index = self.GetListIndex()
        list_node = list_index.create("list", list_name, {
            "name": list_name,          # リストの名前
            "time": time.time(),        # リストの作成された時間
            "description": description, # リストの説明
            "hidden": hidden            # 非公開リストか否か
        })
        if list_node is None:
            logging.error("list_node create error")
            return None
        relationship = self.gdb.create((owner_node, "LIST", list_node))
        if relationship is None:
            logging.error("owner_node --> list_node relation create error")
            list_node.delete()
            return None
        owner_relationship = self.gdb.create((list_node, "OWNER", owner_node))
        if owner_relationship is None:
            logging.error("list_node -[:OWNER]-> owner_node relation create error")
            relationship.remove()
            list_node.delete()
            return None

        # lockせずに作成しているので、
        # 重複して作成したことを考えて、id の一番小さいものを正規のものとするために、
        # 再度検索します
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) > 1:
            candidate_node = list_node
            my_node_id = list_node._id
            min_node_id = my_node_id
            for node in result_list:
                if node._id < min_node_id:
                    min_node_id = node._id
                    candidate_node = node
            if min_node_id < my_node_id:
                # 自分よりid の小さいものがあったので、自分のノードは削除します
                relationship.remove()
                owner_relationship.remove()
                list_node.delete()
                list_node = candidate_node
        return list_node

    # owner_node のlist_node について、フォローしている他のユーザのフォローを外します
    # (主にlistが非公開リストになったときの対応です)
    def DeleteListFollowedUsers(self, owner_node, list_node):
        if owner_node is None or list_node is None:
            return False
        owner_node_id = owner_node._id
        list_node_id = list_node._id
        query = ""
        query += "START owner_node=node(%d), list_node=node(%d) " % (owner_node_id, list_node_id)
        query += "MATCH list_node <-[list_r:LIST]- node "
        query += "WHERE node != owner_node "
        query += "DELETE list_r "
        result_list, metadata = cypher.execute(self.gdb, query)
        return True

    # owner_node のlist_name のリストについて、属性を変化させます
    def UpdateListAttribute(self, owner_node, list_name, description="", hidden=False):
        list_node = self.CreateOrGetListNodeFromName(owner_node, list_name, description=description, hidden=hidden)
        if list_node is None:
            logging.error("list_node get or create failed.")
            return False
        if list_node['description'] != description:
            list_node['description'] = description
        if list_node['hidden'] != hidden:
            list_node['hidden'] = hidden
            if hidden:
                # 後から隠し属性になったので、
                # フォローしている他のユーザからのフォローを外します
                return self.DeleteListFollowedUsers(owner_node, list_node)
        return True

    # owner_node(node) のlist_name(string) を作成します
    def CreateListByNode(self, owner_node, list_name, description="", hiddin=False):
        list_node = self.CreateOrGetListNodeFromName(owner_node, list_name, description, hidden)
        if list_node is None:
            return None
        list_node['description'] = description
        list_node['hidden'] = hidden
        return list_node

    # owner_node(node) のlist_name(string) を作成します(名前指定版)
    def CreateListByName(self, owner_node, list_name, description="", hiddin=False):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("owner_name '%s' is not registerd." % owner_name)
            return None
        return self.CreateListByNode(owner_node, list_name, description, hidden)

    # owner_node(node) のlist_name(string)に、target_node(node) を追加します。
    # 成否(True/False)を返します
    def AddNodeToListByNode(self, owner_node, list_name, target_node):
        if owner_node is None or target_node is None:
            logging.error("owner_node or target_node is None")
            return False
        if list_name == "":
            logging.error("list_name is null")
            return False
        if self.VaridateCypherString(list_name) == False:
            logging.error("list name '%s' has escape string. please user other name" % list_name)
            return False
        # list用のノードを取得します
        list_node = self.CreateOrGetListNodeFromName(owner_node, list_name)
        if list_node is None:
            logging.error("list_node create failed.")
            return False
        # list用のノードからFOLLOWリレーションシップを張ります
        return self.FollowUserByNode(list_node, target_node)

    # owner_name のユーザのlist_nameに、target_nameのユーザを追加します
    def AddNodeToListByName(self, owner_name, list_name, target_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("owner_name '%s' is not registerd." % owner_name)
            return False
        target_node = self.GetUserNode(target_name)
        if target_node is None:
            logging.error("target_name '%s' is not registerd." % target_name)
            return False
        return self.AddNodeToListByNode(owner_node, list_name, target_node)

    # owner_node のlistを全て削除します
    def DeleteAllListByNode(self, owner_node):
        if owner_node is None:
            return False
        owner_node_id = owner_node._id
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH () <-[follow_r:FOLLOW]- list_node <-[:LIST]- owner_node "
        query += ", list_node <-[list_follow_r:LIST]- () "
        query += ", list_node -[owner_r:OWNER]-> list_owner_node "
        query += "WHERE list_owner_node = owner_node "
        query += "DELETE follow_r, owner_r, list_follow_r, follow_r, list_node "
        result_list, metadata = cypher.execute(self.gdb, query)
        return True

    # owner_node のlistの一つを削除します
    def DeleteListByNode(self, owner_node, list_name):
        if owner_node is None:
            return False
        owner_node_id = owner_node._id
        if self.VaridateCypherString(list_name) == False:
            logging.error("list name '%s' has escape string. please user other name" % list_name)
            return False
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH () <-[follow_r:FOLLOW]- list_node <-[:LIST]- owner_node "
        query += ", list_node <-[list_follow_r:LIST]- () "
        query += ", list_node -[owner_r:OWNER]-> list_owner_node "
        query += "WHERE list_owner_node = owner_node "
        query += "AND list_node.name = \"%s\" " % list_name
        query += "DELETE follow_r, owner_r, list_follow_r, follow_r, list_node "
        result_list, metadata = cypher.execute(self.gdb, query)
        return True

    # owner_node のlist_name のノードを取得します
    def GetListNodeByNode(self, owner_node, list_name):
        if owner_node is None:
            return None
        owner_node_id = owner_node._id
        if self.VaridateCypherString(list_name) == False:
            logging.error("list name '%s' has escape string. please user other name" % list_name)
            return None
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH list_node <-[list_r:LIST]- owner_node "
        query += ", list_node -[:OWNER]-> list_owner_node "
        query += "WHERE list_owner_node = owner_node "
        query += "AND list_node.name = \"%s\" " % list_name
        query += "RETURN list_node "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) != 1:
            logging.error("list name '%s' not found." % list_name)
            return None
        return result_list[0][0]

    # owner_node のlistを削除します(名前版)
    def DeleteListByName(self, owner_node_name, list_name):
        owner_node = self.GetUserNode(owner_node_name)
        if owner_node is None:
            logging.error("owner_name '%s' is not registerd." % owner_name)
            return False
        return self.DeleteListByNode(owner_node, list_name)

    # owner_node の保持しているlistのリストを返します(owner_nodeのものだけを返します)
    def GetUserOwnedListListByNode(self, owner_node):
        if owner_node is None:
            return None
        owner_node_id = owner_node._id
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH list_node <-[:LIST]- owner_node "
        query += ", list_node -[:OWNER]-> list_owner_node "
        query += "WHERE list_owner_node = owner_node " # owner_node のものだけをリストします
        query += "RETURN list_node.name, list_node.time, list_owner_node.name, list_node "
        query += "ORDER BY list_node.time ASC "
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # list のクエリ結果からフォーマットされた辞書の配列にして返します
    def FormatList(self, list_list):
        if list_list is None:
            logging.warning("can not get list list")
            return []
        result_list = []
        for list in list_list:
            result_list.append({'name': list[0],
                "time": self.FormatTime(list[1]),
                "owner_name": list[2],
                "unix_time": list[1],
                "id": list[3]._id})
        return result_list

    # owner_node のlistのリストを返します(名前版)(owner_nodeのものだけを返します)
    def GetUserOwnedListListFormated(self, owner_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("owner_name %s is not registerd." % owner_name)
            return []
        return self.FormatList(self.GetUserOwnedListListByNode(owner_node))

    # owner_node のフォローしているlistのリストを返します(他のユーザのものも含みます)
    def GetUserListListByNode(self, owner_node):
        if owner_node is None:
            return None
        owner_node_id = owner_node._id
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH list_node <-[:LIST]- owner_node "
        query += ", list_node -[:OWNER]-> list_owner_node "
        query += "RETURN list_node.name, list_node.time, list_owner_node.name, list_node "
        query += "ORDER BY list_node.time ASC "
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # owner_node のlistのリストを返します(名前版)(他のユーザのものも含みます)
    def GetUserListListFormated(self, owner_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("owner_name %s is not registerd." % owner_name)
            return []
        return self.FormatList(self.GetUserListListByNode(owner_node))

    # list_idのリストからフォローしているユーザのユーザ名リストを取得します
    def GetListUserListByListID(self, list_id):
        query = ""
        query += "START list_node=node(%d) " % list_id
        query += "MATCH (followed_node) <-[follow_r:FOLLOW]- list_node "
        query += "RETURN followed_node.name "
        query += "ORDER BY follow_r.time ASC "
        result_list, metadata = cypher.execute(self.gdb, query)
        user_node_name_list = []
        for node_list in result_list:
            if len(node_list) == 1:
                user_node_name_list.append(node_list[0])
        return user_node_name_list

    # owner_node のlist名list_nameのリストからフォローしているユーザのユーザ名リストを取得します
    def GetListUserListByNode(self, owner_node, list_name):
        if owner_node is None:
            return None
        if self.VaridateCypherString(list_name) == False:
            logging.error("list name '%s' has escape string. please user other name" % list_name)
            return None
        owner_node_id = owner_node._id
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH (followed_node) <-[follow_r:FOLLOW]- list_node <-[:LIST]- owner_node "
        query += ", list_node -[:OWNER]-> list_owner_node "
        query += "WHERE list_owner_node = owner_node "
        query += "AND list_node.name = \"%s\" " % list_name
        query += "RETURN followed_node.name "
        query += "ORDER BY follow_r.time ASC "
        result_list, metadata = cypher.execute(self.gdb, query)
        user_node_name_list = []
        for node_list in result_list:
            if len(node_list) == 1:
                user_node_name_list.append(node_list[0])
        return user_node_name_list

    # owner_node のlist名list_nameのリストからフォローしているユーザのユーザ名リストを取得します(名前版)
    def GetListUserListByName(self, owner_name, list_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("owner_name '%s' is not registerd." % owner_name)
            return False
        return self.GetListUserListByNode(owner_node, list_name)

    # owner_node のlist_nameリストから、target_nodeへのフォローを外します
    # フォロー先が居なくなっても list自体 を削除はしません
    def UnfollowUserFromListByNode(self, owner_node, list_name, target_node):
        if owner_node is None:
            return False
        if target_node is None:
            return False
        if self.VaridateCypherString(list_name) == False:
            logging.error("list name '%s' has escape string. please user other name" % list_name)
            return False
        # delete をCypherで行うと存在しなかったのかどうなのかがわからないので、
        # 一旦 relationship を手に入れてから、削除することにします。
        owner_node_id = owner_node._id
        target_node_id = target_node._id
        query = ""
        query += "START owner_node=node(%d), followed_node=node(%d) " % (owner_node_id, target_node_id)
        query += "MATCH (followed_node) <-[follow_r:FOLLOW]- list_node <-[:LIST]- owner_node "
        query += ", list_node -[:OWNER]-> list_owner_node "
        query += "WHERE list_owner_node = owner_node "
        query += "AND list_node.name = \"%s\" " % list_name
        query += "RETURN follow_r "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) <= 0:
            # 削除対象が存在しない場合は False にします
            return False
        for relation in result_list:
            relation[0].delete()
        return True
        
    # owner_node のlist_nameリストから、target_nodeへのフォローを外します(名前版)
    def UnfollowUserFromListByName(self, owner_name, list_name, target_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("owner_name '%s' is not registerd." % owner_name)
            return False
        target_node = self.GetUserNode(target_name)
        if target_node is None:
            logging.error("target_name '%s' is not registerd." % target_name)
            return False
        return self.UnfollowUserFromListByNode(owner_node, list_name, target_node)

    # リストのタイムラインを取得します。
    # 取得されるのは GetUserTimeLine() と同じtext, time, user_name, tweet_node のリストです。
    def GetListTimeline(self, list_node, limit=None, since_time=None):
        return self.GetUserTimeline(list_node, limit, since_time)

    # リストのタイムライン をGetUserTimelineFormated() と同じ
    # {"text": 本文, "time": 日付文字列, "user_name": ユーザ名}のリストにして返します
    def GetListTimelineFormated(self, user_name, list_name, limit=None, since_time=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User '%s' is undefined." % user_name)
            return []
        list_node = self.GetListNodeByNode(user_node, list_name)
        if list_node is None:
            logging.error("list '%s' not found." % list_name)
            return []
        tweet_list = self.GetListTimeline(list_node, limit, since_time)
        return self.FormatTweet(tweet_list)

    # owner_node がフォローしているlistについてのサマリを取得します
    def GetSummaryOfListByNode(self, owner_node):
        if owner_node is None:
            return None
        owner_node_id = owner_node._id
        query = ""
        query += "START owner_node=node(%d) " % owner_node_id
        query += "MATCH followed_node <-[:FOLLOW]- list_node <-[:LIST]- owner_node "
        query += ", list_node -[:OWNER]-> list_owner_node "
        query += "RETURN followed_node.name, list_node.name, list_owner_node.name, list_node.description, list_node.hidden "
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # GetSummaryOfListByNode で取り出した情報を辞書にして返します
    def FormatSummaryOfList(self, summary_list):
        result_dic = {}
        for summary in summary_list:
            (followed_node_name, list_node_name, list_owner_node_name, list_node_description, list_node_hidden) = summary
            target_dic = {'members': []}
            list_unique_id = "%s#%s" % (list_owner_node_name, list_node_name) # タプルはキーになり得ますが、json.dumps() する時にエラーしてしまうので文字列にします
            if list_unique_id in result_dic:
                target_dic = result_dic[list_unique_id]
            target_dic['name'] = list_node_name
            target_dic['owner_node_name'] = list_owner_node_name
            target_dic['description'] = list_node_description
            target_dic['hidden'] = list_node_hidden
            target_dic['members'].append(followed_node_name)
            result_dic[list_unique_id] = target_dic.copy()
        return result_dic

    # owner_node がフォローしているlistについてのサマリを取得します(名前指定版)
    def GetSummaryOfListByName(self, owner_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("User '%s' is undefined." % owner_name)
            return {}
        return self.FormatSummaryOfList(self.GetSummaryOfListByNode(owner_node))

    # 他のユーザのリストをフォローします
    def AddOtherUserListByNode(self, owner_node, other_user_node, list_name):
        if owner_node is None or other_user_node is None:
            return False
        list_node = self.GetListNodeByNode(other_user_node, list_name)
        if list_node is None:
            return False
        relationship = self.gdb.create((owner_node, "LIST", list_node))
        if relationship is None:
            return False
        relationship[0]['time'] = time.time()
        return True

    # 他のユーザのリストをフォローします(名前指定版)
    def AddOtherUserListByName(self, owner_name, other_user_name, list_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("User '%s' is undefined." % owner_name)
            return False
        other_user_node = self.GetUserNode(other_user_name)
        if other_user_node is None:
            logging.error("User '%s' is undefined." % other_user_name)
            return False
        return self.AddOtherUserListByNode(owner_node, other_user_node, list_name)

    # 自分がフォローしている他人のリストへのフォローを外します
    def DeleteOtherUserListByNode(self, owner_node, other_user_node, list_name):
        if owner_node is None or other_user_node is None:
            return False
        owner_node_id = owner_node._id
        if owner_node_id == other_user_node._id:
            # other_user_node は自分であるので、失敗にします
            logging.warn("same user request DelOtherUserListByNode()")
            return False
        list_node = self.GetListNodeByNode(other_user_node, list_name)
        if list_node is None:
            logging.error("list name '%s' not found" % list_name)
            return False
        list_node_id = list_node._id
        query = ""
        query += "START owner_node=node(%d), list_node=node(%d) " % (owner_node_id, list_node_id)
        query += "MATCH list_node <-[list_r:LIST]- owner_node "
        query += "DELETE list_r "
        result_list, metadata = cypher.execute(self.gdb, query)
        return True

    # 自分がフォローしている他人のリストへのフォローを外します(名前指定版)
    def DeleteOtherUserListByName(self, owner_name, other_user_name, list_name):
        owner_node = self.GetUserNode(owner_name)
        if owner_node is None:
            logging.error("User '%s' is undefined." % owner_name)
            return False
        other_user_node = self.GetUserNode(other_user_name)
        if other_user_node is None:
            logging.error("User '%s' is undefined." % other_user_name)
            return False
        return self.DeleteOtherUserListByNode(owner_node, other_user_node, list_name)

    # tweet をretweet します
    def RetweetByNode(self, user_node, tweet_node):
        if user_node is None:
            logging.error("user_node is None")
            return False
        if tweet_node is None:
            logging.error("tweet_node is None")
            return False
        user_node_id = user_node._id
        tweet_node_id = tweet_node._id
        # 既にretweet していた場合は失敗とします
        query = ""
        query += "START user_node=node(%d), tweet_node=node(%d) " % (user_node_id, tweet_node_id)
        query += "MATCH tweet_node -[r:RETWEET]-> user_node "
        query += "RETURN r "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) > 0:
            logging.warn("already retweeted.")
            return False
        relationship = self.gdb.create((tweet_node, "RETWEET", user_node))
        if relationship is None:
            return False
        relationship[0]['time'] = time.time()
        return True

    # tweet をretweet します(名前指定版)
    def RetweetByName(self, user_name, tweet_id):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User '%s' is undefined." % user_name)
            return False
        tweet_node = self.GetTweetNodeFromID(int(tweet_id))
        return self.RetweetByNode(user_node, tweet_node)

    # retweet を取り消します
    def UnRetweetByNode(self, user_node, tweet_id):
        if user_node is None:
            logging.error("user_node is None")
            return False
        user_node_id = user_node._id
        # retweet していない場合は失敗とします
        query = ""
        query += "START user_node=node(%d), tweet_node=node(%d) " % (user_node_id, tweet_id)
        query += "MATCH tweet_node -[r:RETWEET]-> user_node "
        query += "RETURN r "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) <= 0:
            logging.warn("retweet not found.")
            return False
        for result in result_list:
            result[0].delete()
        return True

    # retweet を取り消します(名前指定版)
    def UnRetweetByName(self, user_name, tweet_id):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User '%s' is undefined." % owner_name)
            return False
        return self.UnRetweetByNode(user_node, int(tweet_id))

    # tweet にstarをつけます
    def AddStarByNode(self, user_node, tweet_node):
        if user_node is None:
            logging.error("user_node is None")
            return False
        if tweet_node is None:
            logging.error("tweet_node is None")
            return False
        user_node_id = user_node._id
        tweet_node_id = tweet_node._id
        # 既にstarをつけていた場合は失敗とします
        query = ""
        query += "START user_node=node(%d), tweet_node=node(%d) " % (user_node_id, tweet_node_id)
        query += "MATCH tweet_node <-[r:STAR]- user_node "
        query += "RETURN r "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) > 0:
            logging.warn("already stared.")
            return False
        relationship = self.gdb.create((user_node, "STAR", tweet_node))
        if relationship is None:
            return False
        relationship[0]['time'] = time.time()
        return True

    # tweet にstarをつけます(名前指定版)
    def AddStarByName(self, user_name, tweet_id):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User '%s' is undefined." % owner_name)
            return False
        tweet_node = self.GetTweetNodeFromID(int(tweet_id))
        return self.AddStarByNode(user_node, tweet_node)

    # つけたstar を取り消します
    def DeleteStarByNode(self, user_node, tweet_id):
        if user_node is None:
            logging.error("user_node is None")
            return False
        user_node_id = user_node._id
        # retweet していない場合は失敗とします
        query = ""
        query += "START user_node=node(%d), tweet_node=node(%d) " % (user_node_id, tweet_id)
        query += "MATCH tweet_node <-[r:STAR]- user_node "
        query += "RETURN r "
        result_list, metadata = cypher.execute(self.gdb, query)
        if len(result_list) <= 0:
            logging.warn("star not found.")
            return False
        for result in result_list:
            result[0].delete()
        return True

    # つけたstar を取り消します(名前指定版)
    def DeleteStarByName(self, user_name, tweet_id):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User '%s' is undefined." % owner_name)
            return False
        return self.DeleteStarByNode(user_node, int(tweet_id))

    # tweet の詳細情報を取得します
    def GetTweetAdvancedInfoByNode(self, tweet_id, user_node=None):
        user_node_id = 0
        if user_node is not None:
            user_node_id = user_node._id
        query = ""
        query += "START tweet_node=node(%d) " % tweet_id
        if user_node is not None:
            query += ", user_node=node(%d) " % user_node_id
        query += "MATCH tweet_node <-[star_r?:STAR]- (stard_node) "
        query += ", tweet_node <-[retweet_r?:RETWEET]- (retweeted_node) "
        query += ", tweet_node -[?:TWEET]-> (tweet_user) "
        if user_node is not None:
            query += ", tweet_node <-[own_star_r?:STAR]- user_node "
            query += ", tweet_node <-[own_retweet_r?:RETWEET]- user_node "
        query += "RETURN tweet_node.text, tweet_node.time, tweet_user.name, tweet_user.icon_url? "
        query += ", count(stard_node), count(retweeted_node)"
        if user_node is not None:
            query += ", own_star_r, own_retweet_r "
        else:
            query += ", null, null "
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # tweet の詳細情報を取得します(辞書で返す版)
    def GetTweetAdvancedInfoFormated(self, tweet_id, user_name=None):
        user_node = None
        if user_name is not None:
            user_node = self.GetUserNode(user_name)
        tweet_list = self.GetTweetAdvancedInfoByNode(int(tweet_id), user_node=user_node)
        if len(tweet_list) <= 0:
            return {}
        tweet = tweet_list[0]
        tweet_dic = {}
        tweet_dic['id'] = tweet_id
        tweet_dic['text'] = tweet[0]
        tweet_dic['unix_time'] = tweet[1]
        tweet_dic['time'] = self.FormatTime(tweet[1])
        tweet_dic['user_name'] = tweet[2]
        tweet_dic['icon_url'] = tweet[3]
        tweet_dic['stard_count'] = tweet[4] if tweet[4] is not None else 0
        tweet_dic['retweeted_count'] = tweet[5] if tweet[5] is not None else 0
        return tweet_dic
