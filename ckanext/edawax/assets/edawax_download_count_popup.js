// CKAN javascript module to better display the download count for
// a given resource.

"use strict";

/* edawax_downlaod_count_popup
 *
 * This module adds a Bootstrap popover with additional information
 * about the resources -- download count and page views.
 *
 * title - title of the dataset
 * id - package's id
 */

ckan.module('edawax_download_count_popup', function($, _){
    // Fix to prevent needed to click twice to get popover working
    // https://stackoverflow.com/questions/32581987/need-click-twice-after-hide-a-shown-bootstrap-popover/34320956
    $('body').on('hidden.bs.popover', function (e) {
        $(e.target).data("bs.popover").inState.click = false;
    });
    return {
        initialize: function(){
            $.proxyAll(this, /_on/);
            var len = this.options.title.length;
            this.el.popover({title: '<span class="text-info"><strong>'+ this.options.title + '</strong></span><a type="button" class="close" style="float:right;" onclick="$(&quot;#' + this.options.id + '_popup&quot;).popover(&quot;hide&quot;);">&times;</a>',
                             html: true,
                             content: 'Loading...',
                             placement: function(){
                                if (len > 30){
                                    return "left";
                                }
                                return "right";
                             } });
            this.el.on('click', this._onClick);
        },

        _snippetReceived: false,
        _onClick: function(event){
            if (!this._snippetReceived){
                this.sandbox.client.getTemplate('edawax_resource_popup.html',
                    this.options,
                    this._onReceiveSnippet);
                this._snippetReceived = true;
            }
        },

        _onReceiveSnippet: function(html){
            // Instead of destroying the loading message, rewrite it.
            var len = this.options.title.length;
            this.el.data('bs.popover').options.html = true;
            this.el.data('bs.popover').options.sanitize = false;
            this.el.data('bs.popover').options.title = '<span class="text-info"><strong>'+ this.options.title + '</strong></span><a class="close" style="float:right;" onclick="$(&quot;#' + this.options.id + '_popup&quot;).popover(&quot;hide&quot;);">&times;</a>';
            this.el.data('bs.popover').options.content = html;
            if (len > 30){
                this.el.data('bs.popover').options.placement = 'left';
            } else {
                this.el.data('bs.popover').options.placement = 'right';
            }
            this.el.popover('show');
        },

    };
});
