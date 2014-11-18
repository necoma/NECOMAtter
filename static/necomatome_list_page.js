// 最後に読み込んだmatomeのIDを保存しておきます。
// 負の値の場合は何も読み込んでいない事になるはずです
var lastReadMatomeID = -1;
// 一度に読み込むmatomeの数を指定します
var readMatomeNum = 10;

// NECOMAtome list を読み込むURL
var getMatomePath = '/matome.json';

// Tweet を埋め込む先のID
var targetID = "#Matome_text";

// サーバから読みだしたdataを使って、lastReadMatomeID を更新します
function LastReadMatomeIDUpdate(all_data)
{
	if(!('NEOCMAtome_list' in all_data)){
        	return;
        }
	var data = all_data['NEOCMAtome_list'];
	if(data.length <= 0){
		return;
	}
	target_list = data[data.length - 1];
	if('matome_id' in target_list){
		lastReadMatomeID = data['matome_id'];
	}
}

// JSRender でレンダリングします
function RenderMatomeToHTML(data)
{
        var ret = '';
	if('NEOCMAtome_list' in data){
        	matome_list = data['NEOCMAtome_list'];
        	for(var i = 0; i < matome_list.length; i++){
			ret += $("#Template_MatomeBlock").render(matome_list[i]);
                }
        }
	return ret;
}

// resource(/timeline/user.json?...) にアクセスして
// $(append_to) に対してツイートのHTMLを追加します。
// success_func が指定されていたらツイートのHTMLを追加する直前に実行します。
// error_func が指定されていたらエラー時に実行します。
function StartReadMatome(resource, append_to, limit, since_id, success_func, error_func) {
	var option = {};
	if(!(limit === undefined)){
		option['limit'] = limit;
	}
	if(since_id >= 0){
		option['since_id'] = since_time;
	}
	$.ajax({  url: resource
		, type: 'GET'
		, dataType: 'json'
		, data: option
		}).done(function(data, textStatus, jqxHR){
			if(success_func){
				success_func(data, textStatus);
			}
			var append_dom_list = $(append_to).append(RenderMatomeToHTML(data));
		}).fail(function(jqXHR, textStatus, errorThrown){
			if(error_func){
				error_func(textStatus, errorThrown);
			}
			if($(append_to).text() == 'now loading...'){
				$(append_to).text('load failed.');
			}
		});
}


// lastReadMatomeID を使って、その続きのNECOMAtomeを読み込みます。
function LoadMatome(func, path, target){
	StartReadMatome(path //'/{{request_path}}.json'
			, target //"#Matome_text"
			, readMatomeNum
			, lastReadMatomeID
			, function(data) {
				LastReadMatomeIDUpdate(data);
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
		LoadMatome(function() { $(targetID).html(""); }, getMatomePath, targetID);
	});

function ReadMoreButtonClicked(){
	if($("#ReadMoreButton").attr('disabled')){
		return;
	}
	$("#ReadMoreButton").attr('disabled', true);
	LoadMatome(function(data){
		if(data.length >= readTweetNum){
			$("#ReadMoreButton").removeAttr('disabled');
		}
		else
		{
			$("#ReadMoreButton").attr('disabled', true);
		}
	}, getTweetPath, targetID);
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
