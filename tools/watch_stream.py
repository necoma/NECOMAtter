#!/usr/bin/python
# coding: UTF-8

# 正規表現マッチでtweetストリーミングを監視します

import sys
import json
import requests # pip install requests

if len(sys.argv) != 4:
    print "Usage: %s UserName API_Key regexp" % sys.argv[0]
    exit(1)

user_name = sys.argv[1]
api_key = sys.argv[2]
regexp = sys.argv[3]

request_data = {}
request_data['user_name'] = user_name
request_data['api_key'] = api_key
request_data['regexp'] = regexp
request_data['description'] = "Public Timeline Watcher (sample) use regexp: %s" % regexp

req = requests.post('http://[::1]:8000/stream/regexp.json',
        headers={'content-type': 'application/json; charset=utf-8'},
        data=json.dumps(request_data),
        stream=True)
if req.status_code != 200:
    print "post failed: ", req.status_code
    exit(1)

# iter_lines() を引数なしで使うとchunk_size が512になるらしいのですが、
# chunk_size分のバッファが確保されてそれ未満の長さのデータだとバッファされてしまうので、
# 怪しく 1 で上書きして使います。
for line in req.iter_lines(chunk_size=1):
    if line: # filter out keep-alive new lines
        print line

print "stream end."
