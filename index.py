#!/usr/bin/python
# coding: utf-8

import sys,os
import logging

from flask import Flask, flash, redirect, url_for, session, request, jsonify, g, render_template, stream_with_context, Response, abort
from NECOMATter import NECOMATter
import time
import json
import re
import gevent
from gevent.wsgi import WSGIServer
import gevent.queue

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'f34b38b053923d1cb202fc5b9e8d2614'

world = NECOMATter("http://localhost:7474")

# streaming API で監視を走らせる時のwatcherを管理するclass
# ストリーミングのクライアントが現れる毎にwatchdogリストに登録する
# 登録されたものはクライアント側で何らかのエラーがあったら登録を削除する
class StreamingWatcherManager():
    def __init__(self):
        self.uniq_id = 0
        self.regexp_watcher_list = {}

    def RegisterWatcher_RegexpMatch(self, regexp_pattern, queue):
        regist_id = self.uniq_id
        self.uniq_id += 1
        self.regexp_watcher_list[regist_id] = {'re_prog': re.compile(regexp_pattern), 'queue': queue }
        return regist_id

    def UnregisterWatcher(self, delete_id):
        del self.regexp_watcher_list[delete_id]

    def UpdateTweet(self, tweet_text, tweet_dic):
        for regexp_watcher in self.regexp_watcher_list.values():
            if 're_prog' not in regexp_watcher or 'queue' not in regexp_watcher:
                continue
            re_prog = regexp_watcher['re_prog']
            queue = regexp_watcher['queue']
            if re_prog is None or queue is None:
                continue
            match_result = re_prog.findall(tweet_text)
            if not match_result:
                continue
            queue.put_nowait((tweet_dic, match_result))

    def GetWatcherListNum(self):
        return len(self.regexp_watcher_list)

watchDogManager = StreamingWatcherManager()

# NECOMATter で認証完了しているユーザ名を取得します。
# 認証完了していない場合にはNoneを返します
def GetAuthenticatedUserName():
    user_name = session.get('user_name')
    session_key = session.get('session_key')
    if world.CheckUserSessionKeyIsValid(user_name, session_key):
        return user_name
    #print 'session_key failed', user_name, session_key
    if ( request.method == 'POST' and
        request.json is not None and
        'user_name' in request.json and
        'api_key' in request.json and
        world.CheckUserAPIKeyByName(request.json['user_name'], request.json['api_key']) ):
            return request.json['user_name']
    #print 'request has no valid API key failed'
    return None

# NECOMATter でのユーザ認証を行うデコレータ。
# 1) Flask のセッションに入っている user_name が存在するか
# 2) リクエストの中にjsonでAPI_keyが入っていればそのAPI keyが正しいか
# をそれぞれ判定して、問題なければ元の関数を呼び出し、駄目であれば abort(401) するようになります
def NECOMATterAuthRequired(func, fallback_path=None, result_type="text"):
    def decorated_func(*args, **keyWordArgs):
        user_name = GetAuthenticatedUserName()
        if user_name is None:
            abort(401)
            return
        func(*args, **keyWordArgs)
    return decorated_func 

@app.route('/')
def topPage():
    return render_template('index.html')

@app.route('/user/<user_name>.json')
def userPage_Get_Rest(user_name):
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetUserTweetFormated(user_name, limit=limit, since_time=since_time)
    return json.dumps(tweet_list)

@app.route('/user/<user_name>')
def userPage_Get(user_name):
    return render_template('timeline_page.html', user_name=user_name, do_target="Tweet", request_path="user")

@app.route('/tweet/<int:tweet_id>')
def userTweet_Get(tweet_id):
    return render_template('tweet_tree.html', tweet_id=tweet_id)

# 対象のtweetID の tweet のみを取得します
@app.route('/tweet/<int:tweet_id>.json')
def userTweet_Get_Rest(tweet_id):
    return json.dumps(world.GetTweetNodeFromIDFormatted(tweet_id))

# 対象のtweetID の返信関係の木構造を返します
@app.route('/tweet/<int:tweet_id>_tree.json')
def userTweetTree_Get_Rest(tweet_id):
    tweet_list = world.GetParentTweetAboutTweetIDFormatted(tweet_id)
    tweet_list.extend(world.GetTweetNodeFromIDFormatted(tweet_id))
    tweet_list.extend(world.GetChildTweetAboutTweetIDFormatted(tweet_id))
    return json.dumps(tweet_list)

@app.route('/tweet/<int:tweet_id>_parent.json')
def userTweetTreeParent_Get_Rest(tweet_id):
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetParentTweetAboutTweetIDFormatted(tweet_id, limit, since_time)
    return json.dumps(tweet_list)

@app.route('/tweet/<int:tweet_id>_child.json')
def userTweetTreeChild_Get_Rest(tweet_id):
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetChildTweetAboutTweetIDFormatted(tweet_id, limit, since_time)
    return json.dumps(tweet_list)

@app.route('/user/<user_name>/followed_user_name_list.json')
def userFollowedGet(user_name):
    return json.dumps(world.GetUserFollowedUserNameList(user_name))

@app.route('/timeline/<user_name>.json')
def timelinePage_Get_Rest(user_name):
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetUserTimelineFormated(user_name, limit, since_time)
    return json.dumps(tweet_list)

@app.route('/timeline/<user_name>')
def timelinePage_Get(user_name):
    return render_template('timeline_page.html', user_name=user_name, do_target="Timeline", request_path="timeline")

@app.route('/tag/<tag_name>')
def tagPage_Get(tag_name):
    return render_template('tag_page.html', tag_name=tag_name)

@app.route('/tag/<tag_name>.json')
def tagPage_Get_Rest(tag_name):
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetTagTweetFormated("#" + tag_name, limit, since_time)
    return json.dumps(tweet_list)

@app.route('/user_setting/')
def userSettingsPage_Get():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        return render_template('user_setting_page.html', error="authenticate required")
    key_list = world.GetUserAPIKeyListByName(user_name)
    return render_template('user_setting_page.html', user=user_name, key_list=key_list)

@app.route('/user_setting/key/<key>.json', methods=['DELETE', 'POST'])
def userSettingsPage_DeleteKey(key):
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    if world.DeleteUserAPIKeyByName(user_name, key):
        return json.dumps({'result': 'ok'})
    abort(500)

@app.route('/user_setting/create_new_key.json', methods=['POST'])
def userSettingsPage_CreateNewKey():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    new_key = world.CreateUserAPIKeyByName(user_name)
    if new_key is None or 'key' not in new_key:
        abort(401)
    return json.dumps({'result': 'ok', 'key': new_key['key']})

@app.route('/post.json', methods=['POST'])
def postTweet():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    if 'text' not in request.json:
        abort(400)
    text = request.json['text']
    reply_to = None
    if 'reply_to' in request.json:
        reply_to = request.json['reply_to']
    user_node = world.GetUserNode(user_name)
    if user_node is None:
        abort(501)
    print "reply_to: ", reply_to
    tweet_node = world.Tweet(user_node, tweet_string=text, reply_to=reply_to)
    tweet_dic = world.ConvertTweetNodeToHumanReadableDictionary(tweet_node)
    tweet_dic.update({'user': user_name, 'id': tweet_node._id})
    # 怪しく result ok の入っていない状態でstreaming側に渡します
    watchDogManager.UpdateTweet(text, tweet_dic)
    tweet_dic.update({'result': 'ok'})
    return json.dumps(tweet_dic)

@app.route('/follow.json', methods=['POST'])
def followUser():
    follower_user_name = GetAuthenticatedUserName()
    if follower_user_name is None:
        abort(401)
    if request.json is None or 'user_name' not in request.json:
        abort(400, {'result': 'error', 'description': 'target user name is not defined. You must set "user_name" field.'})
    target_user_name = request.json['user_name']
    if not world.FollowUserByName(follower_user_name, target_user_name):
        return abort(500, {'result': 'error', 'description': 'follow failed.'})
    return json.dumps({'result': 'ok'})

@app.route('/unfollow.json', methods=['POST', 'DELETE'])
def unfollowUser():
    follower_user_name = GetAuthenticatedUserName()
    if follower_user_name is None:
        abort(401)
    if request.json is None or 'user_name' not in request.json:
        abort(400, {'result': 'error', 'description': 'target user name is not defined. You must set "user_name" field.'})
    target_user_name = request.json['user_name']
    if not world.UnFollowUserByName(follower_user_name, target_user_name):
        abort(500, {'result': 'error', 'description': 'unfollow failed.'})
    return json.dumps({'result': 'ok'})

@app.route('/signup', methods=['GET'])
def signupPage():
    user_name = GetAuthenticatedUserName()
    if user_name is not None:
        return redirect('/user/%s' % user_name)
    return render_template('signup.html')

@app.route('/signup', methods=['POST'])
def signupProcess():
    user_name = request.form['user_name']
    password = request.form['password']
    user_node = world.GetUserNode(user_name)
    if user_node is not None:
        return render_template('signup.html', error="user %s is already registerd." % user_name)
    if world.AddUser(user_name, password):
        session_key = world.UpdateUserSessionKey(user_name)
        if session_key is None:
            return render_template('signin.html', error="user %s created. but session create failed." % user_name)
        session['user_name'] = user_name
        session['session_key'] = session_key
        return redirect('/timeline/%s' % user_name)
    return render_template('signup.html', error="create user %s failed. unknown error." % user_name)

@app.route('/signin', methods=['GET'])
def signinPage():
    user_name = GetAuthenticatedUserName()
    if user_name is not None:
        return redirect('/user/%s' % user_name)
    return render_template('signin.html')

@app.route('/signin', methods=['POST'])
def signinProcess():
    user_name = request.form['user_name']
    password = request.form['password']
    if world.CheckUserPasswordIsValid(user_name, password):
        session_key = world.UpdateUserSessionKey(user_name)
        if session_key is None:
            return render_template('signin.html', error="undefined error. (CreateSessionKey)")
        session['user_name'] = user_name
        session['session_key'] = session_key
        return redirect('/timeline/%s' % user_name)
    return render_template('signin.html', error="invalid password or username")

@app.route('/signout')
def signoutPage():
    session.pop('session_key', None)
    return redirect(url_for('topPage'))

@app.route('/user_name_list.json')
def userNameList():
    return json.dumps(world.GetUserNameList())

def RegexpMatchWait(queue):
    if queue.empty():
        gevent.sleep(1)
        return ''
    (tweet_dic, match_result) = queue.get()
    result_dic = tweet_dic.copy()
    result_dic['match_result'] = match_result
    logging.info('waiting tweet text got: %s' % str(result_dic))
    return "%s\n" % json.dumps(result_dic)

@app.route('/stream/regexp.json', methods=['POST'])
def streamed_response():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    if 'regexp' not in request.json:
        abort(400)
    regexp = request.json['regexp']
    queue = gevent.queue.Queue()
    regist_id = watchDogManager.RegisterWatcher_RegexpMatch(regexp, queue)
    print "accept streaming client. user: %s" % user_name
    def generate():
        while True:
            try:
                yield RegexpMatchWait(queue)
            except IOError:
                # クライアント側が接続を切ると、
                # MatchWait で何かを書き込もうとした時に
                # BrokenPipe(IOError) が発生するはず
                # ……なのだけれど、IOError では catch できないのは何故？
                print "IOError detected. unregister watcher"
                watchDogManager.UnregisterWatcher(regist_id)
                break
    #return Response(generate(), mimetype='application/json; charset=utf-8')
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    #app.run('0.0.0.0', port=1000, debug=True)
    #app.run('::', port=8000, debug=True)
    http_server = WSGIServer(('::', 8000), app)
    http_server.serve_forever()
