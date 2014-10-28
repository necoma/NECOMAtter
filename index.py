#!/usr/bin/python -u
# coding: utf-8

import sys,os
import logging

from flask import Flask, flash, redirect, url_for, session, request, jsonify, g, render_template, stream_with_context, Response, abort
from NECOMAtter import NECOMAtter
import time
import json
import re
import gevent
import signal
from gevent.wsgi import WSGIServer
import gevent.queue
from gevent import Timeout
from werkzeug.utils import secure_filename

#from OpenSSL import SSL
#ssl_context = SSL.Context(SSL.SSLv23_METHOD)
#ssl_context.use_privatekey_file('ssl_keys/NECOMAtter_server.key')
#ssl_context.use_certificate_file('ssl_keys/NECOMAtter_server.crt')

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig()

app = Flask(__name__)
app.secret_key = 'f34b38b053923d1cb202fc5b9e8d2614'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

world = NECOMAtter("http://localhost:7474")
force_scheme = "https"

# StreamingWatcherManager で heartbeat を叩くための greenlet method
def HeartBeatKicker(watcher):
    while True:
        gevent.sleep(25)
        watcher.SendHeartbeat()

# streaming API で監視を走らせる時のwatcherを管理するclass
# ストリーミングのクライアントが現れる毎にwatchdogリストに登録する
# 登録されたものはクライアント側で何らかのエラーがあったら登録を削除する
class StreamingWatcherManager():
    def __init__(self):
        self.uniq_id = 0
        self.regexp_watcher_list = {}
        # タイムアウトで self.SendHeartbeat() を呼ぶための greenlet を作る
        self.heartbeat_greenlet = gevent.spawn(HeartBeatKicker, self)

    def __del__(self):
        if self.heartbeat_greenlet is not None:
            self.heartbeat_greenlet.join()

    def RegisterWatcher_RegexpMatch(self, regexp_pattern, queue, user_name, description="undefined"):
        regist_id = self.uniq_id
        self.uniq_id += 1
        self.regexp_watcher_list[regist_id] = {'re_prog': re.compile(regexp_pattern),
                'queue': queue,
                'user_name': user_name,
                'description': world.EscapeForXSS(description)
                }
        return regist_id

    def UnregisterWatcher(self, delete_id):
        del self.regexp_watcher_list[delete_id]

    def SendHeartbeat(self):
        for regexp_watcher in self.regexp_watcher_list.values():
            queue = regexp_watcher['queue']
            #print "send heartbeat to %s (%s)" % (regexp_watcher['user_name'], regexp_watcher['description'])
            queue.put_nowait((None, None))

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
            print "streaming hit for %s (%s)" % (regexp_watcher['user_name'], regexp_watcher['description'])
            queue.put_nowait((tweet_dic, match_result))

    def GetWatcherListNum(self):
        return len(self.regexp_watcher_list)

    # streaming API で監視中のユーザ情報のリストを辞書形式で返します
    def GetWatcherDescriptionList(self):
        description_list = []
        for regexp_client in self.regexp_watcher_list.values():
            description = {}
            description['user_name'] = regexp_client['user_name']
            description['description'] = regexp_client['description']
            description_list.append(description)
        return description_list

watchDogManager = StreamingWatcherManager()

# GET か POST(JSON) の場合で key の値を取り出します。
# int や float に変換するのは自前でやってください。
def GetValueFromRequest(request, key):
    if (request.json is not None and
        key in request.json):
        return request.json[key]
    if key in request.values:
        return request.values[key]
    return None

# NECOMAtter で認証完了しているユーザ名を取得します。
# 認証完了していない場合にはNoneを返します
def GetAuthenticatedUserName():
    user_name = session.get('user_name')
    session_key = session.get('session_key')
    if world.CheckUserSessionKeyIsValid(user_name, session_key):
        return user_name
    if ( request.method == 'POST' and
        request.json is not None and
        'user_name' in request.json and
        'api_key' in request.json and
        world.CheckUserAPIKeyByName(request.json['user_name'], request.json['api_key']) ):
            return request.json['user_name']
    # 失敗したのでcookie上のセッションキーは消しておきます
    session.pop('session_key', None)
    return None

@app.after_request
def after_request(responce):
    # これを書けばContent-Security-Policy が効くようになる
    # 参考: http://blog.hash-c.co.jp/2013/12/Content-Security-Policy-CSP.html
    #responce.headers.add("Content-Security-Policy", "default-src 'self'")
    responce.headers.add("X-Content-Type-Options", "nosniff")
    responce.headers.add("X-Frame-Options", "SAMEORIGIN")
    return responce

@app.route('/')
def topPage():
    return render_template('index.html')

@app.route('/favicon.ico')
def faviconPage():
    return redirect('/static/favicon.ico')

@app.route('/user/<user_name>.json')
def userPage_Get_Rest(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetUserTweetFormatted(user_name, query_user_name=auth_user_name, limit=limit, since_time=since_time)
    return json.dumps(tweet_list)

# ユーザページ
@app.route('/user/<user_name>')
def userPage_Get(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('timeline_page.html', user_name=user_name, do_target="Tweet", request_path="user")

# ツイートの削除
@app.route('/tweet/<int:tweet_id>', methods=['DELETE'])
def userTweet_Delete(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    result = world.DeleteTweetByTweetID(tweet_id, auth_user_name)
    if result == False:
        abort(404)
    return json.dumps({"result": "ok", "description": "tweet %d deleted." % (tweet_id, )})

# ツイートの削除
@app.route('/tweet/<int:tweet_id>_delete.json', methods=['GET'])
def userTweet_Delete_Get(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    result = world.DeleteTweetByTweetID(tweet_id, auth_user_name)
    if result == False:
        abort(404)
    return json.dumps({"result": "ok", "description": "tweet %d deleted." % (tweet_id, )})

# 個別のツイートページ
@app.route('/tweet/<int:tweet_id>')
def userTweet_Get(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('tweet_tree.html', tweet_id=tweet_id)

# 個別のツイートページ
@app.route('/tweet/<int:tweet_id>_tree')
def userTweet_Get_Tree(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('tweet_tree.html', tweet_id=tweet_id)

# 対象のtweetID の tweet のみを取得します
@app.route('/tweet/<int:tweet_id>.json')
def userTweet_Get_Rest(tweet_id):
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    return json.dumps(world.GetTweetNodeFromIDFormatted(tweet_id, query_user_name=user_name))

# 対象のtweetID の返信関係の木構造を返します
@app.route('/tweet/<int:tweet_id>_tree.json')
def userTweetTree_Get_Rest(tweet_id):
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    tweet_list = world.GetParentTweetAboutTweetIDFormatted(tweet_id, query_user_name=user_name)
    tweet_list.extend(world.GetTweetNodeFromIDFormatted(tweet_id, query_user_name=user_name))
    tweet_list.extend(world.GetChildTweetAboutTweetIDFormatted(tweet_id, query_user_name=user_name))
    return json.dumps(tweet_list)

# 対象のツイートの親(replyしている先)を辿って返します
@app.route('/tweet/<int:tweet_id>_parent.json')
def userTweetTreeParent_Get_Rest(tweet_id):
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetParentTweetAboutTweetIDFormatted(tweet_id, user_name, limit, since_time)
    return json.dumps(tweet_list)

# 対象のツイートの子(replyしてきたtweet)を辿って返します
@app.route('/tweet/<int:tweet_id>_child.json')
def userTweetTreeChild_Get_Rest(tweet_id):
    query_user_name = GetAuthenticatedUserName()
    if query_user_name is None:
        abort(401)
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetChildTweetAboutTweetIDFormatted(tweet_id, query_user_name, limit, since_time)
    return json.dumps(tweet_list)

# 対象のユーザがフォローしているユーザ名のリストを返します
@app.route('/user/<user_name>/followed_user_name_list.json')
def userFollowedGet(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    return json.dumps(world.GetUserFollowedUserNameList(user_name))

# ユーザのタイムラインを返します
@app.route('/timeline/<user_name>.json', methods=['GET', 'POST'])
def timelinePage_Get_Rest(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    query_user_name = auth_user_name
    since_time = GetValueFromRequest(request, 'since_time')
    limit = GetValueFromRequest(request, 'limit')
    if since_time is not None:
        since_time = float(since_time)
    if limit is not None:
        limit = int(limit)
    tweet_list = world.GetUserTimelineFormatted(user_name, query_user_name, limit=limit, since_time=since_time)
    return json.dumps(tweet_list)

# ユーザのタイムラインページ
@app.route('/timeline/<user_name>')
def timelinePage_Get(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('timeline_page.html', user_name=user_name, do_target="Timeline", request_path="timeline")

# すべてのユーザのタイムラインを返します
@app.route('/alluser/timeline.json')
def alluserTimelinePage_Get_Rest():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    query_user_name = GetAuthenticatedUserName()
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetAllUserTimelineFormatted(query_user_name, limit, since_time)
    return json.dumps(tweet_list)

# すべてのユーザのタイムラインページ
@app.route('/alluser/timeline')
def alluserTimelinePage_Get():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('all_user_timeline_page.html')

# タグページ
@app.route('/tag/<tag_name>')
def tagPage_Get(tag_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('tag_page.html', tag_name=tag_name, title=tag_name)

# タグのタイムラインを返します
@app.route('/tag/<tag_name>.json')
def tagPage_Get_Rest(tag_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetTagTweetFormatted("#" + world.EscapeForXSS(tag_name), auth_user_name, limit, since_time)
    return json.dumps(tweet_list)

# ユーザ設定ページ
@app.route('/user_setting/')
def userSettingsPage_Get():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        return render_template('user_setting_page.html', error="authenticate required", is_can_create_user=False)
    key_list = world.GetUserAPIKeyListByName(user_name)
    icon_url = world.GetUserAbaterIconURLByName(user_name)
    return render_template('user_setting_page.html', user=user_name, key_list=key_list, icon_url=icon_url, is_can_create_user=world.IsUserCanCreateUser(user_name))

# API Key の削除
@app.route('/user_setting/key/<key>.json', methods=['DELETE', 'POST'])
def userSettingsPage_DeleteKey(key):
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    if world.DeleteUserAPIKeyByName(user_name, key):
        return json.dumps({'result': 'ok'})
    abort(500)

# 新しいAPI Keyの生成
@app.route('/user_setting/create_new_key.json', methods=['POST'])
def userSettingsPage_CreateNewKey():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    new_key = world.CreateUserAPIKeyByName(user_name)
    if new_key is None or 'key' not in new_key:
        abort(401)
    return json.dumps({'result': 'ok', 'key': new_key['key']})

# tweet します
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
    list_owner_name = None
    if 'list_owner_name' in request.json:
        list_owner_name = request.json['list_owner_name']
    target_list = None
    if 'target_list' in request.json:
        target_list = request.json['target_list']
    tweet_dic = world.TweetByName(user_name, tweet_string=text, reply_to=reply_to, list_owner_name=list_owner_name, target_list=target_list)
    # 怪しく result ok の入っていない状態でstreaming側に渡します
    watchDogManager.UpdateTweet(text, tweet_dic)
    tweet_dic.update({'result': 'ok'})
    return json.dumps(tweet_dic)

# フォローします
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

# フォローを外します
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

# ユーザ生成ページ
@app.route('/signup', methods=['GET'])
def signupPage():
    user_name = GetAuthenticatedUserName()
    if user_name is not None:
        return redirect(url_for('userPage_Get', user_name=user_name, _external=True, _scheme=force_scheme))
    return render_template('signup.html')

# ユーザ生成ページ(POSTされた後の実際の生成部分)
@app.route('/signup', methods=['POST'])
def signupProcess():
    # 一旦サインアップページは動かないことにします
    return render_template('signup.html', error="user sign up page is closed.")
    user_name = request.form['user_name']
    password = request.form['password']
    user_node = world.GetUserNode(user_name)
    if user_node is not None:
        return render_template('signup.html', error="user %s is already registerd." % user_name)
    result = world.AddUser(user_name, password)
    if result[0] == True:
        session_key = world.UpdateUserSessionKey(user_name)
        if session_key is None:
            return render_template('signin.html', error="user %s created. but session create failed." % user_name)
        session['user_name'] = user_name
        session['session_key'] = session_key
        return redirect(url_for("timelinePage_Get", user_name=user_name, _external=True, _scheme=force_scheme))
    return render_template('signup.html', error="create user %s failed. %s" % (user_name, result[1]))

# サインインページ
@app.route('/signin', methods=['GET'])
def signinPage():
    user_name = GetAuthenticatedUserName()
    if user_name is not None:
        return redirect(url_for('userPage_Get', user_name=user_name, _external=True, _scheme=force_scheme))
    return render_template('signin.html')

# サインインページ(POSTされた後の実際のサインイン部分)
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
        return redirect(url_for("topPage", _external=True, _scheme=force_scheme))
    return render_template('signin.html', error="invalid password or username")

# サインアウトページ. このページが開いたら強制的にサインアウトさせます
@app.route('/signout')
def signoutPage():
    user_name = GetAuthenticatedUserName()
    if user_name is not None:
        # DB側のセッションキーも消しておきます
        world.DeleteUserSessionKey(user_name)
    session.pop('session_key', None)
    return redirect(url_for('topPage', _scheme=force_scheme, _external=True))

# 登録されているユーザ名をリストで返します
@app.route('/user_name_list.json')
def userNameList():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    return json.dumps(world.GetUserNameList())

# 現在稼働中のstreaming API client の情報リストを出力します
@app.route('/stream/client_list.json')
def streamClientList_Rest():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    return json.dumps(watchDogManager.GetWatcherDescriptionList())

# 現在稼働中のstreaming API client の情報リストページ
@app.route('/stream/client_list')
def streamClientList():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('stream_client.html')

# streaming AIP での正規表現マッチの待機用関数
def RegexpMatchWait(queue):
    if queue.empty():
        gevent.sleep(1)
        return ''
    (tweet_dic, match_result) = queue.get()
    if tweet_dic is None or match_result is None:
        return "\n"
    result_dic = tweet_dic.copy()
    result_dic['match_result'] = match_result
    logging.info('waiting tweet text got: %s' % str(result_dic))
    return "%s\n" % json.dumps(result_dic)

# streaming API. 正規表現でマッチしたtweetがあるたびに
# そのtweetをjson形式で送信します.
# 接続してきた時点までのtweetについては特に何もしません
@app.route('/stream/regexp.json', methods=['POST'])
def streamed_response():
    user_name = GetAuthenticatedUserName()
    if user_name is None:
        abort(401)
    if 'regexp' not in request.json:
        abort(400)
    regexp = request.json['regexp']
    description = None
    if 'description' in request.json:
        description = request.json['description']
    queue = gevent.queue.Queue()
    regist_id = watchDogManager.RegisterWatcher_RegexpMatch(regexp, queue, user_name, description)
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
    res = Response(generate(), mimetype='text/event-stream')
    res.headers.add('X-Accel-Buffering', 'no')
    return res

#
# LIST機能周り
#
# list を新しく作成します
@app.route("/list/<user_name>.json", methods=['POST'])
def add_new_list_JSON():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401, {'result': 'error', 'description': 'authentication required'})
    if auth_user_name != user_name:
        abort(400, {'result': 'error', 'description': 'only owner-user can add list.'})
    if 'list_name' not in request.json:
        abort(400, {'result': 'error', 'description': 'list_name required'})
    list_name = request.json['list_name']
    if list_name is None or len(list_name) <= 0:
        abort(500, {'result': 'error', 'description': 'invalid list_name'})
    description = request.json['description']
    hidden = False
    if 'hidden' in request.json and request.json['hidden']:
        hidden = True
    list_node = world.CreateOrGetListNodeFromName(auth_user_name, list_name, description=description, hidden=hidden)
    if list_node is None:
        abort(500, {'result': 'error', 'description': 'list create error'})
    return json.dumps({'result': 'ok', 'description': 'list "%s" created.' % (list_name, )})

# リストに含まれるユーザのリストを取得します
@app.route('/list/<user_name>/<list_name>.json', methods=['GET'])
def list_user_list_get(target_user, list_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401, {'result': 'error', 'description': 'authentication required'})
    user_list = world.GetListUserListByName(user_name, list_name, auth_user_name)
    if user_list is None:
        abort(500, {'result': 'error', 'description': 'user list fetch failed.'})
    return json.dumps({'result': 'ok', 'user_list': user_list})

# リストにユーザを追加します
@app.route('/list/<user_name>/<list_name>.json', methods=['POST'])
def list_add(user_name, list_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401, {'result': 'error', 'description': 'authentication required'})
    if auth_user_name != user_name:
        abort(400, {'result': 'error', 'description': 'only owner-user can add user to list.'})
    if 'target_user' not in request.json or 'list_name' not in request.json:
        abort(400, {'result': 'error', 'description': 'target_user and list_name required'})
    target_user = request.json['target_user']
    if world.AddNodeToListByName(user_name, list_name, target_user):
        return json.dumps({'result': 'ok', 'list_name': list_name})
    abort(500, {'result': 'error', 'description': 'list add failed.'})

# リストからユーザを削除します(本当なら/list_delete/.... ではなくて
#/list/<user_name>/<list_name>/<delete_user_name> へのDELETEです)
#POSTでないと駄目な場合にこれを使います
@app.route('/list_delete/<user_name>/<list_name>/<target_user_name>.json', methods=['POST'])
def list_user_delete_post(user_name, list_name, target_user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401, {'result': 'error', 'description': 'authentication required'})
    if auth_user_name != user_name:
        abort(400, {'result': 'error', 'description': 'only owner-user can modify list.'})
    if world.UnfollowUserFromListByName(user_name, list_name, target_user_name):
        return json.dumps({'result': 'ok', 'list_name': list_name,
            "delete_user": target_user})
    abort(500, {'result': 'error', 'description':
        'user "%s" delete from list "%s" failed.' % (target_user, list_name)})

# リストからユーザを削除します
@app.route('/list/<user_name>/<list_name>/<target_user_name>.json', methods=['DELETE'])
def list_user_delete_rest(user_name, list_name, target_user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401, {'result': 'error', 'description': 'authentication required'})
    if auth_user_name != user_name:
        abort(400, {'result': 'error', 'description': 'only owner-user can modify list.'})
    if world.UnfollowUserFromListByName(user_name, list_name, target_user_name):
        return json.dumps({'result': 'ok', 'list_name': list_name,
            "delete_user": target_user_name})
    abort(500, {'result': 'error', 'description':
        'user "%s" delete from list "%s" failed.' % (target_user_name, list_name)})

# ユーザの定義したリスト名を取得します
#TODO: 非公開リストに未対応
@app.route('/list/<user_name>.json', methods=['GET'])
def list_get(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    list_list = world.GetUserListListFormatted(user_name, auth_user_name)
    if list_list is None:
        abort(500, {'result': 'error', 'description': 'user list get failed.'})
    return json.dumps({'result': 'ok', 'list': list_list})

# ユーザのリストにあるユーザのリストのタイムラインを取得します
#TODO: 非公開リストに未対応
@app.route('/list_timeline/<user_name>/<list_name>.json', methods=['GET'])
def list_user_get(user_name, list_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    tweet_list = world.GetListTimelineFormatted(user_name, list_name, auth_user_name, limit, since_time)
    return json.dumps(tweet_list)

# リストのタイムラインページ
@app.route('/list_timeline/<user_name>/<list_name>', methods=['GET'])
def list_user_page(user_name, list_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('timeline_page.html', user_name="%s/%s" %(user_name, list_name), list_name="list")

# ユーザのリストのリストページ
@app.route('/list/<user_name>', methods=['GET'])
def list_user_page_(user_name):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('user_list_list_page.html', user_name=user_name)

# tweet に STAR をつける
@app.route('/tweet/<int:tweet_id>/add_star.json', methods=['POST', 'PUT'])
def add_star_post(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    if world.AddStarByName(auth_user_name, tweet_id) == True:
        return json.dumps({'result': 'ok', 'description': 'add star to tweetID %d' % tweet_id})
    abort(400, {'result': 'error', 'description': 'add star to tweetID %d failed.' % tweet_id})
    
# tweet から STAR を外す
@app.route('/tweet/<int:tweet_id>/delete_star.json', methods=['POST', 'PUT'])
def delete_star_post(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    if world.DeleteStarByName(auth_user_name, tweet_id) == True:
        return json.dumps({'result': 'ok', 'description': 'delete star to tweetID %d' % tweet_id})
    abort(400, {'result': 'error', 'description': 'delete star to tweetID %d failed.' % tweet_id})

# tweet を RETWEET する
@app.route('/tweet/<int:tweet_id>/retweet.json', methods=['POST', 'PUT'])
def retweet_post(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    if world.RetweetByName(auth_user_name, tweet_id) == True:
        return json.dumps({'result': 'ok', 'description': 'retweet tweetID %d success.' % tweet_id})
    abort(400, {'result': 'error', 'description': 'retweet tweetID %d failed.' % tweet_id})
    
# RETWEET を取り消す
@app.route('/tweet/<int:tweet_id>/retweet_cancel.json', methods=['POST', 'PUT'])
def retweet_cancel_post(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    if world.UnRetweetByName(auth_user_name, tweet_id) == True:
        return json.dumps({'result': 'ok', 'description': 'retweet cancel tweetID %d success.' % tweet_id})
    abort(400, {'result': 'error', 'description': 'retweet cancel tweetID %d failed.' % tweet_id})

# retweet したユーザのリスト を取り消す
@app.route('/tweet/<int:tweet_id>/retweet_user_list.json', methods=['GET'])
def retweet_users_get_json(tweet_id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    retweet_user_list = world.GetTweetRetweetUserInfoFormatted(tweet_id)
    if retweet_user_list is None:
        abort(500, {'result': 'error', 'description': 'get retweet users failed.'})
    return json.dumps({'result': 'ok', 'retweet_user_list': retweet_user_list })

# ユーザのアイコンをアップロードする
@app.route('/user/icon_upload.html', methods=["POST"])
def post_user_icon_image():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        return render_template('user_setting_page.html', error="authentication required", is_can_create_user=world.IsUserCanCreateUser(auth_user_name))
    if 'icon' not in request.files:
        return render_template('user_setting_page.html', error="post data invalid", is_can_create_user=world.IsUserCanCreateUser(auth_user_name))
    file = request.files['icon']
    key_list = world.GetUserAPIKeyListByName(auth_user_name)
    icon_url = world.GetUserAbaterIconURLByName(auth_user_name)
    if not world.UpdateAbaterIconByName(auth_user_name, file):
        return render_template('user_setting_page.html', error="icon save error", user=auth_user_name, key_list=key_list, icon_url=icon_url, is_can_create_user=world.IsUserCanCreateUser(auth_user_name))
    return redirect(url_for('userSettingsPage_Get', _scheme=force_scheme, _external=True))
    #return render_template('user_setting_page.html', user=auth_user_name, key_list=key_list, icon_url=icon_url, is_can_create_user=world.IsUserCanCreateUser(auth_user_name))

# NECOMAtome json
@app.route('/matome/<int:id>.json', methods=['GET', 'POST'])
def necomatome_Get_Json(id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    since_time = None
    limit = None
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    matome_tweet_list = world.GetNECOMAtomeTweetListByIDFormatted(id, query_user_name=auth_user_name, limit=limit, since_time=since_time)
    return json.dumps(matome_tweet_list)

# NECOMAtome ページ
@app.route('/matome/<int:id>')
def necomatome_Get(id):
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    return render_template('necomatome_page.html', matome_id=id)

# NECOMAtome 作成
@app.route('/matome.json', methods=['POST'])
def necomatome_POST():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    matome_id = 0
    tweet_id_list = []
    description = None
    if 'tweet_id_list' in request.json:
        tweet_id_list = request.json['tweet_id_list']
    if 'description' in request.json:
        description = request.json['description']
    if len(tweet_id_list) <= 0:
        abort(400, {'result': 'error', 'description': 'tweet_id_list not found.'})
    if len(description) <= 0:
        abort(400, {'result': 'error', 'description': 'description not found.'})
    matome_id = world.CreateNewNECOMAtomeByName(auth_user_name, tweet_id_list, description)
    if matome_id < 0:
        abort(400, {'result': 'error', 'description': 'create NECOMAtome failed.'})
    return json.dumps({'result': 'ok', 'matome_id': matome_id})

# 検索
@app.route('/search.json', methods=['GET', 'POST'])
def search_json_POST():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    limit = None
    since_time = None
    search_text = ""
    if 'since_time' in request.values:
        since_time = float(request.values['since_time'])
    if 'limit' in request.values:
        limit = int(request.values['limit'])
    if 'search_text' in request.values:
        search_text = request.values['search_text']
    search_text_list = search_text.split(' ')
    return json.dumps(world.SearchTweetFormatted(search_text_list, query_user_name=auth_user_name, since_time=since_time, limit=limit))

# 検索ページ
@app.route('/search', methods=['GET'])
def search_Page():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))
    limit = None
    search_text = request.args.get('search_text');
    if search_text is None:
        search_text = ""
    return render_template('search_page.html', title=world.EscapeForXSS(search_text))

# 検索ページ
@app.route('/n6/query.json', methods=['GET'])
def n6_query_json():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    return json.dumps(world.GetN6CompatQueryFormatted(request.args))

# パスワードの変更
@app.route('/change_password', methods=['POST'])
def passwordChangePage():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        if session.get('user_name') is not None:
            session.pop('session_key', None)
            return redirect(url_for('signinPage', _external=True, _scheme=force_scheme))
        return redirect(url_for('signoutPage', _external=True, _scheme=force_scheme))

    key_list = world.GetUserAPIKeyListByName(auth_user_name)
    icon_url = world.GetUserAbaterIconURLByName(auth_user_name)

    old_password = None
    new_password_1 = None
    new_password_2 = None
    if 'old_password' in request.values:
        old_password = request.values['old_password']
    if 'password' in request.values:
        new_password_1 = request.values['password']
    if 'password_2' in request.values:
        new_password_2 = request.values['password_2']
    if new_password_1 != new_password_2:
        return render_template('user_setting_page.html', user=auth_user_name, key_list=key_list, icon_url=icon_url, error="password verify failed.", is_can_create_user=world.IsUserCanCreateUser(auth_user_name))
    if world.UpdateUserPassword(auth_user_name, old_password, new_password_1) == False:
        return render_template('user_setting_page.html', user=auth_user_name, key_list=key_list, icon_url=icon_url, error="password change failed.", is_can_create_user=world.IsUserCanCreateUser(auth_user_name))

    # 再度ログインさせるためにセッションを切ります
    session.pop('session_key', None)
    # DB側のセッションキーも消しておきます
    world.DeleteUserSessionKey(auth_user_name)

    return redirect(url_for('topPage', _scheme=force_scheme, _external=True))
    #return render_template('user_setting_page.html', user=auth_user_name, key_list=key_list, icon_url=icon_url, success="password changed.", is_can_create_user=world.IsUserCanCreateUser(auth_user_name))

# ユーザの追加
@app.route('/add_user.json', methods=['POST', 'PUT'])
def AddUser_Json():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        abort(401)
    new_user_name = request.json['new_user_name']
    new_user_password = request.json['new_user_password']
    if new_user_name is None or new_user_password is None or new_user_name == "" or new_user_password == "":
        abort(400)
    result =  world.AddUserWithAuthCheckByName(auth_user_name, new_user_name, new_user_password)
    if result[0] != True:
        return json.dumps({'result': 'error', 'description': result[1]}), 400
    return json.dumps({'result': 'ok'})

# mewを公開状態にします
@app.route("/open_to_public.json", methods=['POST'])
def OpenToPublic_Json():
    auth_user_name = GetAuthenticatedUserName()
    if auth_user_name is None:
        return json.dumps({'result': 'error', 'description': "unautholized"}), 401
    mew_id = request.json['id']
    result =  world.OpenToPublicCensordMew(mew_id)
    if result[0] != True:
        return json.dumps({'result': 'error', 'description': result[1]}), 400
    return json.dumps({'result': 'ok'})

def StartHttp(host, port, app):
    http_server = WSGIServer((host, port), app)
    http_server_greenlet = gevent.spawn(http_server.start)
    return http_server_greenlet

def StartHttps(host, port, app, keyFile, certFile):
    https_server = WSGIServer((host, port), app, keyfile=keyFile, certfile=certFile)
    http_server_greenlet = gevent.spawn(https_server.start)
    return http_server_greenlet

if __name__ == '__main__':
    port = 80
    if len(sys.argv) > 1 and int(sys.argv[1]) > 1024:
        port = int(sys.argv[1])

    servers = []
    if len(sys.argv) > 3:
        ssl_key = sys.argv[2]
        ssl_cert = sys.argv[3]
        if port != 80:
            servers.append(StartHttps('::', port + 443, app, ssl_key, ssl_cert))
            servers.append(StartHttp('0.0.0.0', port + 443, app))
        else:
            servers.append(StartHttps('::', 443, app, ssl_key, ssl_cert))
            servers.append(StartHttp('0.0.0.0', 443, app))
    else:
        force_scheme = "http"

    servers.append(StartHttp('::', port, app))
    servers.append(StartHttp('0.0.0.0', port, app))

    gevent.sleep(3)
    gevent.sleep(60*60*24*365*3)
    gevent.joinall(servers)
