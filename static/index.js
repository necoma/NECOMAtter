// index.html で読み込まれるJavascript
//

$(document).ready(function(){
	$.getJSON('/user_name_list.json',
		{},
		function(user_name_list, textStatus){
			var html = "";
			html += '<div class="btn-group">';
			html += '<button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown">';
			html += 'UserList <span class="caret"></span>';
			html += '</button>';
			html += '<ul class="dropdown-menu">';
			//html = "";
			for(var i = 0, len = user_name_list.length; i < len; i++){
				user_name = user_name_list[i];
				//html += '<a href="/user/' + user_name + '">' + user_name + '</a> ';
				html += '<li><a href="/user/' + user_name + '">' + user_name + '</a></li>';
			}
			html += '</ul>';
			html += '</div>';
			$('#UserList').html(html);
		}
		);
	}
);

