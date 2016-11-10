//Hendrik Bunke
//ZBW - Leibniz Information Centre for Economics
//

"use strict";

// XXX obsolete using data-module now

$('#review_button' ).click(function () {
    var url = $(this).data('url'); // easier to receive the URL from Jinja
    var rev = confirm("This sends an email to the journal's admins, notifying them that your dataset is ready to be reviewed.\n\n Are you sure you want to do that?");
    if (rev == true) {
        location.href = url;
    }
});


$('.infonav li a').filter(function() {
    var url = window.location.href;
    return this.href == url;
}).parent().addClass('active');
