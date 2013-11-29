#!/usr/bin/python
# coding: UTF-8

# tweetストリーミングを監視して "hello" という文字列が現れたら
# そのtweetに対して "hello <user_name>" を返すbot

import sys
import json
import requests # pip install requests

if len(sys.argv) != 3:
    print "Usage: %s UserName API_Key " % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
api_key = sys.argv[2]
regexp = 'hello'

# ツイートします。ツイートに成功したらobjectを、失敗したらNoneを返します
def PostTweet(user_name, api_key, text, reply_to=None):
    request_data = {}
    request_data['user_name'] = user_name
    request_data['api_key'] = api_key
    request_data['text'] = text
    if reply_to is not None:
        request_data['reply_to'] = reply_to

    req = requests.post('http://[::1]:8000/post.json',
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

request_data = {}
request_data['user_name'] = user_name
request_data['api_key'] = api_key
request_data['regexp'] = regexp
request_data['description'] = "hello BOT. use regexp: %s" % regexp

# streaming API越しに監視を開始します
req = requests.post('http://[::1]:8000/stream/regexp.json',
        headers={'content-type': 'application/json; charset=utf-8'},
        data=json.dumps(request_data),
        stream=True)
if req.status_code != 200:
    print "post failed: ", req.status_code
    exit(1)

# 自分がtweetした番号を覚えておくための辞書を用意します
my_tweet_id = {}

print "ready."
# iter_lines() で一行づつ読み出します。(tweetは一行づつのJSONで送られてきます)
for line in req.iter_lines(chunk_size=1):
    if line: # filter out keep-alive new lines
        tweet = json.loads(line)
        # 引っかかったtweetのIDを覚えておきます(あとでtweetする時に返事する先になります)
        tweet_id = None
        if 'id' in tweet:
            tweet_id = tweet['id']
            # 自分のtweetもstreamには現れるので、自分の送信したtweetであれば無視するようにします
            if tweet_id in my_tweet_id:
                continue
        tweet_result = PostTweet(user_name, api_key, "hello %s" % tweet['user_name'], tweet_id)
        if tweet_result is not None and 'id' in tweet_result:
            # 自分のtweetした番号は覚えておきます
            my_tweet_id[tweet_result['id']] = True

print "server disconnect. quit."
