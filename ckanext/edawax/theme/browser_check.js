"use strict;"

ckan.module('browser_check', function($, _){
    return {
        initialize: function(){
            if (navigator.userAgent.indexOf('Edge') !== -1){
                console.log("Please don't use Edge");

            }
        }
    };
});
