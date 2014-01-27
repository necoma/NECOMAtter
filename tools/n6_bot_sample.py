#!/usr/bin/python
# coding: UTF-8

# tweetストリーミングを監視してPOSTを行うBOTのサンプル実装です。
#
# tweetストリーミングからIPv4 address っぽいものを取り出してきて、
# 引っかかったらn6 を使って検索を行った結果を返します。

import sys
import json
import subprocess
import requests # pip install requests

if len(sys.argv) != 3:
    print "Usage: %s UserName API_Key " % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
api_key = sys.argv[2]
regexp = '(\d+\.\d+\.\d+\.\d+)'
key_file = "iimura.key"
cert_file = "iimura.pem"
curl_command = "curl"

def SearchN6(key_file, cert_file, query):
    req = requests.get("https://n6alpha.cert.pl/test/search/events.sjson?%s" % query,
            verify=False,
            cert=(cert_file, key_file))
    if req.status_code != 200:
        print "result status code is not 200. (%d)" % req.status_code
        return None
    return req.text

# n6 でip=... の検索を行います
def SearchN6_IPv4(ipv4_addr):
    return SearchN6(key_file, cert_file, "ip=%s" % ipv4_addr)

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
request_data['description'] = "n6 BOT sample. use regexp: %s" % regexp

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
        # マッチ結果に値がなければ検索できないので無視します
        if 'match_result' not in tweet:
            continue
        # サーバに送信する正規表現に () を入れておけば、
        # match_result にリストで入れて返してくれます
        for match_result in tweet['match_result']:
            print "hit: ", match_result
            n6_result = SearchN6_IPv4(match_result)
            if n6_result is None or n6_result == "":
                print "n6 result is nothing..."
                n6_result = "no result from n6"
            else:
                print "n6 result got."
            tweet_result = PostTweet(user_name, api_key, "n6 search ip: #%s result: %s" % (match_result, n6_result), tweet_id)
            if tweet_result is not None and 'id' in tweet_result:
                # 自分のtweetした番号は覚えておきます
                my_tweet_id[tweet_result['id']] = True

print "server disconnect. quit."
