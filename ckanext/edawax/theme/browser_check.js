/*
 * Microsoft Edge browser doesn't work with the forms.
 * Until that can be addressed this will be used
 * to inform the user that Edge should be avoided.
 */

"use strict;"

function checkLocation(){
    var loc = window.location.href;
    if (loc.includes('/new')){
        return true;
    }

    if (loc.includes('/edit')){
        return true;
    }

    if (loc.includes('resource_edit')){
        return true;
    }

    return false;
}

ckan.module('browser_check', function($){
    var element = null;
    return {
        initialize: function(){
            if (navigator.userAgent.indexOf('Edge') !== -1 && checkLocation()){
                console.log(window.location.href);

                this.sandbox.client.getTemplate('browser_popover.html', this._onReceiveSnippet);
                this._snippetReceived = true;
                element = this.el;
            }
        },

        _onReceiveSnippet: function(html){
            element[0].insertAdjacentHTML('beforeend', html);
            $('#browserModal').modal('show');
        }
    };
});
