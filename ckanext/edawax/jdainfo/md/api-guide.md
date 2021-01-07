# API Overview

The Journal Data Archive is built on [CKAN](https://ckan.org) and the CKAN API can be used to access the JDA. The guide to the CKAN API can be [found here](https://docs.ckan.org/en/2.8/api/). Below you can find some details to get started.

## Making a Request
API requests are made over HTTP. To the end of the base JDA url append `/api/3/action/<api-command>`. If there are parameters required they follow the `<api-command>` with a "`?`" between them. Multiple parameters can be added by placing "`&`" between them.

Most requests resturn JSON with three parts:

* `success` - The API should always return a "`200 OK`" message. The value here will tell you if the request went through or not. Returns `true` or `false`
* `result` - The result of the request for the action specified. Will change depending on which action was called
* `help` - URL to documentation for the action

## Useful API Functions
Listed parameters are optional unless otherwise stated.

* `organization_list` - list of all journal names in the JDA
    * Parameters:
        * sort - Set the sorting for results. Given as &lt;field name&gt; &lt;sort-order&gt;. "field name" can be: "name", "title", "package_count". Default is "`name asc`"
        * limit - Numbers of results that will be returned
        * offset - when `limit` is given, sets the starting place for the results
        * organizations - List of groups to return. When provided only organizations in those groups will be returned.
        * all_fields - Returns journal dictionaries. Otherwise only journal names are returned. Default: `false`
        * include_dataset_count - When `all_fields` is set, includes package_count in results. Default: `true`
        * include_extras - When `all_fields` is set, includes journal "extra fields". Default: `false`
        * include_tags - When `all_fields` is set, includes journal's tags.Default: `false`
* `organization_show` - metadata for one journal
    * Parameters:
        * id - ID or name of a organization **[REQUIRED]**
        * include_datasets - Includes truncated list of the journal's datasets. Default `false`
        * include_dataset_count - Includes package_count. Default `true`
        * includes_extras - Includes the journal's extra fields. Default `true`
        * include_tags - Includes the journal's tags. Default `true`
* `package_list` - list of all dataset names in the JDA
    * Paramters:
        * limit - numbers of results that will be returned.
        + offset - when `limit` is given, sets the starting place for the results.
* `package_show` - metadata for one dataset
    * Parameter:
        * id - ID or name of a organization **[REQUIRED]**
        * use_default_schema - The results use the default schema rather than the custom schema. Defatult `false`
        * include_tracking - Include tracking information in the results. Default: `false`
* `resource_show` - show the metadata for a resource
    * Parameter:
        * id - ID or name of a organization **[REQUIRED]**
        * include_tracking - Include tracking information in the results. Default: `false`
* `xml_show` - returns the metadata for a dataset as XML
    * Parameter:
        * id - ID or name of a organization **[REQUIRED]**

## Metadata
The `result` field for all calls returns JSON, except for `xml_show` which returns XML. The individual values for these results can be accessed like anything else stored in JSON.

Registered DOIs can be found in the "dara_DOI" field in `package_show` or `resource_show` calls.

![alt text](/doi.PNG "DOI")




## Examples

* List of all journals

[https://journaldata.zbw.eu/api/3/action/organization_list](https://journaldata.zbw.eu/api/3/action/organization_list)
![alt text](/journal_list.PNG "Journal List")

* List of all journals with additional fields

[https://journaldata.zbw.eu/api/3/action/organization_list?all_fields=true](https://journaldata.zbw.eu/api/3/action/organization_list?all_fields=true)
![alt text](/journal_list_detials.PNG "Journal List with Details")

* Details for one journal

[https://journaldata.zbw.eu/api/3/action/organization_show?id=sdj](https://journaldata.zbw.eu/api/3/action/organization_show?id=sdj)
![alt text](/journal_details.PNG "Journal Details")

* Details for one dataset

[https://journaldata.zbw.eu/api/3/action/package_show?id=data-management-in-economics-journals-replication-data](https://journaldata.zbw.eu/api/3/action/package_show?id=data-management-in-economics-journals-replication-data)
![alt text](/data_details.PNG "Dataset Details")
