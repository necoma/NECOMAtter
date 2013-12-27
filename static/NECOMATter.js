// /timeline/<<user_name>>.json から取得したobject をHTMLにします。
function RenderTimelineToHTML(tweet_list){
	var html = "";
	for (var i = 0, len = tweet_list.length; i < len; i++){
		var target_tweet = tweet_list[i]
		if( !('id' in target_tweet)
		 || !('user_name' in target_tweet)
		 || !('time' in target_tweet)
		 || !('text' in target_tweet))
		{
			html += '<div class="tweet_column">broken tweet.</div>'
			continue;
		}
		var tweet_id = target_tweet['id'];
		var user = target_tweet['user_name'];
		var time = target_tweet['time'];
		var text = target_tweet['text'];
		var tweet = "";
		tweet += '<div class="tweet_column" id="TweetID_' + tweet_id + '"><span class="tweet_name"><a href="/user/';
		tweet += user;
		tweet += '">'
		tweet += user;
		tweet += '</a></span> <span class="tweet_time"><a href="/tweet/';
		tweet += tweet_id;
		tweet += '">';
		tweet += time;
		tweet += '</a></span"><div class="tweet_body">';
		// 怪しくこの時点で文字列を書き換えます。
		// ・改行は<br>に
		// ・URLっぽい文字列はlinkに
		// ・#タグ ぽい文字列はタグ検索用のURLへのlinkに
		// します。
		tweet += text.replace(/\r\n/g, "<br>").replace(/(\n|\r)/g, "<br>").replace(/([a-z]+:\/\/[^\) \t"]+)|(#[^< ]+)/gi, function(str){
				if(str.match(/^#/)){
					var tag_name = str.replace(/^#/, '');
					return '<a href="/tag/' + tag_name + '">' + str + '</a>';
				}
				return '<a href="' + str + '">' + str + '</a>';
			});
		tweet += '</div></div>';

		html += tweet;
	}
	return html;
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

// JOSN でDELETE します。
function DeleteJSON(url, data, success_func, error_func){
	$.ajax({ url: url
		, type: "DELETE"
		, data: JSON.stringify(data)
		, contentType: "application/json; charset=utf-8"
		, dataType: "json"
		, success: success_func
		, error: error_func
	});
}


//10進数を2桁の16進数に変換
function convert16(_decimalNumber) {
	var decimalNumber = Math.floor(_decimalNumber);
	var value = decimalNumber.toString(16) + "";

	if (value.length < 2) {
		value = "0" + value;
	}
	return value;
}

// http://jsdo.it/windblue/bar_graph_01
// 0 から 1 に正規化された数字(normalized_value) について、
// 赤→黄→緑 と変化する色のうち、どの色になるのかを計算して "#rrggbb" の形式にして返します。
function CreateColor(normalized_value
		, left_red, left_green, left_blue
		, middle_red, middle_green, middle_blue
		, right_red, right_green, right_blue){
	var leftRed = left_red || 255;
	var leftGreen = left_green || 0;
	var leftBlue = left_blue || 128;

	var middleRed = middle_red || 255;
	var middleGreen = middle_green || 255;
	var middleBlue = middle_blue || 128;
        
	var rightRed = right_red || 0;
	var rightGreen = right_green || 255;
	var rightBlue = right_blue || 128;

	if(normalized_value < 0.5){
		var v = normalized_value * 2;
		var red = leftRed - (leftRed - middleRed) * v;
		var green = leftGreen - (leftGreen - middleGreen) * v;
		var blue = leftBlue - (leftBlue - middleBlue) * v;
	}else{
		var v = (normalized_value - 0.5) * 2;
		var red = middleRed - (middleRed - rightRed) * v;
		var green = middleGreen - (middleGreen - rightGreen) * v;
		var blue = middleBlue - (middleBlue - rightBlue) * v;
	}

	return "#" + convert16(red) + convert16(green) + convert16(blue);
}
