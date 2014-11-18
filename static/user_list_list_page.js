var location_href = location.href;
var url_path_matched = location_href.match("://[^/]+:?\d*(.+)");
var url_path = "";
if(url_path_matched && url_path_matched.length > 1){
  url_path = url_path_matched.slice(1)[0];
}
var targetID = "#List_text";

function RenderListHtml(data)
{
  return $("#Template_ListBlock").render({'list': data['list_name_list']});
}

function LoadListNames(func){
  GetJSON(url_path + ".json"
         , ""
         , function(data){
             $(targetID).html(RenderListHtml(data));
         }, function(err){
             $(targetID).html("<div>load error.</div>");
         });
}

// ページの読み込みが終わった時点で起動するfunction をjQueryから呼び出しています。
$(document).ready(
	function(){
		// tweetはページが読み込まれた後に読み込みを開始します。
		// 最初は now loading... と書いてあるので、読み込みが終わった時点で空文字に上書きします。
		LoadListNames(function() { $('#List_text').html("<div></div>"); });
	});
