#!/usr/bin/python
# coding: UTF-8

# JP CERT の RSS を読み込んでtweet します。

import sys
import os
import json
import time
import requests # pip install requests
import feedparser # pip install feedparser
import pickle

if len(sys.argv) != 4:
    print "Usage: %s UserName API_Key state_save_file_path" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
api_key = sys.argv[2]
state_save_file = sys.argv[3]

cert_rss_url = "https://www.jpcert.or.jp/rss/jpcert-all.rdf"
cert_rss_url = "https://www.jpcert.or.jp/rss/jpcert.rdf"

# pickle を使って既に読み込み済みのRSSを取り出します
def LoadAlreadyReadRSSFeed(pickle_file_path, expire_second):
    if not os.path.exists(pickle_file_path):
        return {}
    f = open(pickle_file_path, "r")
    dic = pickle.load(f)
    f.close()
    return dic

# pickle を使って読み込み済みのRSSを保存します
def StoreAlreadyReadRSSFeed(pickle_file_path, dic):
    f = open(pickle_file_path, "w")
    pickle.dump(dic, f)
    f.close()

# RSS を読み込んでツイート用の文字列に変換して、それぞれリストにしてます
# 正常時に返されるのは key を id とし、value が {"time": float, "text": string} の辞書です
# 失敗したら None を返します
def GetRSSText(url):
    feed = feedparser.parse(url)
    if feed is None or "entries" not in feed:
        return None
    entries = feed['entries']
    result = {}
    for item in entries:
        #print item.keys()
        text = item.title.encode('utf8') + "\n"
        if "summary" in item.keys():
            text += item.summary.encode('utf8') + "\n"
        text += item.link.encode('utf8')
        item_time = time.mktime(item.updated_parsed)
        id = item.id
        result[id] = {'time': item_time, 'text': text}
    return result

# dic1 と dic2 の間で、dic1 側にしかないものだけを入れた辞書を返します
def GetNewItems(dic1, dic2):
    only = {}
    dic1_keys = dic1.keys()
    dic2_keys = dic2.keys()
    for dic1_key in dic1_keys:
        if dic1_key not in dic2_keys:
            only[dic1_key] = dic1[dic1_key]
    return only

# ツイートします。ツイートに成功したらobjectを、失敗したらNoneを返します
def PostTweet(user_name, api_key, text, reply_to=None):
    request_data = {}
    request_data['user_name'] = user_name
    request_data['api_key'] = api_key
    request_data['text'] = text
    if reply_to is not None:
        request_data['reply_to'] = reply_to

    req = requests.post('https://necomatter.necoma-project.jp/post.json',
            headers={'content-type': 'application/json; charset=utf-8'},
            data=json.dumps(request_data))
    if req.status_code != 200:
        print "post failed: ", req.status_code
        return None
    result = req.json()
    if 'result' not in result or 'ok' != result['result']:
        print "post failed"
        return None
    return result

# RSS を取得して
rss = GetRSSText(cert_rss_url)
# 既に読み込み済みのものを取得して
already_read_rss = LoadAlreadyReadRSSFeed(state_save_file, 60*60*24*30)
# 新しいものだけを濾しとって
new_items = GetNewItems(rss, already_read_rss)
# 今取得したものを保存しておいて
StoreAlreadyReadRSSFeed(state_save_file, rss)
# 新しいものについてはツイートする
for item in new_items.values():
    PostTweet(user_name, api_key, item['text'])
exit(0)


