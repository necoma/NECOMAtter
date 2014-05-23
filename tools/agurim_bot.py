#!/usr/bin/python
# coding: UTF-8

# agurm から情報を拾って、unique なホストであればtweetできるような markdown text を吐き出します
#
# 1時間毎に情報を取得して、uniqueな agurigate host をtweetする。
# IPv4 の場合は /24 より細かいホスト
# IPv6 の場合は /48 より細かいホスト
# bytes か packets の 割合が 25% を超えるもの
# がunique な対象で、その対象ホストで直近24時間に初めて現れたもの、というフィルタをかける。

import sys
import json
import subprocess
import requests # pip install requests
from requests.auth import HTTPDigestAuth
import re
import pickle
import os

pickle_file_name = "agurim_prev_data.pickle" # 前回までの agurim の情報を保存するファイル
data_set_save_count = 24 # 24回分ということで、24時間分になるはず。cronが一時間に一回走るはずなので。
percent_recurrently_threshold = 25.0 # %表記での割合がこれを超えると多いと判定される
ipv4_mask_threshold = 24 # IPv4 でのnetmaskのビット数がこれ以上であれば十分に細かいホストとされる
ipv6_mask_threshold = 48 # IPv6 でのnetmaskのビット数がこれ以上であれば十分に細かいホストとされる

if len(sys.argv) != 3:
    print "Usage: %s UserName API_Key " % sys.argv[0]
    exit(1)

necomatter_user_name = sys.argv[1]
necomatter_api_key = sys.argv[2]

def GetAgurimData():
    req = requests.post("http://mawi.wide.ad.jp/members_only/aguri2/agurim/cgi-bin/myagurim.cgi",
                        auth=HTTPDigestAuth('wide', 'open sesame'), # oh...
                        data={
            'criteria': 'packet',
            'format': 'json',
            'duration': 3600,
             'interval': 3600,
             'startTime': 0,
             'endTime': 0,
             'threshold': 0,
             'nflows': 0
            })
    return req.text

def ConvertExcapedText(text):
    return text.replace("\\n", "\n").replace("\\t", "\t")

def ParseAgurimDataToDictionary(text):
    """
    "
    %!AGURI-2.0
    %%StartTime: Thu May 22 20:39:00 2014 (2014/05/22 20:39:00)
    %%EndTime: Thu May 22 21:00:00 2014 (1970/01/01 09:00:00)
    %AvgRate: 345.40Mbps 126938.85pps
    % criteria: pkt counter (1 % for addresses, 1 % for protocol data)

    [ 1] 203.178.148.19 *: 2465148971 (4.53%)       41081309 (25.68%)
            [1:2048:2048] 100.00% 100.00%
    """
    # というのが来るので、
    # それらしく辞書に入れる
    agurim_data = re.sub(r'^"\n', '', text) # とりあえず先頭の " は外しておきます。なんかたぶん無意味なので
    agurim_data_list = agurim_data.split("\n\n")
    if len(agurim_data_list) != 2:
        print "header parse error. header separator is not found."
        return None
    agurim_header_list = agurim_data_list[0].split("\n")    
    agurim_raw_list = agurim_data_list[1].split("\n")

    ret = {}
    # 先頭からのものはそのまま入れておく
    ret["version"] = agurim_header_list.pop(0)
    ret["StartTime"] = agurim_header_list.pop(0).replace("%%StartTime: ", "")
    ret["EndTime"] = agurim_header_list.pop(0).replace("%%EndTime: ", "")
    avgrate_list = agurim_header_list.pop(0).replace("%AvgRate: ", "").split(" ")
    if len(avgrate_list) != 2:
        print "header parse error. unknown format from agurim."
        return None
    ret["AvgRate"] = {
        "bps": avgrate_list[0],
        "pps": avgrate_list[1]
        }
    ret["criteria"] = agurim_header_list.pop(0)

    """
        [ 1] 203.178.148.19 *: 2465148971 (4.53%)       41081309 (25.68%)
            [1:2048:2048] 100.00% 100.00%
    """
    ret_data = []
    # 実際のデータをparseする
    data_no = 0
    while len(agurim_raw_list) > 1:
        first_line = agurim_raw_list.pop(0)
        second_line = agurim_raw_list.pop(0)
        
        unit = {}
        unit["first_line"] = first_line
        unit["second_line"] = second_line

        first_line_match = re.findall('^\[\s*\d+\]\s+([^\]]+)\s+([^\]]+)\s+(\d+)\s+\(([\d\.]+)%\)\s+(\d+)\s+\(([\d\.]+)%\)', first_line)
        for match in first_line_match: # 複数回ひっかかる事は無いとおもうけれど……
            unit["from"] = match[0]
            unit["to"] = match[1]
            unit["bytes"] = match[2]
            unit["bytes_p"] = match[3]
            unit["packets"] = match[4]
            unit["packets_p"] = match[5]
        unit['data'] = second_line
        unit['no'] = data_no
        ret_data.append(unit)
        data_no += 1
    ret['data'] = ret_data
    return ret

def LoadPrevData(file_name):
    if not os.path.exists(file_name):
        return []
    try:
        f = open(file_name, 'r')
    except:
        return []
    ret = pickle.load(f)
    f.close()
    if ret is None:
        return []
    return ret

def SaveCurrentData(data, file_name):
    try:
        new_file_name = file_name + ".tmp"
        f = open(new_file_name, "w")
        pickle.dump(data, f)
        f.close()
        if os.path.exists(file_name):
            os.remove(file_name)
        os.rename(new_file_name, file_name)
    except:
        return False
    return True

# data = {} が頻発していると判断したら True を返します
def IsRecurrently(data):
    if not 'bytes' in data or not 'bytes_p' in data or not 'packets' in data or not 'packets_p' in data:
        return False
    bytes = int(data['bytes'])
    bytes_p = float(data["bytes_p"])
    packets = int(data["packets"])
    packets_p = float(data["packets_p"])

    if bytes_p > percent_recurrently_threshold:
        return True
    if packets_p > percent_recurrently_threshold:
        return True
    return False
    

# text に * が入っていなくて、IPv4 なら /24, IPv6 なら /48 よりも狭いレンジなら True、
# そうでなければ False を返します
def IsMinAguri(text):
    if re.match(r'\*', text):
        return False
    prefix = 0    
    subnet_match = re.match(r'/(\d+)', text)
    if subnet_match is not None:
        for subnet in subnet_match:
            prefix = subnet[0]
    else:
        return True
    if re.match(r'\.', text):
        if prefix >= ipv4_mask_threshold:
            return True
        else:
            return False
    if prefix >= ipv6_mask_threshold:
        return True
    return False

# agurim_prev_data の中に from_addr や to_addr が入っているかを確認する
def SearchAddressFromAgrimPrevData(agurim_prev_data, from_addr, to_addr):
    for agurim_data in agurim_prev_data:
        for data_set in agurim_data['data']:
            if from_addr == data_set['from']:
                return True
            if to_addr == data_set['to']:
                return True
    return False

def FilterImportantData(agurim_data, prev_data):
    ret = []
    for data in agurim_data:
        hit = {}
        b_hit = False
        from_addr = None
        to_addr = None
        if not IsRecurrently(data):
            continue
        if IsMinAguri(data['from']):
            hit['from'] = data['from']
            from_addr = data['from']
            hit['hit_from'] = data['from'] # あとで強調するために何が多いと判断されたのかを残しておきます
            b_hit = True
        if IsMinAguri(data['to']):
            hit['to'] = data['to']
            to_addr = data['to']
            hit['hit_to'] = data['to']  # あとで強調するために何が多いと判断されたのかを残しておきます
            b_hit = True
        if SearchAddressFromAgrimPrevData(prev_data, from_addr, to_addr):
            continue
        if b_hit:
            hit['data'] = data
            ret.append(hit)
    return ret

# filterd_agurim_data を NECOMAtter に書き込めるような形式(plain text)に変換します
def FormatAgurimHitData(filterd_agrim_data):
    if filterd_agrim_data is None:
        return ""
    text = "#Agurim  \n"
    text += "%d characteristic nodes found.  \n" % (len(filterd_agrim_data), )
    summary = ""
    detail = ""
    for agurim_data in filterd_agrim_data:
        if not 'data' in agurim_data:
            continue
        data = agurim_data['data']
        first_line = data['first_line']
        if 'hit_from' in agurim_data:
            first_line = first_line.replace(agurim_data['hit_from'], "**" + agurim_data['hit_from'] + "**")
            summary += " - from: " + agurim_data['hit_from'] + "\n"
        if 'hit_to' in agurim_data:
            first_line = first_line.replace(agurim_data['hit_to'], "**" + agurim_data['hit_to'] + "**")
            summary += " - to: " + agurim_data['hit_to'] + "\n"
        detail += first_line + "  \n"
        detail += data['second_line'] + "  \n"
    text += summary + "\n" + "detail here:  \n"
    text += detail
    text += "\nhttp://mawi.wide.ad.jp/members_only/aguri2/agurim/"
    return text

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

# 前までのデータを読み込みます
prev_data = LoadPrevData(pickle_file_name)
# agurim から現在のデータを取り出して普通の text にします(\n\tを変換します)
agurim_data = ConvertExcapedText(GetAgurimData())
# plain text のデータからPythonの辞書形式に変換します
agurim_data_parsed = ParseAgurimDataToDictionary(agurim_data)
# 前までのデータと含めて急に出てきた多きな値を取り出します
filterd_agrim_data = FilterImportantData(agurim_data_parsed['data'], prev_data)

# 一つ前までのデータと今読み込んだデータを君合わせて
prev_data.append(agurim_data_parsed)
new_agurim_data_set = prev_data
# data_set_save_count より多くなったデータは排除して
if new_agurim_data_set is not None and len(new_agurim_data_set) > data_set_save_count:
    new_agurim_data_set.pop(0)
# 今回までのデータを保存しておきます
if not SaveCurrentData(new_agurim_data_set, pickle_file_name):
    print "save failed"

# ヒットしたものを markdown にして NECOMAtter に書き込めるようにします。
#print "hit count: ", len(filterd_agrim_data)
text = FormatAgurimHitData(filterd_agrim_data)

if len(filterd_agrim_data) <= 0:
    exit(0)

PostTweet(necomatter_user_name, necomatter_api_key, text)


