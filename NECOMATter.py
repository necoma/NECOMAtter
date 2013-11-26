#!/usr/bin/python
# coding: UTF-8

# $B%f!<%6$K%D%$!<%H$5$;$k$h$&$J(Btwitter$B$b$I$-$N;v$r$5$;$k;~$N(B
# DB $B$rC!$/%U%m%s%H%(%s%I%/%i%9$G$9(B


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
        # $B$H8@$o$l$?$N$G$H$j$"$($:$N=j$O(Btransaction $B$OIu0u$7$^$9(B
        #self.CypherSession = cypher.Session(url)

    # HTML $B$G(BXSS$B$5$;$J$$$h$&$J%(%9%1!<%W$r$7$^$9!#(B
    def EscapeForXSS(self, text):
        return escape(text)

    # $B%f!<%6MQ$N%$%s%G%C%/%9$r<hF@$7$^$9(B
    def GetUserIndex(self):
        if self.UserIndex is None:
            self.UserIndex = self.gdb.get_or_create_index(neo4j.Node, "user")
        return self.UserIndex

    # tweet$BMQ$N%$%s%G%C%/%9$r<hF@$7$^$9(B
    def GetTweetIndex(self):
        if self.TweetIndex is None:
            self.TweetIndex = self.gdb.get_or_create_index(neo4j.Node, "tweet")
        return self.TweetIndex

    # tag$BMQ$N%$%s%G%C%/%9$r<hF@$7$^$9(B
    def GetTagIndex(self):
        if self.TagIndex is None:
            self.TagIndex = self.gdb.get_or_create_index(neo4j.Node, "tag")
        return self.TagIndex

    # API Key$BMQ$N%$%s%G%C%/%9$r<hF@$7$^$9(B
    def GetAPIKeyIndex(self):
        if self.APIKeyIndex is None:
            self.APIKeyIndex = self.gdb.get_or_create_index(neo4j.Node, "api_key")
        return self.APIKeyIndex

    # tweet $B$N%/%(%j7k2L$+$i%U%)!<%^%C%H$5$l$?<-=q$NG[Ns$K$7$FJV$7$^$9(B
    def FormatTweet(self, tweet_list):
        if tweet_list is None:
            logging.warning("can not get tweet list from tag.")
            return []
        result_list = []
        for tweet in tweet_list:
            result_list.append({'text': tweet[0],
                "time": time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tweet[1])),
                "user": tweet[2],
                "unix_time": tweet[1]})
        return result_list

    # $B%f!<%6$N%N!<%I$r<hF@$7$^$9!#(B
    # $B2?$+LdBj$,$"$C$?>l9g$O(BNone $B$rJV$7$^$9!#(B
    def GetUserNode(self, user_name):
        user_index = self.GetUserIndex()
        # $B<hF@$9$k(B
        user_list = user_index.get("name", user_name)
        if len(user_list) != 1:
            if len(user_list) == 0:
                return None
            else:
                logging.warning("user %s have multiple node: %s" % (user_name, str(user_list)))
                return None
        return user_list[0]

    # $B%f!<%6$N(BAPIKey$B%N!<%I$r<hF@$7$^$9!#B8:_$7$J$1$l$P:n@.$7$^$9(B
    # $B2?$+LdBj$,$"$C$?>l9g$O(BNone $B$rJV$7$^$9!#(B
    def CreateOrGetUserAPIKeyNode(self, key_name):
        api_index = self.GetAPIKeyIndex()
        # $B<hF@$9$k(B
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

    # text $B$+$i%?%0$N$h$&$JJ8;zNs$r<h$j=P$7$F%j%9%H$K$7$FJV$7$^$9(B
    def GetTagListFromText(self, text):
        return re.findall(r"(#[^ ]+)", text)

    # tweet_node $B$r!"(Btext $B$+$iCj=P$7$?%?%0$X$H4XO"IU$1$^$9(B
    def Tweet_LinkToTag(self, tweet_node, text):
        tag_list = self.GetTagListFromText(text)
        #tag_index = self.GetTagIndex()
        for tag in tag_list:
            tag_node = self.gdb.get_or_create_indexed_node("tag", "tag", tag, {"tag": tag})
            tweet_node.create_path("TAG", tag_node)

    # $B%f!<%6$K(Btweet $B$5$;$^$9!#(BTweet$B$K@.8y$7$?$i!"(Btweet_node $B$rJV$7$^$9(B
    def Tweet(self, user_node, tweet_string):
        if user_node is None:
            logging.error("Tweet owner is not defined.")
            return None
        tweet_index = self.GetTweetIndex()
        text = self.EscapeForXSS(tweet_string)
        tweet_node = tweet_index.create("text", text, {
            "text": self.EscapeForXSS(tweet_string), 
            "time": time.time()
            })
        # user_node $B$,(Btweet $B$7$?$H$$$&$3$H$G!"(Bpath $B$r(Btweet_node $B$+$i7R$2$^$9(B
        tweet_node.create_path("TWEET", user_node)
        # $B%?%0$,$"$l$P$=$3$K7R$.$^$9(B
        self.Tweet_LinkToTag(tweet_node, text)
        return tweet_node

    # $B%f!<%6$N(Btweet $B$r<hF@$7$F!"(B{"text": $BK\J8(B, "time": UnixTime} $B$N%j%9%H$H$7$FJV$7$^$9(B
    def GetUserTweet(self, user_node, limit=None, since_time=None):
        if user_node is None:
            logging.error("User is undefined.")
            return []
        # $B%f!<%6$N(BID $B$r<hF@$7$^$9(B
        user_id = user_node._id
        # $B%/%(%j$r:n$j$^$9(B
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (tweet) -[:TWEET]-> (user) "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list
        """ # good old code. not used cypher
        relationship_list = user_node.match_incoming(rel_type="TWEET", limit=limit)
        result_node_list = []
        for relationship in relationship_list:
            result_node_list.append(relationship.start_node)
        return result_node_list
        """

    # tweet_node $B$r(B{"text": $BK\J8(B, "time": $BF|IUJ8;zNs(B, "user": $B%f!<%6L>(B} $B$N7A<0$N<-=q$K$7$^$9(B
    def ConvertTweetNodeToHumanReadableDictionary(self, tweet_node):
        if tweet_node is None:
            logging.error("tweet_node is None")
            return None
        result_dic = {}
        result_dic['text'] = tweet_node['text']
        result_dic['time'] = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tweet_node['time']))
        return result_dic

    # $B%f!<%6$N(Btweet $B$r(B{"text": $BK\J8(B, "time": $BF|IUJ8;zNs(B}$B$N%j%9%H$K$7$FJV$7$^$9(B
    def GetUserTweetFormated(self, user_name, limit=None, since_time=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return []
        tweet_list = self.GetUserTweet(user_node, limit=limit, since_time=since_time)
        return self.FormatTweet(tweet_list)

    # $B%f!<%6$N%?%$%`%i%$%s$r<hF@$7$^$9!#(B
    # $B<hF@$5$l$k$N$O(B text, time, name $B$N%j%9%H$G$9!#(B
    def GetUserTimeline(self, user_node, limit=None, since_time=None):
        if user_node is None:
            logging.error("User is undefined.")
            return []
        user_id = user_node._id
        # $B%/%(%j$r:n$j$^$9(B
        query = ""
        query += "START user = node(%d) " % user_id
        query += "MATCH (tweet) -[:TWEET]-> (target) <-[:FOLLOW]- (user) "
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, target.name "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # $B%f!<%6$N%?%$%`%i%$%s(B $B$r(B{"text": $BK\J8(B, "time": $BF|IUJ8;zNs(B, "user": $B%f!<%6L>(B}$B$N%j%9%H$K$7$FJV$7$^$9(B
    def GetUserTimelineFormated(self, user_name, limit=None, since_time=None):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("User %s is undefined." % user_name)
            return []
        tweet_list = self.GetUserTimeline(user_node, limit, since_time)
        return self.FormatTweet(tweet_list)

    # $B%f!<%6L>$H%;%C%7%g%s%-!<$+$i!"$=$N%;%C%7%g%s$,M-8z$+$I$&$+$rH=Dj$7$^$9!#(B
    def CheckUserSessionKeyIsValid(self, user_name, session_key):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return False
        if session_key != user_node['session_key'] or session_key is None:
            return False
        expire_time = user_node['session_expire_time']
        now_time = time.time()
        if expire_time > now_time:
            logging.info("session expired.")
            return False
        return True

    # $B%f!<%6%;%C%7%g%s$r?75,:n@.$7$FJV$7$^$9(B
    def UpdateUserSessionKey(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return None
        # $B2x$7$/%;%C%7%g%s%-!<J8;zNs$r@8@.$7$^$9(B
        session_key = self.GetPasswordHash(user_name,
            str(time.time() + random.randint(0, 100000000)))
        user_node['session_key'] = session_key
        user_node['session_expire_time'] = time.time() + self.SessionExpireSecond
        return session_key

    # DB$B$KEPO?$5$l$k%Q%9%o!<%I$N%O%C%7%eCM$r<hF@$7$^$9(B
    def GetPasswordHash(self, user_name, password):
        if isinstance(user_name, unicode):
            user_name = user_name.encode('utf-8')
        if isinstance(password, unicode):
            password = password.encode('utf-8')
        return hashlib.sha256("%s/%s" % (password, user_name)).hexdigest()

    # $B%f!<%6$N%Q%9%o!<%I$r3NG'$7$^$9(B
    def CheckUserPasswordIsValid(self, user_name, password):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.warning("User %s is undefined." % user_name)
            return False
        if self.GetPasswordHash(user_name, password) != user_node['password_hash']:
            return False
        return True

    # $B%f!<%6$N%Q%9%o!<%I$r99?7$7$^$9(B
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

    # $B%f!<%6$rEPO?$7$^$9(B
    def AddUser(self, user_name, password):
        # $B%f!<%6L>$O$$$A$$$A%(%9%1!<%W$9$k$N$,$a$s$I$/$5$$$N$G(B
        # $BEPO?;~$K%(%9%1!<%W$5$l$J$$$3$H$r3NG'$9$k$@$1$K$7$^$9(B($B$$$$$N$+$J$!(B)
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
        # $B<+J,$r%U%)%m!<$7$F$$$J$$$H<+J,$N%?%$%`%i%$%s$K<+J,$,=P$^$;$s(B
        self.FollowUserByNode(user_node, user_node)
        return True

    # follower $B$,(Btarget $B$r%U%)%m!<$7$F$$$k$+$I$&$+$r3NG'$7$^$9(B
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

    # $B%f!<%6$r%U%)%m!<$7$^$9(B
    def FollowUserByNode(self, follower_user_node, target_user_node):
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        if self.IsFollowed(follower_user_node, target_user_node):
            logging.warning("already followed.")
            return True
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        relationship = self.gdb.create((follower_user_node, "FOLLOW", target_user_node))
        if relationship is None:
            return False
        return True

    # $B%f!<%6$r%U%)%m!<$7$^$9(B
    def FollowUserByName(self, follower_user_name, target_user_name):
        follower_user_node = self.GetUserNode(follower_user_name)
        target_user_node = self.GetUserNode(target_user_name)
        return self.FollowUserByNode(follower_user_node, target_user_node)

    # $B%f!<%6$r%U%)%m!<$7$F$$$?$i%U%)%m!<$r30$7$^$9(B
    def UnFollowUserByNode(self, follower_user_node, target_user_node):
        if follower_user_node is None or target_user_node is None:
            logging.error("follower_user_node or target_user_node is None")
            return False
        result = self.gdb.match(start_node=follower_user_node, rel_type="FOLLOW", end_node=target_user_node)
        if result is None:
            logging.error("fatal error. match() return None.")
            return False
        for relationship in result:
            self.gdb.delete(relationship)
        return True

    # $B%f!<%6$r%U%)%m!<$7$F$$$?$i%U%)%m!<$r30$7$^$9(B
    def UnFollowUserByName(self, follower_user_name, target_user_name):
        follower_user_node = self.GetUserNode(follower_user_name)
        target_user_node = self.GetUserNode(target_user_name)
        return self.UnFollowUserByNode(follower_user_node, target_user_node)

    # $B%f!<%6L>$N%j%9%H$r<hF@$7$^$9(B
    def GetUserNameList(self):
        user_index = self.gdb.get_or_create_index(neo4j.Node, "user")
        query_result = user_index.query("name:*")
        user_name_list = []
        for user_node in query_result:
            if "name" in user_node:
                user_name_list.append(user_node["name"])
        return user_name_list

    # $BBP>]$N%f!<%6$,%U%)%m!<$7$F$$$k%f!<%6L>$N%j%9%H$r<hF@$7$^$9(B
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

    # tweet$B$N%N!<%I(BID$B$+$iBP>]$N%f!<%6$N(Btweet $B$r<hF@$7$^$9!#(B
    def GetTweetFromID(self, tweet_id):
        query = ""
        query += "start tweet = node(%d) " % tweet_id
        query += "MATCH (user) <-[:TWEET]- (tweet) "
        query += "RETURN tweet.text, tweet.time, user.name "
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # tag $B$+$i(Btweet $B$r<hF@$7$^$9(B
    def GetTagTweet(self, tag_string, limit=None, since_time=None):
        query = ""
        query += "start tag_node=node:tag(tag=\"%s\") " % tag_string.replace('"', '_')
        query += "MATCH (user) <-[:TWEET]- (tweet) -[:TAG]-> tag_node " 
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # tag $B$+$i<hF@$7$?(Btweet $B$r(B{"text": $BK\J8(B, "time": $BF|IUJ8;zNs(B}$B$N%j%9%H$K$7$FJV$7$^$9(B
    def GetTagTweetFormated(self, tag_name, limit=None, since_time=None):
        tweet_list = self.GetTagTweet(tag_name, limit=limit, since_time=since_time)
        return self.FormatTweet(tweet_list)

    # tag $B$N%j%9%H$r<hF@$7$^$9(B
    def GetTagList(self, limit=None, since_time=None):
        query = ""
        query += "start tag_node=node:tag(tag=\"%s\") " % tag_string.replace('"', '_')
        query += "MATCH (user) <-[:TWEET]- (tweet) -[:TAG]-> tag_node " 
        if since_time is not None:
            query += "WHERE tweet.time < %f " % since_time
        query += "RETURN tweet.text, tweet.time, user.name "
        query += "ORDER BY tweet.time DESC "
        if limit is not None:
            query += "LIMIT %d " % limit
        result_list, metadata = cypher.execute(self.gdb, query)
        return result_list

    # $B%f!<%6$N(BAPI$B%-!<$N%j%9%H$r<hF@$7$^$9(B($B%N!<%I;XDjHG(B)
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

    # $B%f!<%6$N(BAPI$B%-!<$N%j%9%H$r<hF@$7$^$9(B($BL>A0;XDjHG(B)
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

    # $B%f!<%6$,(BAPI$B%-!<$r;}$C$F$$$k$+$I$&$+$r3NG'$7$^$9(B
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

    # $B%f!<%6$N(BAPI$B%-!<$r:o=|$7$^$9(B
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
        query += "DELETE key_node, r" # $B%N!<%I$r(Bdelete$B$9$k$H$-$O(B node $B$H(B $B%j%l!<%7%g%s%7%C%W$rN>J}(Bdelete$B$9$kI,MW$,$"$k$C$]$$(B
        result_list, metadata = cypher.execute(self.gdb, query)
        # $B<:GT$7$?;~$K$O$A$c$s$H(Blist$B$,J#?t$K$J$k$N!)(B
        if len(result_list) != 0:
            return False
        return True

    # $B%f!<%6$K(BAPI$B%-!<$rDI2C$7$^$9(B
    def CreateUserAPIKeyByName(self, user_name):
        user_node = self.GetUserNode(user_name)
        if user_node is None:
            logging.error("user %s is not registerd" % user_name)
            return None
        # $B2x$7$/(BAPI$B%-!<$r@8@.$7$^$9(B
        key = self.GetPasswordHash(user_name,
            str(time.time() + random.randint(0, 100000000)))
        key_node = self.CreateOrGetUserAPIKeyNode(key)
        key_node['time'] = time.time()
        relationship = self.gdb.create((key_node, "API_KEY", user_node))
        if relationship is None:
            self.gdb.delete(key_node)
            return None
        return key_node
        

