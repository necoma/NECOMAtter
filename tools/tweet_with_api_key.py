#!/usr/bin/python
# coding: UTF-8

# API key を使ってtweetします

import sys
import json
import requests # pip install requests
import re

if len(sys.argv) < 3:
    print "Usage: %s Host UserName API_Key [reply tweet ID]" % sys.argv[0]
    exit(1)

host = sys.argv[1]
user_name = sys.argv[2]
api_key = sys.argv[3]
reply_to = None
if len(sys.argv) > 4:
    reply_to = int(sys.argv[4])

tweet = sys.stdin.read()

request_data = {}
request_data['user_name'] = user_name
request_data['api_key'] = api_key
request_data['text'] = tweet
if reply_to is not None:
    request_data['reply_to'] = reply_to

req = requests.post('http://' + host + ':8000/post.json',
        headers={'content-type': 'application/json; charset=utf-8'},
        data=json.dumps(request_data))
if req.status_code != 200:
    print "post failed: ", req.status_code
    exit(1)
result = req.json()
if 'result' not in result or 'ok' != result['result']:
    print "post failed"
    exit(1)

print "post success"
