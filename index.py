#!/usr/bin/python

import sys,os
import logging

from flask import Flask, flash, redirect, url_for, session, request, jsonify, g, render_template, stream_with_context, Response, abort
from NECOMATter import NECOMATter
import time
import json

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'f34b38b053923d1cb202fc5b9e8d2614'

world = NECOMATter("http://localhost:7474")

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

@app.route('/user/<user_name>/<unix_time>')
def userTweet_Get(user_name, unix_time):
    # TODO: ユーザのツイートを個別で見られるページを作る予定……    
    return render_template('one_tweet.html', user_name=user_name)

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
    user_name = session.get('user_name')
    if user_name is None or user_name == "":
        return render_template('user_setting_page.html', error="authenticate required")
    key_list = world.GetUserAPIKeyListByName(user_name)
    return render_template('user_setting_page.html', user=user_name, key_list=key_list)

@app.route('/user_setting/key/<key>.json', methods=['DELETE', 'POST'])
def userSettingsPage_DeleteKey(key):
    user_name = session.get('user_name')
    if user_name is None or user_name == "":
        abort(401)
    if world.DeleteUserAPIKeyByName(user_name, key):
        return json.dumps({'result': 'ok'})
    abort(500)

@app.route('/user_setting/create_new_key.json', methods=['POST'])
def userSettingsPage_CreateNewKey():
    user_name = session.get('user_name')
    if user_name is None or user_name == "":
        abort(401)
    new_key = world.CreateUserAPIKeyByName(user_name)
    if new_key is None or 'key' not in new_key:
        abort(401)
    return json.dumps({'result': 'ok', 'key': new_key['key']})

@app.route('/post.json', methods=['POST'])
def postTweet():
    #user_name = request.json['user_name']
    user_name = session.get('user_name')
    text = request.json['text']
    user_node = world.GetUserNode(user_name)
    if user_node is None:
        return json.dumps({'result': "error", 'description': "user %s is not registerd." % user_name})
    tweet_node = world.Tweet(user_node, text)
    tweet_dic = world.ConvertTweetNodeToHumanReadableDictionary(tweet_node)
    tweet_dic.update({'result': 'ok'})
    return json.dumps(tweet_dic)

@app.route('/follow.json', methods=['POST'])
def followUser():
    follower_user_name = session.get('user_name')
    if follower_user_name is None:
        return json.dumps({'result': 'error', 'description': 'sign in required.'})
    if request.json is None or 'user_name' not in request.json:
        return json.dumps({'result': 'error', 'description': 'target user name is not defined. You must set "user_name" field.'})
    target_user_name = request.json['user_name']
    if not world.FollowUserByName(follower_user_name, target_user_name):
        return json.dumps({'result': 'error', 'description': 'follow failed.'})
    return json.dumps({'result': 'ok'})

@app.route('/unfollow.json', methods=['POST', 'DELETE'])
def unfollowUser():
    follower_user_name = session.get('user_name')
    if follower_user_name is None:
        return json.dumps({'result': 'error', 'description': 'sign in required.'})
    if request.json is None or 'user_name' not in request.json:
        return json.dumps({'result': 'error', 'description': 'target user name is not defined. You must set "user_name" field.'})
    target_user_name = request.json['user_name']
    if not world.UnFollowUserByName(follower_user_name, target_user_name):
        return json.dumps({'result': 'error', 'description': 'unfollow failed.'})
    return json.dumps({'result': 'ok'})

@app.route('/signup', methods=['GET'])
def signupPage():
    user_name = session.get('user_name')
    session_key = session.get('session_key')
    if world.CheckUserSessionKeyIsValid(user_name, session_key):
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
            return render_template('signup.html', error="user %s created. but session create failed." % user_name)
        session['user_name'] = user_name
        session['session_key'] = session_key
        return redirect('/timeline/%s' % user_name)
    return render_template('signup.html', error="create user %s failed. unknown error." % user_name)

@app.route('/signin', methods=['GET'])
def signinPage():
    user_name = session.get('user_name')
    session_key = session.get('session_key')
    if world.CheckUserSessionKeyIsValid(user_name, session_key):
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

def CheckNewColumn():
    time.sleep(1)
    yield "sleep.\n"

@app.route('/user_name_list.json')
def userNameList():
    return json.dumps(world.GetUserNameList())

@app.route('/stream')
def streamed_response():
    def generate():
        while True:
            yield CheckNewColumn()
    return Response(stream_with_context(generate()))

if __name__ == '__main__':
    #app.run('0.0.0.0', port=1000, debug=True)
    app.run('::', port=8000, debug=True)
