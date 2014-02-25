function DeleteKeyButtonClicked(key){
	DeleteJSON("/user_setting/key/" + key + ".json", {}, function(data, textStatus, xhr)
		{
			$('#DeleteKey_' + key).fadeOut('slow');
		});
}
function CreateNewKeyButtonClicked(){
	PostJSON("/user_setting/create_new_key.json", {}, function(data, textStatus, xhr)
		{
			if('key' in data){
				var key = data['key'];
				var html = '<li id="DeleteKey_' + key + '">';
				html += '<code>' + key + '</code>';
				html += ' <input type="button" value="delete key" onClick="DeleteKeyButtonClicked("' + key + '");">(NEW!)</li>';
				$('#KeyList').prepend(html);
			}
		}
		, function(xhr, textStatus){
			$('#error_fade').remove();
			$('#KeyList').prepend('<div class="error" id="error_fade">Create New Key failed.</div>');
			$('#error_fade').fadeIn('slow', function(){
				$('#error_fade').fadeOut('slow', function(){
					$('#error_fade').remove();
				});
			});
		});
}
