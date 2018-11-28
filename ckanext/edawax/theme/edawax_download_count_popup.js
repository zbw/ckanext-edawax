// CKAN javascript module to better display the download count for 
// a given resource.

"use strict";

/* edawax_downlaod_count_popup
 *
 * This module adds a Bootstrap popover with additional information
 * about the resources -- download count and page views.
 *
 * title - title of the dataset
 * num_resources - number of resources in the dataset
 *
 */

ckan.module('edawax_download_count_popup', function($, _){
    return {
        initialize: function(){
            $.proxyAll(this, /_on/);

            this.el.popover({title: this.options.title,
                             html: true,
                             content: 'Loading...',
                             placement: 'left'});
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
            this.el.popover('destroy');
            this.el.popover({title: this.options.title, 
                             html: true,
                             content: html, 
                             placement: 'left'});
            this.el.popover('show');
        },
    };
});
