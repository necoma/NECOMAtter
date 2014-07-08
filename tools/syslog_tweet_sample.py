#!/usr/bin/python
# coding: UTF-8

# syslog-ng のprogram として起動して、単にtweetするサンプル
# 動作としては、標準入力から受け取った文字列をそのままtweetするだけです。
# syslog-ng 側では、
"""
destination d_necomatter { program("/home/iimura/NECOMAtter/tools/syslog_tweet_sample.py limura 3394fa5eb1f97f0b84405eeb4ad0b51bb6d320f8c1ffd56ed5f069a005c17521");};
filter f_test   { facility(local6) and level(info) and message(TEST); };
log { source(s_src); filter(f_test);  destination(d_necomatter); };
"""
# といったような形で config を書くことで実行できます。
# この例の場合だと、
# % logger -p local6.info TEST Message
# といった形で syslog を書くことで、確認できます。

import sys
import json
import requests # pip install requests

if len(sys.argv) != 3:
    print "Usage: %s UserName API_Key " % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
api_key = sys.argv[2]

# ツイートします。ツイートに成功したらobjectを、失敗したらNoneを返します
def PostTweet(user_name, api_key, text, reply_to=None):
    request_data = {}
    request_data['user_name'] = user_name
    request_data['api_key'] = api_key
    request_data['text'] = text
    if reply_to is not None:
        request_data['reply_to'] = reply_to

    req = requests.post('http://[::1]/post.json',
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

for line in iter(sys.stdin.readline, ""):
    tweet_result = PostTweet(user_name, api_key, line)

