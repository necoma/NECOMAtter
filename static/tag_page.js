// 最後に読み込んだtweetのUnixTimeを保存しておきます。
// 負の値の場合は何も読み込んでいない事になるはずです
var lastReadUnixTime = -1;
// 一度に読み込むtweetの数を指定します
var readTweetNum = 10;

var location_href = location.href;
//var pathList = location_href.match(/http:\/\/[^\/]+:?\d*\/([^\/]+)*/g).slice(1);
var resourcePath = location_href.match("https?://[^/]+:?\d*/(.*)$")[1];
var pathList = resourcePath.split('/');

// tweet を読み込むURL
var getTweetPath = '/' + pathList.join('/') + ".json";
// Tweet を埋め込む先のID
var targetID = "#Tweet_text";

// サーバから読みだしたdataを使って、lastReadUnixTime を更新します
function LastReadUnixTimeUpdate(data)
{
	if(data.length <= 0){
		return;
	}
	target_tweet = data[data.length - 1];
	if('unix_time' in target_tweet){
		lastReadUnixTime = target_tweet['unix_time'];
	}
}
// lastReadUnixTime を使って、その続きのtweetを読み込みます。
function LoadTweets(func){
	StartReadTweets(getTweetPath // '/tag/{{tag_name}}.json'
			, targetID //"#Tweet_text"
			, readTweetNum
			, lastReadUnixTime
			, function(data) {
				LastReadUnixTimeUpdate(data);
				if(func){
					func(data);
				}
			} );
}

// ページの読み込みが終わった時点で起動するfunction をjQueryから呼び出しています。
$(document).ready(
	function(){
		// tweetはページが読み込まれた後に読み込みを開始します。
		// 最初は now loading... と書いてあるので、読み込みが終わった時点で空文字に上書きします。
		LoadTweets(function() { $('#Tweet_text').html("<div></div>"); });
	});

function ReadMoreButtonClicked(){
	if($("#ReadMoreButton").attr('disabled')){
		return;
	}
	$("#ReadMoreButton").attr('disabled', true);
	LoadTweets(function(data){
		if(data.length >= readTweetNum){
			$("#ReadMoreButton").removeAttr('disabled');
		}
		else
		{
			$("#ReadMoreButton").attr('disabled', true);
		}
	});
}

// スクロールして要素が表示されたら勝手にリロードするようにします
// from http://hennayagyu.com/webhack/javascript/%E3%81%82%E3%82%8B%E8%A6%81%E7%B4%A0%E3%81%8C%E8%A1%A8%E7%A4%BA%E3%81%95%E3%82%8C%E3%81%9F%E3%81%A8%E3%81%8D%E3%81%AB%E5%91%BD%E4%BB%A4%E3%82%92%E5%AE%9F%E8%A1%8C%E3%81%99%E3%82%8Bjavascript-w-jquery-2348
$(function(){
	var triggerNode = $("#ReadMoreButton");
	$(window).scroll(function(){
		var offset_value = $(triggerNode).offset();
		var triggerNodePosition = $(triggerNode).offset().top - $(window).height();
		if( $(window).scrollTop() > triggerNodePosition) {
			ReadMoreButtonClicked();
		}
	});
});
