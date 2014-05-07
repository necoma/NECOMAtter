#!/usr/bin/python
# coding: UTF-8

# RSS を読み込んでtweet します。
# RSS から読み込むためのフィード内のターゲット等を JSON形式 のconfig fileで記述します
# config file の format は
"""
{
    "rss_url": "RSS のURL"
    , "cache_file_path": "既にtweetしたフィードを覚えておくためのキャッシュファイルへのパス"
    , "target_list": [
        {"target_key": "個々の item内 のkey", "type": "string 等データタイプ。" }
        , {同上}
        , ...
    ]
}
"""
# という感じで書きます。typeについてはGetRSSText() を直接参照して解析理解追加してください。

import sys
import os
import json
import time
import requests # pip install requests
import feedparser # pip install feedparser
import pickle

if len(sys.argv) != 4:
    print "Usage: %s UserName API_Key config_file_path" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
api_key = sys.argv[2]
config_file = sys.argv[3]

# config file を読み込みます
config = json.loads(open(config_file).read())
if 'rss_url' not in config:
    print "error: 'rss_url' key not found in config"
    exit(1)
if 'cache_file_path' not in config:
    print "error: 'cache_file_path' key not found in config"
    exit(1)
if 'target_list' not in config:
    print "error: 'target_list' key not found in config"
    exit(1)

rss_url = config['rss_url']
cache_file_path = config['cache_file_path']
config_list = config['target_list']

# pickle を使って既に読み込み済みのRSSを取り出します
def LoadAlreadyReadRSSFeed(pickle_file_path):
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
# 正常時に返されるのは key を id とし、value が {"text": string} の辞書です
# 失敗したら None を返します
def GetRSSText(url, config_list):
    feed = feedparser.parse(url)
    if feed is None or "entries" not in feed:
        return None
    entries = feed['entries']
    result = {}
    for item in entries:
        #print dir(item)
        #print item.keys()
        text = ""
        item_time = None
        for config in config_list:
            target_key = config['target_key']
            target_type = config['type']
            if target_key in item.keys():
                if target_type == "string":
                    text += item[target_key].encode('utf8') + "\n"
                elif target_type == "[0]['value'] string":
                    text += item[target_key][0]['value'].encode('utf8') + "\n"
                elif target_type == "['value'] string":
                    text += item[target_key]['value'].encode('utf8') + "\n"
                elif target_type == "time":
                    item_time = time.mktime(item[target_key])
        #print text
        id = item.id
        result[id] = {'text': text}
        if item_time is not None:
            result[id]['time'] = item_time
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
rss = GetRSSText(rss_url, config_list)
# 既に読み込み済みのものを取得して
already_read_rss = LoadAlreadyReadRSSFeed(cache_file_path)
# 新しいものだけを濾しとって
new_items = GetNewItems(rss, already_read_rss)
# 今取得したものを保存しておいて
StoreAlreadyReadRSSFeed(cache_file_path, rss)
# 新しいものについてはツイートする
for item in new_items.values():
    #print item
    PostTweet(user_name, api_key, item['text'])
exit(0)


