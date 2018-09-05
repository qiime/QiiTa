// http://www.9lessons.info/2012/04/bootstrap-registration-form-tutorial.html
function dualpass_validator() {
  // Popover 
  $('.dualpass input').hover(function()
  {
    $(this).popover('show');
  });

  function validatePasswordIsASCIIOnly(value)
  {
    if(value.match(/^[\x20-\x7E]{1,}$/)) {
        return true;
    }
    return false;
  }

  jQuery.validator.addMethod("validate_password_is_ascii",validatePasswordIsASCIIOnly,"Passwords may only include printable ASCII characters; e.g., A-Z, a-z, 0-9, space, _, -, @, etc.");

  // Validation
  $(".dualpass").validate({
    rules:{
      username:{required:true,email: true},
      email:{required:true, email: true},
      oldpass:{required:true},
      newpass:{required:true, minlength: 8, validate_password_is_ascii:'sel'},
      newpass2:{required:true, minlength: 8, validate_password_is_ascii:'sel', equalTo: "#newpass"},
    },

    messages:{
      email:{
        required:"Enter your email address",
        email:"Enter a valid email address"},
      oldpass:{
        required:"Enter your current password"},
      newpass:{
        required:"Enter your new password",
        minlength:"Password must be a minimum of 8 characters"},
      newpass2:{
        required:"Enter your new password again",
        minlength:"Password must be a minimum of 8 characters",
        equalTo:"'Password' and 'Confirm Password' fields must match"}
    }
  });
}
