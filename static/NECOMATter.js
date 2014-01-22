// GlobalTweetModal をreplyモードにします
function GlobalTweetModal_SetReplyMode(tweet_id, target_user_name){
	$('#GlobalTweetModalLabel').html(target_user_name + ' への返信');
	$('#GlobalTweetModalReplyTo').val(tweet_id);
}
// GlobalTweetModal を通常モード(返信ではない状態)にします
function GlobalTweetModal_SetNormalMode(){
	$('#GlobalTweetModalLabel').html('Tweet');
	$('#GlobalTweetModalReplyTo').val('');
	$('#GlobalTweetModalReplyToTweet').html('');
}

// ReplyButton がクリックされた時にtweet用のmodalを表示します
function ReplyButtonClick(tweet_id, tweet_index, text, target_user_name){
	GlobalTweetModal_SetReplyMode(tweet_id, target_user_name);
	$('#GlobalTweetModalText').val(text);
	$('#GlobalTweetModal').modal('show');

	GetJSON("/tweet/" + tweet_id + ".json"
		, ""
		, function(data, textStatus, jqxHR){
			var html = RenderTimelineToHTML(data, true);
			$('#GlobalTweetModalReplyToTweet').html(html);
		});
}

// starをつけます
function Star(tweet_id, success_func, error_func){
	PostJSON("/tweet/" + tweet_id + "/add_star.json"
		, {}
		, function(){
			if(success_func){
				success_func();
			}
		}
		, function(){
			if(error_func){
				error_func();
			}
		});
}

// starをキャンセルします
function StarCancel(tweet_id, success_func, error_func){
	PostJSON("/tweet/" + tweet_id + "/delete_star.json"
		, {}
		, function(){
			if(success_func){
				success_func();
			}
		}
		, function(){
			if(error_func){
				error_func();
			}
		});
}

// retweetします
function Retweet(tweet_id, success_func, error_func){
	PostJSON("/tweet/" + tweet_id + "/retweet.json"
		, {}
		, function(){
			if(success_func){
				success_func();
			}
		}
		, function(){
			if(error_func){
				error_func();
			}
		});
}

// retweetをキャンセルします
function RetweetCancel(tweet_id, success_func, error_func){
	PostJSON("/tweet/" + tweet_id + "/retweet_cancel.json"
		, {}
		, function(){
			if(success_func){
				success_func();
			}
		}
		, function(){
			if(error_func){
				error_func();
			}
		});
}

// Starボタンが押された場合の処理
function StarButtonClick(tweet_id, star_button_id){
	button_element_list = $('#' + star_button_id);
	if(button_element_list.length <= 0)
	{
		return;
	}
	var star_html = '<span class="glyphicon glyphicon-star"</span> <span class="hidden-xs">へぇを取り消す</span>';
	var not_star_html = '<span class="glyphicon glyphicon-star-empty"</span> <span class="hidden-xs">へぇ</span>';

	var element = button_element_list[0];
	var class_name = element.className;
	// StarボタンまわりのAJAX呼び出し前にボタンをdisableにします
	button_element_list.attr('disabled', 'disabled');
	if(class_name.indexOf('btn-default') > 0){
		Star(tweet_id
			, function(){
				// success
				element.className = class_name.replace('btn-default', 'btn-success');
				element.innerHTML = star_html;
				button_element_list.removeAttr('disabled');
			}
			, function(){
				// failed
				button_element_list.removeAttr('disabled');
			});
	}else{
		StarCancel(tweet_id
			, function(){
				// success
				element.className = class_name.replace('btn-success', 'btn-default');
				element.innerHTML = not_star_html;
				button_element_list.removeAttr('disabled');
			}
			, function(){
				// failed
				button_element_list.removeAttr('disabled');
			});
	}
}

// リツイートボタンが押された場合の処理
function RetweetButtonClick(tweet_id, retweet_button_id){
	button_element_list = $('#' + retweet_button_id);
	if(button_element_list.length <= 0)
	{
		return;
	}
	var retweeted_html = '<span class="glyphicon glyphicon-retweet"></span> <span class="hidden-xs">リツイートを取り消す</span>';
	var not_retweeted_html = '<span class="glyphicon glyphicon-retweet"></span> <span class="hidden-xs">リツイート</span>';

	element = button_element_list[0];
	var class_name = element.className;
	// リツイート周りのAJAX呼び出し前にボタンをdisableにします
	button_element_list.attr('disabled', 'disabled');
	if(class_name.indexOf('btn-default') > 0){
		Retweet(tweet_id
			, function(){
				//success
				element.className = class_name.replace('btn-default', 'btn-success');
				element.innerHTML = retweeted_html;
				button_element_list.removeAttr('disabled');
			}
			, function(){
				// failed
				button_element_list.removeAttr('disabled');
			});
	}else{
		RetweetCancel(tweet_id
			, function(){
				//success
				element.className = class_name.replace('btn-success', 'btn-default');
				element.innerHTML = not_retweeted_html;
				button_element_list.removeAttr('disabled');
			}
			, function(){
				//failed
				button_element_list.removeAttr('disabled');
			});
	}
}

// user_list を受け取って、@~, @~, ... という文字列にします
// toplevel_user は最初の@~ の人になり、重複しないようにします
function CreateAtText(toplevel_user, user_list){
	var text = '@' + toplevel_user + ' ';
	for(var i = 0; i < user_list.length; ++i)
	{
		var user = user_list[i];
		if(user == toplevel_user)
		{
			continue;
		}
		text += "@" + user_list[i] + ' ';
	}
	return text;
}

// /timeline/<<user_name>>.json から取得した一つのobject(tweet) をHTMLにします。
// TODO: 何かテンプレートを使ったようなものにしたほうがよかったような……
function RenderTweetToHTML(target_tweet, is_not_need_reply_button){
	if( !('id' in target_tweet)
	 || !('user_name' in target_tweet)
	 || !('time' in target_tweet)
	 || !('text' in target_tweet))
	{
		html += '<div class="tweet_column">broken tweet.</div>';
		return html;
	}
	var tweet_id = target_tweet['id'];
	var tweet_index = "TweetID_" + tweet_id;
	var user = target_tweet['user_name'];
	var time = target_tweet['time'];
	var text = target_tweet['text'];
	var icon_url = "/static/img/footprint3.1.png"; // 移行期用？アイコン未設定の場合のアイコンはこれにします
	var is_own_stard = target_tweet['own_stard'];
	var is_own_retweeted = target_tweet['own_retweeted'];
	if('icon_url' in target_tweet){
		icon_url = target_tweet['icon_url'];
	}
	var tweet = "";
	//tweet += '<div class="tweet_column pull-right img-responsive" id="TweetID_' + tweet_id + '">';
	tweet += '<div class="tweet_column img-responsive" id="' + tweet_index + '">';
	tweet += '<a href="/user/' + user + '">';
	tweet += '<div class="ImageFloat"><img src="' + icon_url + '" width="40" alt=""></div>';
	tweet += ' <span class="tweet_name">';
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
	// ついでに、@～ が出てきていた場合は覚えておきます
	at_list = new Array();
	tweet += text
		.replace(/\r\n/g, "<br>")
		.replace(/(\n|\r)/g, "<br>")
		.replace(/([a-z]+:\/\/[^\) \t"]+)|(#[^< ]+)|(@[^< ]+)/gi, function(str){
			if(str.match(/^#/)){
				var tag_name = str.replace(/^#/, '');
				return '<a href="/tag/'
					+ tag_name + '">' + str + '</a>';
			}else if(str.match(/^@/)){
				var user_name = str.replace(/^@/, '');
				at_list.push(user_name);
				return '<a href="/user/'
					+ user_name + '">' + str + '</a>';
			}
			return '<a href="' + str + '">' + str + '</a>';
		});
	tweet += '</div>';
	tweet += '<div class="tweet_footer text-right">';
	if(!is_not_need_reply_button){
		tweet += '<a href="javascript: ReplyButtonClick(' + tweet_id + ", '" + tweet_index + "', '" + CreateAtText(user, at_list) + "', '" + user + "'" + ');"';
		tweet += ' class="btn btn-default btn-mini" type="button">';
		tweet += '<span class="glyphicon glyphicon-pencil"></span> <span class="hidden-xs">返信</span></a> ';
		var retweet_button_id = "RetweetButton_ID_" + tweet_id;
		tweet += '<a ';
		var retweet_text = "リツイート";
		if(is_own_retweeted){
			tweet += 'class="btn btn-success btn-mini" ';
			retweet_text = "リツートを取り消す";
		}else{
			tweet += 'class="btn btn-default btn-mini" ';
		}
		tweet += 'id="' + retweet_button_id + '" href="javascript: RetweetButtonClick(' + tweet_id + ", '" + retweet_button_id + "'" + ');" type="button"><span class="glyphicon glyphicon-retweet"></span> <span class="hidden-xs">' + retweet_text + '</span></a> ';
		var star_button_id = "StarButton_ID_" + tweet_id;
		var star_button_text = '<span class="glyphicon glyphicon-star-empty"</span> <span class="hidden-xs">へぇ</span>';
		var star_button_class = 'class="btn btn-default btn-mini"';
		if(is_own_stard){
			star_button_text = '<span class="glyphicon glyphicon-star"</span> <span class="hidden-xs">へぇを取り消す</span>';
			star_button_class = 'class="btn btn-success btn-mini"';
		}
		tweet += '<a id="' + star_button_id + '" '
			+ 'href="javascript: StarButtonClick(' + tweet_id + ", '" + star_button_id + "'" + ');" '
			+ star_button_class + ' type="button">' + star_button_text + '</a> ';
	}
	tweet += '</div>';
	tweet += '<span class="ImageFloatClear"></span>';
	tweet += '</div>';

	return tweet;
}
// /timeline/<<user_name>>.json から取得したobject(tweetのリスト) をHTMLにします。
function RenderTimelineToHTML(tweet_list, is_not_need_reply_button){
	var html = "";
	for (var i = 0, len = tweet_list.length; i < len; i++){
		var tweet_html = RenderTweetToHTML(tweet_list[i], is_not_need_reply_button);
		html += tweet_html;
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
			if($(append_to).text() == 'now loading...'){
				$(append_to).text('load failed.');
			}
		});
}


// tweet します。tweet に成功した?らfunc を呼びます。
function PostTweet(user_name, text, reply_to, func){
	post_json_data = {"user_name": user_name, "text": text};
	if(reply_to > 0){
		post_json_data['reply_to'] = reply_to;
	}
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

// JSON をGETします。
function GetJSON(url, data, success_func, error_func){
	$.ajax({url: url
		, type: "GET"
		, data: data
		, dataType: 'json'
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

// フォローしているユーザ名を取得して、".TweetTextArea" の
// typeahead(文字入力してるときの候補) 用 data-source を更新する
function UpdateTypeAheadForUserList(target_class, user_name){
	$.getJSON("/user/" + user_name + "/followed_user_name_list.json",
		{},
		function(user_name_list, textStatus){
			$(target_class).attr("data-items", user_name_list);
		}
	);
}

// 指定されたオブジェクトに user_name のフォローしているユーザ名のtypeaheadを設定する
function ApplyUserNameTypeAhead(target, user_name){
	$.getJSON("/user/" + user_name + "/followed_user_name_list.json"
		, {}
		, function(user_name_list){
			var at_name_list = [];
			for(var i = 0; i < user_name_list.length; i++)
			{
				at_name_list.push("@" + user_name_list[i] + " ");
			}
			$(target).typeahead({source: at_name_list});
		}
	);
}

//ページを読んでいるユーザ名(document.ready() で更新されるはずです)
var authUserName = "";

$(document).ready(function(){
	// bootstrap でいろんなものを enable にするための呪文
	$(".collapse").collapse();
	$(".alert").alert();
	// ページを読んでいるユーザ名を更新します
	authUserName = $("#AuthUserName").text();

	$("#GlobalTweetModalSubmitButton").prop('disabled', true);
	// GlobalTweetModal でテキストが入力されていなければTweetボタンを押させない
	$('#GlobalTweetModalForm textarea').each(function(){
		$(this).bind('keyup', function(elm){
			var txt = $('#GlobalTweetModalText').val();
			if(txt == ""){
				$("#GlobalTweetModalSubmitButton").attr('disabled', 'disabled');
				GlobalTweetModal_SetNormalMode();
			}else{
				$("#GlobalTweetModalSubmitButton").removeAttr('disabled');
			}
		});
	});

	// global なtweetダイアログからのtweet
	$('#GlobalTweetModalSubmitButton').click(function(){
		var text = $("#GlobalTweetModalText").val();
		var reply_to = $("#GlobalTweetModalReplyTo").val();
		var user = authUserName;
		if(text == "")
		{
			$('#GlobalTweetFormHelp').text("please imput text").fadeIn("slow").fadeOut("slow");
			return false;
		}
		PostTweet(user, text, reply_to, function(data){
			GlobalTweetModal_SetNormalMode();
			$('#GlobalTweetModalText').val('');
			$('#GlobalTweetModal').modal('hide');
			html = RenderTimelineToHTML([data]);
			$('#Tweet_text > div:first').before(html).fadeIn("slow");
		}, function(data){
			$('#GlobalTweetFormHelp').text("tweet failed.").fadeIn("slow").fadeOut("slow");
		});
		return true;
	});

	// フォローしているユーザ名を取得して、Tweet用のテキストエリアに
	// typeahead(文字入力してるときの候補) を設定する
	ApplyUserNameTypeAhead("#GlobalTweetModalText", authUserName);
});
