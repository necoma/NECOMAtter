//ページを読んでいるユーザ名(document.ready() で更新されるはずです)
var authUserName = "";

// インラインフレームで呼び出されているか否かを示す真偽値
// どうやら document と、window.parent.document(インラインフレームだったら一つ上のdocument) を == で比較すると、
// chrome であれば自分がインラインフレームで呼び出されているか否かが取得できるみたい。
// IEとかFirefoxはわかりません。(ﾟ∀ﾟ)
var isInlineFrame = window.parent.document != document;

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


// tweetを消しますします
function DeleteTweet(tweet_id, success_func, error_func){
  DeleteJSON("/tweet/" + tweet_id
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


// ツイート削除ボタンが押された場合の処理
function DeleteButtonClick(tweet_id, tweet_delete_button_id, text, target_user_name){
  button_element_list = $('#' + tweet_id);
  if(button_element_list.length <= 0)
  {
    return;
  }
  DeleteTweet(tweet_id, function(){
    button_element_list.fadeOut('slow');
  }, function(){
    console.log("can not delete tweet");
  });
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
			AssignTweetColumnClickEvent();
			AssignTweetColumnDraggable();
			$('.dropdown-toggle').dropdown();
		});
}

// tweet が追加された時に呼び出されて、tweet column がクリックされた時のイベントを追加します
function AssignTweetColumnClickEvent(){
	$('.tweet_column').unbind('click', TweetColumnClicked); // 一旦イベントを解除して
	$('.tweet_column').click(TweetColumnClicked); // 再登録します
	$('.tweet_column .btn').click(function(event){event.stopPropagation();}); // このdivにはボタンも含むので、ボタンについてはクリックイベントを親に伝えないようにします
}

// NECOMAtome でまとめられているもののIDをリストします
function GetNECOMATomeTweetIDs(){
	var res = [];
	$("#NECOMAtome_list > .tweet_column").each(function(){
		var tmp = $(this).attr('id');
		if(tmp != null){
			res.push(tmp.replace("dropTweetID_", ""));
		}
	});
	return res;
}

// ドラッグしているtweet の tweetID
var dragging_tweet_id = "";
// tweet が追加された時に呼び出されて、tweet column をドラッグできるようにします
function AssignTweetColumnDraggable(){
	$('.tweet_column').draggable({
		connectToSortable: "#NECOMAtome_list"
		, scope: "NECOMAtome_drop"
		//, containment: "#NECOMAtome_top"
		, helper: "clone"
		, revert: "invalid"
		, handle: ".drag_handle"
		, cursor: "move"
		//, cursorAt: { left: 0, top: 0 }
		, start: function(e){
			// 怪しくドラッグを開始する時につまみ上げられたもののIDを保存しておきます……
			srcID = e.target.id;
			dragging_tweet_id = srcID;
		}
		// XXXX
	});
	//$("#NECOMAtome_block, #Tweet_text").equalHeights();
}

// まとめを新しく作成するためにpostします
function PostMatome(description, tweet_id_list){
	console.log("post NECOMAtome: " + description);
	PostJSON('/matome.json', {
		'tweet_id_list': tweet_id_list,
		'description': description
	},
	function(data){
		if('matome_id' in data){
			var matome_id = data['matome_id'];
			if(matome_id >= 0)
			{
				document.location = '/matome/' + data['matome_id'];
			}
			else
			{
				console.log('ERROR: NECOMAtome post success. but matome_id is invalid(' + matome_id + ')');
			}
		}
		else
		{
			console.log('ERROR: NECOMAtome post success. but matome_id is not found in result.');
		}
	}, function(){
		console.log('NECOMAtome post failed.');
	});
}

// ツイートで、link以外の部分をクリックした場合に反応するためのイベントハンドラです
function TweetColumnClicked(){
	var tweet_column = this;
	var tweet_id_name = this.id;
	var description_object = $("#" + tweet_id_name + " .TweetDescription");
	var tweet_id = this.id.replace('TweetID_', '');
	//description_object.hide().html('a<br>b<br>c<br>d').slideDown();
	if(description_object.text().length > 0)
	{
		description_object.slideUp().html('');
	}
	else
	{
		GetJSON('/tweet/' + tweet_id + '/retweet_user_list.json'
			, ""
			, function(data){
				var description_html = 'Retweet users: ';
				if(!('retweet_user_list' in data)){
					// 中身がなければ何もしません
					return;
				}
				var user_list = data['retweet_user_list'];
				if(user_list.length <= 0){
					// ユーザがいなくてもやっぱり何もしません。
					return;
				}
				for(var i in user_list){
					var user = user_list[i];
					if(!('icon_url' in user) || !('name' in user)){
						// 表示できるものがなくても表示しません
						continue;
					}
					var icon_url = user['icon_url'];
					var name = user['name'];
					var user_id = user['id'];
					description_html += '<a href="/user/' + name + '" data-toggle="tooltip" title="' + name + '">';
					description_html += '<img src="' + icon_url + '" ' + 'height="16px">';
					description_html += '</a> ';
				}
				description_object.html(description_html).slideDown();
			});
	}
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

// csv っぽい文字列があったら table に変換します。
function StrCSV2Table(str){
  return str;

  // 封印中
  var match_result = str.match(/([^,]+,)+([^.]+)\n/gm);
  if(!match_result){
    return str;
  }
  var all = "";
  var lines = str.split("\n");
  var table_start = false;
  for(var i in lines){
    var line = lines[i];
    if(line.replace(/([^,]+,)+([^,]+)/, function(){

       })){
      if(!table_start){
        all += "<table>";
        table_start = true;
      }else if(table_start){
        all += "</table>";
      }
    }
    all += line;
  }
}

// /timeline/<<user_name>>.json から取得した一つのobject(tweet) をHTMLにします。
// テンプレート(jsrender)を使った版のtweetレンダラ
function RenderTweetToHTML(target_tweet, is_not_need_reply_button){
	if( !('id' in target_tweet)
	 || !('user_name' in target_tweet)
	 || !('time' in target_tweet)
	 || !('text' in target_tweet))
	{
		html += '<div class="tweet_column">broken tweet.</div>';
		return html;
	}
	var icon_url = "/static/img/footprint3.1.png"; // 移行期用？アイコン未設定の場合のアイコンはこれにします
	var is_own_retweeted = target_tweet['own_retweeted'];
	var is_own_stard = target_tweet['own_stard'];
	var is_own_tweeted = target_tweet['user_name'] == authUserName;
	if('icon_url' in target_tweet){
		icon_url = target_tweet['icon_url'];
	}
	// 怪しくこの時点でtweet文字列を書き換えます。
	// ・改行は<br>に
	// ・URLっぽい文字列はlinkに
	// ・#タグ ぽい文字列はタグ検索用のURLへのlinkに
	// します。
	// ついでに、@～ が出てきていた場合は覚えておきます
	at_list = new Array();
	replaced_text = target_tweet.text
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
			if(isInlineFrame){
				return '<a href="' + str + '" target="frame_upper_right">' + str + '</a>';
			}
			return '<a href="' + str + '">' + str + '</a>';
		}).replace(/__iframe\[([^\]"]+)\]__/g, function(str){
			str = str.replace(/^__iframe\[/, '').replace(/\]__$/, '');
			url = str.replace(/^([a-z]+)\/\//, "$1://");
			return '<iframe src="' + url + '" frameborder="1" style="-webkit-transform: scale(0.8); -webkit-transform-origin: 0 0;" width="120%" height="300px"></iframe>'
			+ '<a href="' + url + '">' + url + '</a><br>';
		});
        replaced_text = StrCSV2Table(replaced_text);

	// jsrender で使うための情報を作ります
	data = {
		"id": target_tweet.id
		, "user_id": target_tweet.user_name
		, "user_icon_url": icon_url
		, "tweet_body": replaced_text
		, "time": target_tweet.time
		, "is_display_footer": !is_not_need_reply_button
		, "is_own_tweeted": is_own_tweeted
		, "is_own_retweeted": is_own_retweeted
		, "is_own_stard": is_own_stard
		, "is_not_owner": displayUserName == "timeline" || displayUserName != target_tweet.user_name
	};
	// jsrender でレンダリングして返します
	return $("#Template_TweetBlock").render(data);
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
			AssignTweetColumnClickEvent();
			AssignTweetColumnDraggable();
			$('.dropdown-toggle').dropdown();
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
	}).done(function(data, textStatus, jqxHR){
		if(success_func){
			success_func(data, textStatus, jqxHR);
		}
	}).fail(function(jqXHR, textStatus, errorThrown){
		if(error_func){
			error_func(jqXHR, textStatus, errorThrown);
		}
		console.log('post failed.');
		console.log(textStatus);
		console.log(errorThrown);
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

// パスワードの強さを確認してテキトーに表示を変えます。
function SignUp_checkPassword(text){
	var password = $("#sign_up_password_1").val();
	var strength = testPassword(password);

	$("#password_strength").css("background-color", CreateColor(strength));

	var strength_disp = $("#password_strength");
	if(strength > 2/3){
		strength_disp.text("強い");
		$("#password_submit_button").removeAttr("disabled");
	}else if(strength > 1/3){
		strength_disp.text("普通");
		$("#password_submit_button").removeAttr("disabled");
	}else{
		strength_disp.text("弱い");
		$("#password_submit_button").attr("disabled", true);
	}
	// パスワードが2つ同じかどうかを確認します。
	var password_2 = $("#sign_up_password_2").val();
	if(password != password_2){
		$("#password_submit_button").attr("disabled", true);
	}
}


$(document).ready(function(){
	// bootstrap でいろんなものを enable にするための呪文
	$(".collapse").collapse();
	$(".alert").alert();
	$('.dropdown-toggle').dropdown();
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
			AssignTweetColumnClickEvent();
			AssignTweetColumnDraggable();
			$('.dropdown-toggle').dropdown();
		}, function(data){
			$('#GlobalTweetFormHelp').text("tweet failed.").fadeIn("slow").fadeOut("slow");
		});
		return true;
	});

	// フォローしているユーザ名を取得して、Tweet用のテキストエリアに
	// typeahead(文字入力してるときの候補) を設定する
	ApplyUserNameTypeAhead("#GlobalTweetModalText", authUserName);
});
