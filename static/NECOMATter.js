// /user/<<user_name>>.json から取得したobject をHTMLにします。
function RenderTweetToHTML(tweet_list){
	var html = "";
	for (var i = 0, len = tweet_list.length; i < len; i++){
		var tweet = "";
		tweet += '<div class="tweet_column"><span class="tweet_body">';
		tweet += tweet_list[i]['text'];
		tweet += '</span><span class="tweet_time">';
		tweet += tweet_list[i]['time'];
		tweet += '</span></div>';

		html += tweet;
	}
	return html;
}

// /timeline/<<user_name>>.json から取得したobject をHTMLにします。
function RenderTimelineToHTML(tweet_list){
	var html = "";
	for (var i = 0, len = tweet_list.length; i < len; i++){
		var tweet = "";
		tweet += '<div class="tweet_column"><span class="tweet_name"><a href="/user/';
		tweet += tweet_list[i]['user'];
		tweet += '">'
		tweet += tweet_list[i]['user'];
		tweet += '</a></span> <span class="tweet_time">';
		tweet += tweet_list[i]['time'];
		tweet += '</span"><div class="tweet_body">';
		//tweet += tweet_list[i]['text'].replace(/\r\n/g, "<br>").replace(/(\n|\r)/g, "<br>").replace(/([a-z]+:\/\/[\x21-\x7e]+)/gi, "<a href=\"$1\">$1</a>");
		tweet += tweet_list[i]['text'].replace(/\r\n/g, "<br>").replace(/(\n|\r)/g, "<br>").replace(/([a-z]+:\/\/[^\) \t"]+)/gi, "<a href=\"$1\">$1</a>");
		tweet += '</div></div>';

		html += tweet;
	}
	return html;
}

// 動的にtweet page を読み込むためのfunction を返します。
// user_name: ユーザ名
// target: 追加される要素の検索式 ('#tweet_text' とかそういう奴)
function AddTweetAjax_CreateFunc(user_name, target, func) {
	return function (){
		$.getJSON('/user/' + user_name + '.json',
		{},
		function(data, textStatus){
			if(func){
				func();
			}
 			$(target).append(RenderTweetToHTML(data));
		});
	};
}

// 動的にtimeline page を読み込むためのfunction を返します。
// user_name: ユーザ名
// target: 追加される要素の検索式 ('#tweet_text' とかそういう奴)
function AddTimelineAjax_CreateFunc(user_name, target, func) {
	return function (){
		$.getJSON('/timeline/' + user_name + '.json',
		{},
		function(data, textStatus){
			if(func){
				func();
			}
 			$(target).append(RenderTimelineToHTML(data));
		});
	};
}

// resource(/timeline/user.json?...) にアクセスして
// $(append_to) に対してツイートのHTMLを追加します。
// success_func が指定されていたらツイートのHTMLを追加する直前に実行します。
// error_func が指定されていたらエラー時に実行します。
function StartReadTweets(resource, append_to, limit, since_time, success_func, error_func) {
	var option = {};
	if(!(limit === undefined)){
		option['limit'] = limit;
	}
	if(since_time >= 0){
		option['since_time'] = since_time;
	}
	$.ajax({  url: resource
		, type: 'GET'
		, dataType: 'json'
		, data: option
		}).done(function(data, textStatus, jqxHR){
			if(success_func){
				success_func(data, textStatus);
			}
			$(append_to).append(RenderTimelineToHTML(data));
		}).fail(function(jqXHR, textStatus, errorThrown){
			if(error_func){
				error_func(textStatus, errorThrown);
			}
		});
}


// tweet します。tweet に成功した?らfunc を呼びます。
function PostTweet(user_name, text, func){
	post_json_data = {"user_name": user_name, "text": text};
	$.ajax({  url: '/post.json'
		, type: 'POST'
		, data: JSON.stringify(post_json_data)
		, dataType: 'json'
		, contentType: 'application/json'
		}).done(function(data, textStatus, jqxHR){
			if(data['result'] == 'ok'){
				if(func){
					func(data);
				}
			}else{
				console.log("tweet failed." + data['description'])
			}
		}).fail(function(jqXHR, textStatus, errorThrown){
			console.log("post failed");
			console.log(textStatus);
			console.log(errorThrown);
		});
}

// JOSN でpost します。
function PostJSON(url, data, success_func, error_func){
	$.ajax({ url: url
		, type: "POST"
		, data: JSON.stringify(data)
		, contentType: "application/json; charset=utf-8"
		, dataType: "json"
		, success: success_func
		, error: error_func
	});
}

