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

function AddUser(user_name_id, password_1_id, password_2_id, result_field_id, submit_button_id, can_create_user){
  if(!user_name_id || !password_1_id || !password_2_id || !result_field_id || !submit_button_id || !can_create_user){
    return false;
  }
  var user_name = $(user_name_id).val();
  var password_1 = $(password_1_id).val();
  var password_2 = $(password_2_id).val();
  var canCreateUser = $(can_create_user).prop('checked');
  console.log("user_name: ", user_name, "password: ", password_1, "canCreateUser", canCreateUser);
  $(submit_button_id).attr("disabled", true);
  PostJSON(
    "/add_user.json", {
      'new_user_name': user_name
      , 'new_user_password': password_1
      , 'new_user_can_create_user': canCreateUser
    }
    , function(){
        $(result_field_id).slideUp(0).removeClass('bg-danger').addClass('bg-success').text('user ' + user_name + " created.").slideDown('slow');
        $(submit_button_id).removeAttr("disabled");
    }, function(jqXHR, textStatus, errorThrown){
         response = jqXHR.responseText;
         err_txt = "";
         if(response.length > 0){
           console.log(response);
           err_obj = JSON.parse(response);
           if(err_obj){
             err_txt = err_obj['description'];
           }
         }
         $(result_field_id).slideUp(0).removeClass('bg-success').addClass('bg-danger').text('user ' + user_name + " create failed (" + err_txt + ").").slideDown('slow');
         $(submit_button_id).removeAttr("disabled");
         $(user_name_id).val('');
         $(password_1_id).val('');
         $(password_2_id).val('');
    }
  );
  return false;
}