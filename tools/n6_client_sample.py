#!/usr/bin/python
# coding: UTF-8

# n6 のクライアントサンプル(Python版)

import sys
import json
import requests # pip install requests

if len(sys.argv) != 4:
    print "Usage: %s key_file cert_file query " % sys.argv[0]
    print "example: %s iimura.key iimura.pem ip.net=10.0.0.1/8" % sys.argv[0]
    exit(1)

key_file = sys.argv[1]
cert_file = sys.argv[2]
query = sys.argv[3]

def SearchN6(key_file, cert_file, query):
    req = requests.get("https://n6alpha.cert.pl/test/search/events.sjson?%s" % query,
            verify=False,
            cert=(cert_file, key_file))
    if req.status_code != 200:
        print "result status code is not 200. (%d)" % req.status_code
        return None
    return req.text

result = SearchN6(key_file, cert_file, query)
if result is None:
    print "request failed."
    exit(1)

print result
